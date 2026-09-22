import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from application.schemas import InventoryPolicy, Product, ProductVariant
from application.shopify.errors import ShopifyError, VariantNotFoundError, VariantUpdateRejectedError
from application.shopify.graphql_documents import (
    PRODUCTS_QUERY,
    SHOP_CURRENCY_QUERY,
    VARIANT_UPDATE_MUTATION,
    VARIANTS_PER_PRODUCT,
)
from application.shopify.identifiers import to_global_identifier, to_numeric_identifier

logger = logging.getLogger(__name__)

# The userErrors codes that mean the thing the caller named is not there. Any
# other code means Shopify understood the request and refused it.
_NOT_FOUND_CODES = frozenset(
    {"PRODUCT_DOES_NOT_EXIST", "PRODUCT_VARIANT_DOES_NOT_EXIST", "MUST_BE_FOR_THIS_PRODUCT"}
)


class GraphQLTransport(Protocol):
    """What the gateway needs from ShopifyGraphQLClient, and all a test must fake."""

    async def execute(self, document: str, variables: dict[str, Any] | None = None) -> dict[str, Any]: ...


class AdminApiProductGateway:
    """Reads and writes the catalog of a real Shopify store.

    This is the boundary. Global identifiers, the Money scalar and the
    GraphQL response shape stop here; what leaves is the application models,
    with numeric identifiers and decimal prices.
    """

    def __init__(self, client: GraphQLTransport) -> None:
        self._client = client
        # A variant's price is in the shop currency, and a mutation cannot ask
        # the shop for it. Kept after the first read; a shop changes its
        # currency rarely, and never in the middle of a sale.
        self._currency_code: str | None = None

    async def list_products(self, limit: int = 25) -> list[Product]:
        data = await self._client.execute(
            PRODUCTS_QUERY,
            {"first": limit, "variantsPerProduct": VARIANTS_PER_PRODUCT},
        )
        self._currency_code = _required(data, "shop", "currencyCode")

        products = []
        for node in _required(data, "products", "nodes"):
            variants = node["variants"]
            if variants.get("pageInfo", {}).get("hasNextPage"):
                logger.warning(
                    "A product has more variants than one page, and only the first page is shown.",
                    extra={"product_id": to_numeric_identifier(node["id"]), "shown": VARIANTS_PER_PRODUCT},
                )
            products.append(
                Product(
                    id=to_numeric_identifier(node["id"]),
                    title=node["title"],
                    status=node["status"],
                    variants=[self._to_variant(variant) for variant in variants["nodes"]],
                )
            )
        return products

    async def update_variant(
        self,
        product_id: str,
        variant_id: str,
        price: Decimal | None = None,
        inventory_policy: InventoryPolicy | None = None,
    ) -> ProductVariant:
        # Anything but digits cannot name a Shopify record. Sent as it is, it
        # would come back as a GraphQL error, which reads as the store failing
        # rather than as the caller asking for something that is not there.
        if not (product_id.isdigit() and variant_id.isdigit()):
            raise VariantNotFoundError(f"Variant {variant_id} does not exist on product {product_id}.")

        variant_input: dict[str, Any] = {"id": to_global_identifier("ProductVariant", variant_id)}
        if price is not None:
            # Money travels as text. str of a Decimal is exact; a float is not.
            variant_input["price"] = str(price)
        if inventory_policy is not None:
            variant_input["inventoryPolicy"] = inventory_policy.value

        data = await self._client.execute(
            VARIANT_UPDATE_MUTATION,
            {"productId": to_global_identifier("Product", product_id), "variants": [variant_input]},
        )
        result = _required(data, "productVariantsBulkUpdate")

        # A 200 with userErrors is a failure. The transport has no way to know.
        user_errors = result.get("userErrors") or []
        if any(error.get("code") in _NOT_FOUND_CODES for error in user_errors):
            raise VariantNotFoundError(f"Variant {variant_id} does not exist on product {product_id}.")
        if user_errors:
            messages = "; ".join(error.get("message") or "unknown error" for error in user_errors)
            raise VariantUpdateRejectedError(f"Shopify refused the change: {messages}")

        for node in result.get("productVariants") or []:
            if to_numeric_identifier(node["id"]) == variant_id:
                if self._currency_code is None:
                    self._currency_code = _required(
                        await self._client.execute(SHOP_CURRENCY_QUERY), "shop", "currencyCode"
                    )
                return self._to_variant(node)
        raise ShopifyError("Shopify accepted the change but did not return the variant.")

    def _to_variant(self, node: dict[str, Any]) -> ProductVariant:
        """Map one variant node. A node we cannot read is the store failing, not a crash."""
        try:
            return ProductVariant(
                id=to_numeric_identifier(node["id"]),
                product_id=to_numeric_identifier(node["product"]["id"]),
                title=node["title"],
                sku=node.get("sku") or None,
                # The client parses numbers as Decimal and Money arrives as text,
                # so neither path goes through a float. str() covers both.
                price=Decimal(str(node["price"])),
                currency_code=self._currency_code or "",
                # Null when the shop does not track stock for this variant. Zero
                # is the honest reading of "nothing we know of to sell".
                inventory_quantity=node.get("inventoryQuantity") or 0,
                inventory_policy=InventoryPolicy(node["inventoryPolicy"]),
                updated_at=datetime.fromisoformat(node["updatedAt"]),
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            raise ShopifyError(f"Shopify returned a variant that could not be read: {error!r}") from error


def _required(data: dict[str, Any], *path: str) -> Any:
    """Walk into a response, and fail as ShopifyError rather than KeyError."""
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or current.get(key) is None:
            raise ShopifyError(f"Shopify returned a response without {'.'.join(path)}.")
        current = current[key]
    return current
