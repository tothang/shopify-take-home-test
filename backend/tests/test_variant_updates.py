"""Behaviour around tasks 1 and 2 that the provided suite does not pin down.

The contract tests check the happy path and the status codes. These check the
rules the README states in prose: a field left out stays as it was, money is
limited to two decimal places, and a store that refuses or cannot be reached
is reported as a bad gateway rather than as our own failure. The last test
covers the event the update endpoint publishes, which is what keeps a second
browser tab correct.
"""

import asyncio
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from application.dependencies import get_product_gateway
from application.main import application
from application.schemas import InventoryPolicy, ProductVariant, VariantUpdatedEvent
from application.services.event_broker import EventBroker, event_broker
from application.shopify.errors import ShopifyError, VariantUpdateRejectedError
from application.shopify.in_memory_gateway import InMemoryProductGateway

PRODUCT_ID = "8100000000001"
VARIANT_ID = "45100000000001"
VARIANT_PATH = f"/api/products/{PRODUCT_ID}/variants/{VARIANT_ID}"


class FailingGateway:
    """A catalog that always fails, so the router's error mapping is visible.

    Standing in for a store that is refusing changes or is unreachable. It
    satisfies ProductGateway structurally, which is the point of the port
    being a Protocol rather than a base class.
    """

    def __init__(self, error: ShopifyError) -> None:
        self._error = error

    async def list_products(self, limit: int = 25) -> list:
        raise self._error

    async def update_variant(self, *arguments: object, **keywords: object) -> ProductVariant:
        raise self._error


@pytest.fixture
def failing_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    gateway = FailingGateway(request.param)
    application.dependency_overrides[get_product_gateway] = lambda: gateway
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _read_variant(client: TestClient) -> dict:
    products = client.get("/api/products").json()
    return next(variant for variant in products[0]["variants"] if variant["id"] == VARIANT_ID)


def test_changing_only_the_price_leaves_the_inventory_policy_alone(client: TestClient) -> None:
    """The README calls this out: sending only a price must not reset the policy."""
    before = _read_variant(client)
    assert before["inventory_policy"] == "DENY"

    response = client.patch(VARIANT_PATH, json={"price": "18.50"})

    assert response.status_code == 200
    assert response.json()["inventory_policy"] == "DENY"
    assert _read_variant(client)["inventory_policy"] == "DENY"


def test_changing_only_the_policy_leaves_the_price_alone(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"inventory_policy": "CONTINUE"})

    assert response.status_code == 200
    assert response.json()["price"] == "24.00"
    assert _read_variant(client)["price"] == "24.00"


def test_a_price_with_more_than_two_decimal_places_is_rejected(client: TestClient) -> None:
    """Money has two decimal places. A third is a mistake, not something to round."""
    response = client.patch(VARIANT_PATH, json={"price": "18.555"})

    assert response.status_code == 422


def test_a_price_of_exactly_zero_is_rejected(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"price": "0.00"})

    assert response.status_code == 422


def test_an_unknown_product_is_reported_as_not_found(client: TestClient) -> None:
    response = client.patch("/api/products/404404404/variants/404404404", json={"price": "18.50"})

    assert response.status_code == 404


@pytest.mark.parametrize(
    "failing_client",
    [VariantUpdateRejectedError("Shopify refused the change.")],
    indirect=True,
)
def test_a_refused_change_is_reported_as_a_bad_gateway(failing_client: TestClient) -> None:
    """Shopify answering with userErrors is an upstream failure, not a 500."""
    response = failing_client.patch(VARIANT_PATH, json={"price": "18.50"})

    assert response.status_code == 502
    assert "could not be saved" in response.json()["detail"]


@pytest.mark.parametrize(
    "failing_client",
    [ShopifyError("Shopify request failed: connection refused")],
    indirect=True,
)
def test_an_unreachable_store_is_reported_as_a_bad_gateway(failing_client: TestClient) -> None:
    response = failing_client.patch(VARIANT_PATH, json={"price": "18.50"})

    assert response.status_code == 502


@pytest.mark.parametrize(
    "failing_client",
    [ShopifyError("Shopify request failed: connection refused")],
    indirect=True,
)
def test_an_unreachable_catalog_does_not_reach_the_browser_as_a_crash(
    failing_client: TestClient,
) -> None:
    """Task 1: the browser gets something it can act on, not a stack trace."""
    response = failing_client.get("/api/products")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Traceback" not in detail
    assert "connection refused" not in detail


async def test_a_successful_update_is_broadcast_to_every_tab() -> None:
    """A second browser tab only learns about this edit if the endpoint says so.

    In mock mode nothing else will ever tell it: there is no Shopify behind
    this to send a webhook back.
    """
    gateway = InMemoryProductGateway()
    application.dependency_overrides[get_product_gateway] = lambda: gateway
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        async with event_broker.subscribe() as queue:
            response = await test_client.patch(VARIANT_PATH, json={"price": "18.50"})
            assert response.status_code == 200
            event = await asyncio.wait_for(queue.get(), timeout=2.0)

    application.dependency_overrides.clear()

    assert event.source == "api"
    assert event.variant.id == VARIANT_ID
    assert event.variant.price == Decimal("18.50")
    assert event.variant.inventory_policy is InventoryPolicy.DENY


async def test_a_subscriber_that_falls_behind_is_dropped_and_can_tell() -> None:
    """The event stream ends a dropped subscriber, so the browser reconnects."""
    broker = EventBroker(queue_size=1)
    variant = InMemoryProductGateway()._products[PRODUCT_ID].variants[0]

    async with broker.subscribe() as queue:
        assert broker.is_subscribed(queue)
        await broker.publish(VariantUpdatedEvent(source="api", variant=variant))
        await broker.publish(VariantUpdatedEvent(source="api", variant=variant))

        assert not broker.is_subscribed(queue)
