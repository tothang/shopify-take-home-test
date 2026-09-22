"""Changing a variant, and telling every connected browser about it.

Two paths end with the same obligation. The update endpoint changes a variant
itself, and the webhook hears that somebody else changed one. Both have to
reach every open tab, or an operator ends up looking at a price that is no
longer the price. Keeping that obligation in one place means the next caller
cannot forget it.
"""

from decimal import Decimal

from application.schemas import InventoryPolicy, ProductVariant, VariantUpdatedEvent
from application.services.event_broker import event_broker
from application.shopify.gateway import ProductGateway

# Where a change came from, for the log and for anyone reading the stream. The
# browser does not need it: it orders every change by updated_at, its own
# included, so one rule covers an echo of its own edit and somebody else's.
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

    Raises VariantNotFoundError when the variant does not exist, and
    VariantUpdateRejectedError when the catalog refuses the change. Callers
    turn those into status codes; this function does not know about HTTP.
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
