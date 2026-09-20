import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from application.schemas import InventoryPolicy, Product, ProductVariant
from application.shopify.errors import VariantNotFoundError


def _build_seed_catalog() -> dict[str, Product]:
    timestamp = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
    deny = InventoryPolicy.DENY
    keep_selling = InventoryPolicy.CONTINUE
    definitions = [
        (
            "8100000000001",
            "Everyday Cotton T-Shirt",
            [
                ("45100000000001", "Small / Black", "COTTON-TEE-S-BLACK", "24.00", 12, deny),
                ("45100000000002", "Medium / Black", "COTTON-TEE-M-BLACK", "24.00", 0, keep_selling),
                ("45100000000003", "Large / Black", "COTTON-TEE-L-BLACK", "24.00", 3, deny),
            ],
        ),
        (
            "8100000000002",
            "Insulated Travel Bottle",
            [
                ("45100000000004", "500 milliliter", "BOTTLE-500", "32.50", 48, deny),
                ("45100000000005", "750 milliliter", "BOTTLE-750", "38.00", 0, deny),
            ],
        ),
        (
            "8100000000003",
            "Merino Wool Beanie",
            [
                ("45100000000006", "One size / Grey", "BEANIE-GREY", "19.90", 7, keep_selling),
            ],
        ),
    ]

    catalog: dict[str, Product] = {}
    for product_id, product_title, variant_definitions in definitions:
        variants = [
            ProductVariant(
                id=variant_id,
                product_id=product_id,
                title=variant_title,
                sku=sku,
                price=Decimal(price),
                currency_code="USD",
                inventory_quantity=quantity,
                inventory_policy=policy,
                updated_at=timestamp,
            )
            for variant_id, variant_title, sku, price, quantity, policy in variant_definitions
        ]
        catalog[product_id] = Product(
            id=product_id,
            title=product_title,
            status="ACTIVE",
            variants=variants,
        )
    return catalog


class InMemoryProductGateway:
    """A small fake store so the application runs without Shopify credentials.

    It is deliberately simple: no pagination, no rate limits, no failures.
    Treat it as a development convenience, not as a model of Shopify.
    """

    def __init__(self) -> None:
        self._products = _build_seed_catalog()
        self._lock = asyncio.Lock()

    async def list_products(self, limit: int = 25) -> list[Product]:
        async with self._lock:
            return [product.model_copy(deep=True) for product in list(self._products.values())[:limit]]

    async def update_variant(
        self,
        product_id: str,
        variant_id: str,
        price: Decimal | None = None,
        inventory_policy: InventoryPolicy | None = None,
    ) -> ProductVariant:
        async with self._lock:
            product = self._products.get(product_id)
            if product is None:
                raise VariantNotFoundError(f"Product {product_id} does not exist.")

            for index, variant in enumerate(product.variants):
                if variant.id != variant_id:
                    continue
                updated = variant.model_copy(
                    update={
                        "price": price if price is not None else variant.price,
                        "inventory_policy": (
                            inventory_policy if inventory_policy is not None else variant.inventory_policy
                        ),
                        "updated_at": datetime.now(tz=UTC),
                    }
                )
                product.variants[index] = updated
                return updated.model_copy(deep=True)

            raise VariantNotFoundError(f"Variant {variant_id} does not exist on product {product_id}.")
