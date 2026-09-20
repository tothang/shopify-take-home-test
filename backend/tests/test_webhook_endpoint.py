"""Contract tests for task 3. They fail until the webhook handler is written."""

import asyncio
import base64
import hashlib
import hmac
import json
from decimal import Decimal

from fastapi.testclient import TestClient
from httpx import AsyncClient

from application.schemas import InventoryPolicy
from application.services.event_broker import event_broker
from application.settings import get_settings

WEBHOOK_PATH = "/webhooks/shopify/products-update"
PAYLOAD = {
    "id": 8100000000001,
    "title": "Everyday Cotton T-Shirt",
    "status": "active",
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


def _sign(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()).decode()


def _headers(body: bytes, secret: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Shopify-Topic": "products/update",
        "X-Shopify-Hmac-Sha256": _sign(secret, body),
        "X-Shopify-Shop-Domain": "development-store.myshopify.com",
    }


def test_a_signed_webhook_is_accepted(client: TestClient) -> None:
    body = json.dumps(PAYLOAD).encode("utf-8")
    headers = _headers(body, get_settings().shopify_webhook_secret)

    response = client.post(WEBHOOK_PATH, content=body, headers=headers)

    assert response.status_code in {200, 202, 204}


def test_an_unsigned_webhook_is_rejected(client: TestClient) -> None:
    body = json.dumps(PAYLOAD).encode("utf-8")

    response = client.post(WEBHOOK_PATH, content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 401


def test_a_webhook_signed_with_the_wrong_secret_is_rejected(client: TestClient) -> None:
    body = json.dumps(PAYLOAD).encode("utf-8")

    response = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, "the-wrong-secret"))

    assert response.status_code == 401


async def test_an_accepted_webhook_publishes_a_variant_update(async_client: AsyncClient) -> None:
    """The browser must learn about a price change it did not make itself."""
    body = json.dumps(PAYLOAD).encode("utf-8")

    async with event_broker.subscribe() as queue:
        response = await async_client.post(
            WEBHOOK_PATH,
            content=body,
            headers=_headers(body, get_settings().shopify_webhook_secret),
        )
        assert response.status_code in {200, 202, 204}
        event = await asyncio.wait_for(queue.get(), timeout=2.0)

    assert event.source == "webhook"
    assert event.variant.id == "45100000000001"
    assert event.variant.product_id == "8100000000001"
    assert event.variant.price == Decimal("17.25")
    assert event.variant.inventory_policy is InventoryPolicy.CONTINUE
