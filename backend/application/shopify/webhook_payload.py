"""Turning the REST shaped products/update payload into application models.

Shopify sends webhooks in the REST shape even when the rest of the
integration speaks GraphQL, so this is the one place that understands lower
case policy values and identifiers that arrive as numbers.

It is a plain function rather than part of the route on purpose: the mapping
is the part most likely to be wrong, and this way it can be tested without
signing a request first.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from application.schemas import InventoryPolicy, ProductVariant

logger = logging.getLogger(__name__)

# The REST webhook payload carries no currency. A shop has exactly one, and
# Shopify assumes the receiver already knows it. An application serving
# several shops would read it once from the shop record and cache it per shop;
# here there is one shop and the seed catalog is in dollars.
DEFAULT_CURRENCY_CODE = "USD"


def variants_from_webhook_payload(payload: Any) -> list[ProductVariant]:
    """Map every variant in a products/update payload.

    A variant that cannot be mapped is logged and left out rather than
    failing the whole webhook. Shopify retries a webhook it considers failed,
    and a payload we cannot read will not read any better the second time.

    A payload that is not shaped like one at all raises TypeError. This
    function raises nothing but ValueError, KeyError and TypeError, which is
    what the route catches.
    """
    if not isinstance(payload, dict):
        raise TypeError(f"A products/update payload is a JSON object, not {type(payload).__name__}.")
    entries = payload.get("variants") or []
    if not isinstance(entries, list):
        raise TypeError(
            f"The variants of a products/update payload are a list, not {type(entries).__name__}."
        )

    product_id = _as_identifier(payload.get("id"))
    fallback_timestamp = payload.get("updated_at")

    variants: list[ProductVariant] = []
    for entry in entries:
        variant = _variant_from_entry(entry, product_id, fallback_timestamp)
        if variant is not None:
            variants.append(variant)
    return variants


def _variant_from_entry(
    entry: Any,
    product_id: str,
    fallback_timestamp: Any,
) -> ProductVariant | None:
    if not isinstance(entry, dict):
        logger.warning(
            "Skipped a variant in a products/update payload that is not an object.",
            extra={"product_id": product_id, "entry_type": type(entry).__name__},
        )
        return None
    try:
        return ProductVariant(
            id=_as_identifier(entry["id"]),
            product_id=_as_identifier(entry.get("product_id")) or product_id,
            title=entry.get("title") or "",
            sku=entry.get("sku"),
            price=_as_money(entry["price"]),
            currency_code=entry.get("currency_code") or DEFAULT_CURRENCY_CODE,
            inventory_quantity=int(entry.get("inventory_quantity") or 0),
            inventory_policy=_as_inventory_policy(entry["inventory_policy"]),
            updated_at=_as_timestamp(entry.get("updated_at") or fallback_timestamp),
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        logger.warning(
            "Skipped a variant in a products/update payload that could not be mapped.",
            exc_info=True,
            extra={"variant_id": _as_identifier(entry.get("id")), "product_id": product_id},
        )
        return None


def _as_identifier(value: Any) -> str:
    """Webhook identifiers arrive as numbers; this API carries them as strings."""
    return "" if value is None else str(value)


def _as_money(value: Any) -> Decimal:
    """Take the price as text, so it never passes through a float on the way in."""
    return Decimal(str(value))


def _as_inventory_policy(value: Any) -> InventoryPolicy:
    """ "continue" over the wire is InventoryPolicy.CONTINUE here.

    An unknown value raises, which drops the variant. Guessing DENY would put
    "stop at zero" on the screen for a variant that keeps selling, and being
    wrong about that is worse than saying nothing.
    """
    return InventoryPolicy(str(value).upper())


def _as_timestamp(value: Any) -> datetime:
    """Shopify sends an offset, as in 2026-01-15T09:30:00-05:00."""
    if not value:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
