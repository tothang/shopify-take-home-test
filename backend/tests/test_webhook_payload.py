"""The REST to application mapping, tested without signing a request.

The provided endpoint tests cover one well formed payload. These cover the
shapes a real store produces: identifiers as numbers, a policy in lower case,
a price that must not become a float, missing optional fields, and an entry
that cannot be read at all.
"""

from datetime import UTC, datetime
from decimal import Decimal

from application.schemas import InventoryPolicy
from application.shopify.webhook_payload import (
    DEFAULT_CURRENCY_CODE,
    variants_from_webhook_payload,
)

PAYLOAD = {
    "id": 8100000000001,
    "title": "Everyday Cotton T-Shirt",
    "updated_at": "2026-01-15T09:30:00-05:00",
    "variants": [
        {
            "id": 45100000000001,
            "product_id": 8100000000001,
            "title": "Small / Black",
            "sku": "COTTON-TEE-S-BLACK",
            "price": "17.25",
            "inventory_policy": "continue",
            "inventory_quantity": 12,
            "updated_at": "2026-01-15T09:30:00-05:00",
        }
    ],
}


def test_identifiers_arrive_as_numbers_and_leave_as_strings() -> None:
    """Shopify sends 45100000000001; this API carries "45100000000001"."""
    variant = variants_from_webhook_payload(PAYLOAD)[0]

    assert variant.id == "45100000000001"
    assert variant.product_id == "8100000000001"


def test_the_lower_case_policy_becomes_the_enumeration() -> None:
    variant = variants_from_webhook_payload(PAYLOAD)[0]

    assert variant.inventory_policy is InventoryPolicy.CONTINUE


def test_deny_maps_too() -> None:
    payload = {**PAYLOAD, "variants": [{**PAYLOAD["variants"][0], "inventory_policy": "deny"}]}

    assert variants_from_webhook_payload(payload)[0].inventory_policy is InventoryPolicy.DENY


def test_the_price_stays_exact() -> None:
    variant = variants_from_webhook_payload(PAYLOAD)[0]

    assert variant.price == Decimal("17.25")
    assert not isinstance(variant.price, float)


def test_a_price_that_arrives_as_a_json_number_does_not_become_a_float() -> None:
    """The route parses with parse_float=Decimal, so a number stays exact."""
    payload = {**PAYLOAD, "variants": [{**PAYLOAD["variants"][0], "price": Decimal("17.25")}]}

    assert variants_from_webhook_payload(payload)[0].price == Decimal("17.25")


def test_the_timestamp_keeps_its_offset() -> None:
    variant = variants_from_webhook_payload(PAYLOAD)[0]

    assert variant.updated_at == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)


def test_a_variant_without_a_timestamp_falls_back_to_the_product() -> None:
    entry = {key: value for key, value in PAYLOAD["variants"][0].items() if key != "updated_at"}
    payload = {**PAYLOAD, "variants": [entry]}

    assert variants_from_webhook_payload(payload)[0].updated_at == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)


def test_the_missing_currency_falls_back_to_the_shop_currency() -> None:
    """The REST webhook payload has no currency field at all."""
    variant = variants_from_webhook_payload(PAYLOAD)[0]

    assert variant.currency_code == DEFAULT_CURRENCY_CODE


def test_optional_fields_may_be_absent() -> None:
    payload = {
        "id": 8100000000001,
        "variants": [{"id": 45100000000001, "price": "9.99", "inventory_policy": "deny"}],
    }

    variant = variants_from_webhook_payload(payload)[0]

    assert variant.sku is None
    assert variant.title == ""
    assert variant.inventory_quantity == 0
    assert variant.product_id == "8100000000001"


def test_every_variant_in_the_payload_is_mapped() -> None:
    """A bulk edit changes several variants and arrives as one webhook."""
    first, second = PAYLOAD["variants"][0], {**PAYLOAD["variants"][0], "id": 45100000000002}
    payload = {**PAYLOAD, "variants": [first, second]}

    assert [variant.id for variant in variants_from_webhook_payload(payload)] == [
        "45100000000001",
        "45100000000002",
    ]


def test_an_unreadable_variant_is_skipped_and_the_rest_survive() -> None:
    """One bad entry must not cost us the other changes in the same payload."""
    good = PAYLOAD["variants"][0]
    unknown_policy = {**good, "id": 45100000000002, "inventory_policy": "sometimes"}
    missing_price = {**good, "id": 45100000000003}
    missing_price.pop("price")

    payload = {**PAYLOAD, "variants": [unknown_policy, good, missing_price]}

    assert [variant.id for variant in variants_from_webhook_payload(payload)] == ["45100000000001"]


def test_a_payload_without_variants_maps_to_nothing() -> None:
    """Shopify sends products/update for changes that touch no variant at all."""
    assert variants_from_webhook_payload({"id": 8100000000001}) == []
    assert variants_from_webhook_payload({"id": 8100000000001, "variants": []}) == []
