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

# userErrors codes that mean "not found".
# - Any other code means Shopify rejected the change.
_NOT_FOUND_CODES = frozenset(
    {"PRODUCT_DOES_NOT_EXIST", "PRODUCT_VARIANT_DOES_NOT_EXIST", "MUST_BE_FOR_THIS_PRODUCT"}
)


class GraphQLTransport(Protocol):
    """The part of ShopifyGraphQLClient the gateway uses (and tests fake)."""

    async def execute(self, document: str, variables: dict[str, Any] | None = None) -> dict[str, Any]: ...


class AdminApiProductGateway:
    """Reads and writes the catalog of a real Shopify store.

    - In: GraphQL shapes, global IDs, Money strings.
    - Out: application models with numeric IDs and Decimal prices.
    """

    def __init__(self, client: GraphQLTransport) -> None:
        self._client = client
        # Shop currency:
        # - cached after the first read
        # - the mutation response does not include it
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
        # - Non-numeric IDs cannot exist in Shopify.
        # - Return 404 now, instead of a GraphQL error that becomes a 502.
        if not (product_id.isdigit() and variant_id.isdigit()):
            raise VariantNotFoundError(f"Variant {variant_id} does not exist on product {product_id}.")

        variant_input: dict[str, Any] = {"id": to_global_identifier("ProductVariant", variant_id)}
        if price is not None:
            # Send money as a string to stay exact.
            variant_input["price"] = str(price)
        if inventory_policy is not None:
            variant_input["inventoryPolicy"] = inventory_policy.value

        data = await self._client.execute(
            VARIANT_UPDATE_MUTATION,
            {"productId": to_global_identifier("Product", product_id), "variants": [variant_input]},
        )
        result = _required(data, "productVariantsBulkUpdate")

        # userErrors arrive with a 200, so check them here.
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
        """Map one variant node. Raise ShopifyError if it is malformed."""
        try:
            return ProductVariant(
                id=to_numeric_identifier(node["id"]),
                product_id=to_numeric_identifier(node["product"]["id"]),
                title=node["title"],
                sku=node.get("sku") or None,
                # Price is a string or a Decimal, never a float.
                price=Decimal(str(node["price"])),
                currency_code=self._currency_code or "",
                # Null when stock is not tracked; show 0.
                inventory_quantity=node.get("inventoryQuantity") or 0,
                inventory_policy=InventoryPolicy(node["inventoryPolicy"]),
                updated_at=datetime.fromisoformat(node["updatedAt"]),
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            raise ShopifyError(f"Shopify returned a variant that could not be read: {error!r}") from error


def _required(data: dict[str, Any], *path: str) -> Any:
    """Read a nested key, raising ShopifyError instead of KeyError."""
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or current.get(key) is None:
            raise ShopifyError(f"Shopify returned a response without {'.'.join(path)}.")
        current = current[key]
    return current
