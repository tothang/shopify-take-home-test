from decimal import Decimal

import pytest

from application.schemas import InventoryPolicy
from application.shopify.errors import VariantNotFoundError
from application.shopify.in_memory_gateway import InMemoryProductGateway


async def test_list_products_returns_the_seeded_catalog(gateway: InMemoryProductGateway) -> None:
    products = await gateway.list_products()

    assert len(products) == 3
    assert all(product.variants for product in products)


async def test_list_products_respects_the_limit(gateway: InMemoryProductGateway) -> None:
    products = await gateway.list_products(limit=1)

    assert len(products) == 1


async def test_update_variant_changes_price_and_policy(gateway: InMemoryProductGateway) -> None:
    updated = await gateway.update_variant(
        product_id="8100000000001",
        variant_id="45100000000001",
        price=Decimal("18.50"),
        inventory_policy=InventoryPolicy.CONTINUE,
    )

    assert updated.price == Decimal("18.50")
    assert updated.inventory_policy is InventoryPolicy.CONTINUE

    products = await gateway.list_products()
    stored = next(variant for variant in products[0].variants if variant.id == "45100000000001")
    assert stored.price == Decimal("18.50")
    assert stored.inventory_policy is InventoryPolicy.CONTINUE


async def test_update_variant_leaves_untouched_fields_alone(gateway: InMemoryProductGateway) -> None:
    before = (await gateway.list_products())[0].variants[0]

    updated = await gateway.update_variant(
        product_id="8100000000001",
        variant_id="45100000000001",
        price=Decimal("18.50"),
    )

    assert updated.inventory_policy is before.inventory_policy
    assert updated.inventory_quantity == before.inventory_quantity


async def test_update_variant_rejects_an_unknown_variant(gateway: InMemoryProductGateway) -> None:
    with pytest.raises(VariantNotFoundError):
        await gateway.update_variant(
            product_id="8100000000001",
            variant_id="does-not-exist",
            price=Decimal("10.00"),
        )
