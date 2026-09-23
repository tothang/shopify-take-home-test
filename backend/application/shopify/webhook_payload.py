"""Turning the REST shaped products/update payload into application models.

- Webhooks use the REST shape (numeric IDs, lowercase policies), unlike the
  rest of the integration, which uses GraphQL.
- Kept separate from the route so it can be tested without signing requests.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from application.schemas import InventoryPolicy, ProductVariant

logger = logging.getLogger(__name__)

# The webhook payload has no currency.
# - Several shops: cache each shop's currency.
# - Here: one shop, priced in dollars.
DEFAULT_CURRENCY_CODE = "USD"


def variants_from_webhook_payload(payload: Any) -> list[ProductVariant]:
    """Map every variant in a products/update payload.

    - A variant that cannot be mapped is logged and skipped.
    - A payload with the wrong shape raises TypeError.
    - Only raises ValueError, KeyError and TypeError, which the route catches.
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
    """Webhook IDs are numbers; the application uses strings."""
    return "" if value is None else str(value)


def _as_money(value: Any) -> Decimal:
    """Parse via str so the price never becomes a float."""
    return Decimal(str(value))


def _as_inventory_policy(value: Any) -> InventoryPolicy:
    """Map "continue" to InventoryPolicy.CONTINUE.

    - An unknown value raises, and the variant is skipped.
    - Guessing DENY could show "stop at zero" for a variant that keeps selling.
    """
    return InventoryPolicy(str(value).upper())


def _as_timestamp(value: Any) -> datetime:
    """Parse e.g. 2026-01-15T09:30:00-05:00. Assume UTC if no offset."""
    if not value:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
