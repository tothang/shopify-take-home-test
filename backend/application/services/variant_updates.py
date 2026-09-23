"""Changing a variant, and telling every connected browser about it.

- Both the update endpoint and the webhook must broadcast to every open tab.
- Keeping that in one place means no caller can forget it.
"""

from decimal import Decimal

from application.schemas import InventoryPolicy, ProductVariant, VariantUpdatedEvent
from application.services.event_broker import event_broker
from application.shopify.gateway import ProductGateway

# Where a change came from.
# - Informational only (log and stream readers).
# - The browser orders changes by updated_at, whatever the source.
SOURCE_API = "api"
SOURCE_WEBHOOK = "webhook"


async def apply_variant_change(
    gateway: ProductGateway,
    product_id: str,
    variant_id: str,
    price: Decimal | None = None,
    inventory_policy: InventoryPolicy | None = None,
) -> ProductVariant:
    """Apply a change through the gateway and broadcast what was stored.

    - Raises VariantNotFoundError or VariantUpdateRejectedError.
    - Callers map them to HTTP status codes.
    """
    variant = await gateway.update_variant(
        product_id=product_id,
        variant_id=variant_id,
        price=price,
        inventory_policy=inventory_policy,
    )
    await broadcast_variant_update(variant, source=SOURCE_API)
    return variant


async def broadcast_variant_update(variant: ProductVariant, source: str) -> None:
    """Push one variant to every connected browser."""
    await event_broker.publish(VariantUpdatedEvent(source=source, variant=variant))
