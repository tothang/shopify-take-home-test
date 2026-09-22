"""The webhook path under inputs that are signed but not what we expect.

A signed request comes from Shopify, so answering it with a 500 only makes
Shopify send it again, and a payload we could not read will fail the same way
every time. These pin down that such a request is answered 204 and publishes
nothing, that a good one publishes exactly what it should, that the signature
check refuses an unconfigured secret, and that one slow browser cannot make
publishing fail.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from application.schemas import InventoryPolicy, ProductVariant, VariantUpdatedEvent
from application.services.event_broker import EventBroker, event_broker
from application.settings import get_settings
from application.shopify.webhook_signature import verify_webhook_signature

WEBHOOK_PATH = "/webhooks/shopify/products-update"


def _sign(body: bytes, secret: str | None = None) -> str:
    key = (get_settings().shopify_webhook_secret if secret is None else secret).encode("utf-8")
    return base64.b64encode(hmac.new(key, body, hashlib.sha256).digest()).decode()


def _headers(body: bytes, secret: str | None = None) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Shopify-Topic": "products/update",
        "X-Shopify-Hmac-Sha256": _sign(body, secret),
        "X-Shopify-Shop-Domain": "development-store.myshopify.com",
    }


def _variant(variant_id: int, policy: str) -> dict[str, Any]:
    return {
        "id": variant_id,
        "product_id": 8100000000001,
        "title": "Small / Black",
        "price": "17.25",
        "inventory_policy": policy,
        "inventory_quantity": 12,
        "updated_at": "2026-01-15T09:30:00-05:00",
    }


async def _post_and_collect(client: AsyncClient, body: bytes) -> tuple[int, list[VariantUpdatedEvent]]:
    """Post a signed body and return the status and every event it published.

    Publishing happens before the route answers, so once the response is back
    the queue holds everything this request will ever publish.
    """
    async with event_broker.subscribe() as queue:
        response = await client.post(WEBHOOK_PATH, content=body, headers=_headers(body))
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
    return response.status_code, events


# Signed, but not something we can read: answered 204, nothing published.


async def test_signed_json_without_a_variants_key_answers_204_and_publishes_nothing(
    async_client: AsyncClient,
) -> None:
    status, events = await _post_and_collect(async_client, json.dumps({"id": 8100000000001}).encode())

    assert status == 204
    assert events == []


async def test_a_signed_body_that_is_not_json_answers_204_and_publishes_nothing(
    async_client: AsyncClient,
) -> None:
    status, events = await _post_and_collect(async_client, b"this is not json {")

    assert status == 204
    assert events == []


@pytest.mark.parametrize(
    "payload",
    [
        [1, 2, 3],
        5,
        "a string",
        None,
        {"id": 8100000000001, "variants": {"not": "a list"}},
        {"id": 8100000000001, "variants": "not a list"},
    ],
    ids=["list", "number", "string", "null", "variants-object", "variants-string"],
)
async def test_a_signed_payload_of_the_wrong_shape_answers_204_and_publishes_nothing(
    async_client: AsyncClient, payload: Any
) -> None:
    """Each of these used to raise past the route and come back as a 500."""
    status, events = await _post_and_collect(async_client, json.dumps(payload).encode())

    assert status == 204
    assert events == []


async def test_a_malformed_variant_entry_is_skipped_and_the_others_still_publish(
    async_client: AsyncClient,
) -> None:
    payload = {"id": 8100000000001, "variants": ["not an object", _variant(45100000000001, "deny")]}

    status, events = await _post_and_collect(async_client, json.dumps(payload).encode())

    assert status == 204
    assert [event.variant.id for event in events] == ["45100000000001"]


# Signed and well formed: one event per variant.


async def test_a_well_formed_payload_publishes_one_event_per_variant(async_client: AsyncClient) -> None:
    payload = {
        "id": 8100000000001,
        "variants": [_variant(45100000000001, "continue"), _variant(45100000000002, "deny")],
    }

    status, events = await _post_and_collect(async_client, json.dumps(payload).encode())

    assert status == 204
    assert [event.source for event in events] == ["webhook", "webhook"]
    assert [event.variant.id for event in events] == ["45100000000001", "45100000000002"]
    assert [event.variant.inventory_policy for event in events] == [
        InventoryPolicy.CONTINUE,
        InventoryPolicy.DENY,
    ]


# The signature check.

BODY = b'{"id":8100000000001,"variants":[{"id":45100000000001,"price":"19.99"}]}'
SECRET = "test-webhook-secret"


def test_a_correct_signature_is_accepted() -> None:
    """So the refusals below are refusals of something, not of everything."""
    assert verify_webhook_signature(SECRET, BODY, _sign(BODY, SECRET)) is True


def test_an_empty_secret_is_refused_even_with_a_signature_made_from_it() -> None:
    """Anyone can compute an HMAC with an empty key. It proves nothing."""
    assert verify_webhook_signature("", BODY, _sign(BODY, "")) is False


@pytest.mark.parametrize("header", [None, ""], ids=["absent", "empty"])
def test_a_missing_header_is_refused(header: str | None) -> None:
    assert verify_webhook_signature(SECRET, BODY, header) is False


@pytest.mark.parametrize(
    "header", ["not base64 at all", "%%%%", "abc", "é"], ids=["words", "symbols", "short", "non-ascii"]
)
def test_a_header_that_is_not_base64_is_refused(header: str) -> None:
    assert verify_webhook_signature(SECRET, BODY, header) is False


def test_a_signature_over_a_different_body_is_refused() -> None:
    assert verify_webhook_signature(SECRET, BODY, _sign(b'{"id":1}', SECRET)) is False


def test_the_endpoint_refuses_everything_when_no_secret_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A backend started without SHOPIFY_WEBHOOK_SECRET accepts nothing."""
    monkeypatch.setenv("SHOPIFY_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    body = json.dumps({"id": 8100000000001, "variants": []}).encode()

    response = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, secret=""))

    assert response.status_code == 401


# Publishing.


def _event() -> VariantUpdatedEvent:
    return VariantUpdatedEvent(
        source="webhook",
        variant=ProductVariant.model_validate(
            {
                "id": "45100000000001",
                "product_id": "8100000000001",
                "title": "Small / Black",
                "price": "17.25",
                "currency_code": "USD",
                "inventory_quantity": 12,
                "inventory_policy": "DENY",
                "updated_at": "2026-01-15T09:30:00Z",
            }
        ),
    )


async def test_a_full_subscriber_cannot_make_publishing_fail(caplog: pytest.LogCaptureFixture) -> None:
    broker = EventBroker(queue_size=1)

    async with broker.subscribe() as slow, broker.subscribe() as healthy:
        await broker.publish(_event())
        healthy.get_nowait()

        with caplog.at_level(logging.WARNING):
            await broker.publish(_event())

        assert healthy.get_nowait().variant.id == "45100000000001"
        assert not broker.is_subscribed(slow)
        assert broker.is_subscribed(healthy)
    assert "fell behind" in caplog.text


async def test_publishing_with_no_subscribers_does_nothing() -> None:
    await EventBroker().publish(_event())
    await asyncio.sleep(0)
