"""AdminApiProductGateway with the GraphQL transport replaced by a test double.

There is no Shopify store in the test suite, so FakeTransport answers the way
the Admin API does: the shapes below are what 2026-07 returns for these
documents. Every request is recorded, so the tests can check what was sent as
well as what was made of the answer.
"""

import json
import logging
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from application.dependencies import get_product_gateway
from application.main import application
from application.schemas import InventoryPolicy
from application.shopify.admin_api_gateway import AdminApiProductGateway
from application.shopify.errors import ShopifyError, VariantNotFoundError, VariantUpdateRejectedError
from application.shopify.graphql_client import ShopifyGraphQLClient
from application.shopify.graphql_documents import (
    PRODUCTS_QUERY,
    SHOP_CURRENCY_QUERY,
    VARIANT_UPDATE_MUTATION,
)


class FakeTransport:
    """Replays canned responses in order and records every request."""

    def __init__(self, *responses: dict[str, Any]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, dict[str, Any] | None]] = []

    async def execute(self, document: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        self.requests.append((document, variables))
        return self._responses.pop(0)

    @property
    def documents(self) -> list[str]:
        return [document for document, _ in self.requests]


def _variant_node(**overrides: Any) -> dict[str, Any]:
    node = {
        "id": "gid://shopify/ProductVariant/45100000000001",
        "title": "Small / Black",
        "sku": "COTTON-TEE-S-BLACK",
        "price": "24.00",
        "inventoryQuantity": 12,
        "inventoryPolicy": "DENY",
        "updatedAt": "2026-01-15T09:00:00Z",
        "product": {"id": "gid://shopify/Product/8100000000001"},
    }
    return {**node, **overrides}


def _products_response(*variant_nodes: dict[str, Any], has_next_page: bool = False) -> dict[str, Any]:
    return {
        "shop": {"currencyCode": "EUR"},
        "products": {
            "nodes": [
                {
                    "id": "gid://shopify/Product/8100000000001",
                    "title": "Everyday Cotton T-Shirt",
                    "status": "ACTIVE",
                    "variants": {
                        "nodes": list(variant_nodes) or [_variant_node()],
                        "pageInfo": {"hasNextPage": has_next_page},
                    },
                }
            ]
        },
    }


def _update_response(*variant_nodes: dict[str, Any], user_errors: list | None = None) -> dict[str, Any]:
    return {
        "productVariantsBulkUpdate": {
            "productVariants": list(variant_nodes) if user_errors is None else None,
            "userErrors": user_errors or [],
        }
    }


CURRENCY_RESPONSE = {"shop": {"currencyCode": "EUR"}}


# Reading.


async def test_products_are_mapped_with_numeric_identifiers() -> None:
    gateway = AdminApiProductGateway(FakeTransport(_products_response()))

    product = (await gateway.list_products())[0]
    variant = product.variants[0]

    assert product.id == "8100000000001"
    assert product.status == "ACTIVE"
    assert variant.id == "45100000000001"
    assert variant.product_id == "8100000000001"
    assert "gid://" not in product.model_dump_json()


async def test_every_field_the_screen_needs_is_read() -> None:
    gateway = AdminApiProductGateway(FakeTransport(_products_response()))

    variant = (await gateway.list_products())[0].variants[0]

    assert variant.title == "Small / Black"
    assert variant.sku == "COTTON-TEE-S-BLACK"
    assert variant.inventory_quantity == 12
    assert variant.inventory_policy is InventoryPolicy.DENY
    assert variant.updated_at.isoformat() == "2026-01-15T09:00:00+00:00"


async def test_the_currency_comes_from_the_shop() -> None:
    gateway = AdminApiProductGateway(FakeTransport(_products_response()))

    variant = (await gateway.list_products())[0].variants[0]

    assert variant.currency_code == "EUR"


async def test_the_price_stays_exact_including_trailing_zeros() -> None:
    gateway = AdminApiProductGateway(FakeTransport(_products_response(_variant_node(price="19.90"))))

    variant = (await gateway.list_products())[0].variants[0]

    assert variant.price == Decimal("19.90")
    assert variant.model_dump(mode="json")["price"] == "19.90"


async def test_the_query_asks_for_the_requested_page() -> None:
    transport = FakeTransport(_products_response())

    await AdminApiProductGateway(transport).list_products(limit=10)

    document, variables = transport.requests[0]
    assert document == PRODUCTS_QUERY
    assert variables is not None and variables["first"] == 10


async def test_untracked_stock_reads_as_zero_and_a_blank_sku_as_none() -> None:
    node = _variant_node(inventoryQuantity=None, sku="")
    gateway = AdminApiProductGateway(FakeTransport(_products_response(node)))

    variant = (await gateway.list_products())[0].variants[0]

    assert variant.inventory_quantity == 0
    assert variant.sku is None


async def test_a_truncated_variant_list_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    gateway = AdminApiProductGateway(FakeTransport(_products_response(has_next_page=True)))

    with caplog.at_level(logging.WARNING):
        await gateway.list_products()

    assert "more variants than one page" in caplog.text


async def test_a_variant_that_cannot_be_read_is_a_shopify_error_not_a_crash() -> None:
    broken = _variant_node()
    del broken["inventoryPolicy"]
    gateway = AdminApiProductGateway(FakeTransport(_products_response(broken)))

    with pytest.raises(ShopifyError):
        await gateway.list_products()


async def test_a_response_without_products_is_a_shopify_error() -> None:
    gateway = AdminApiProductGateway(FakeTransport({"shop": {"currencyCode": "EUR"}}))

    with pytest.raises(ShopifyError):
        await gateway.list_products()


# Writing.


async def test_the_update_sends_global_identifiers_and_the_price_as_text() -> None:
    transport = FakeTransport(_update_response(_variant_node(price="18.50")), CURRENCY_RESPONSE)

    await AdminApiProductGateway(transport).update_variant(
        "8100000000001", "45100000000001", price=Decimal("18.50"), inventory_policy=InventoryPolicy.CONTINUE
    )

    document, variables = transport.requests[0]
    assert document == VARIANT_UPDATE_MUTATION
    assert variables == {
        "productId": "gid://shopify/Product/8100000000001",
        "variants": [
            {
                "id": "gid://shopify/ProductVariant/45100000000001",
                "price": "18.50",
                "inventoryPolicy": "CONTINUE",
            }
        ],
    }


async def test_changing_only_the_price_does_not_send_a_policy() -> None:
    """The README rule, at the boundary: a field left out stays as Shopify has it."""
    transport = FakeTransport(_update_response(_variant_node()), CURRENCY_RESPONSE)

    await AdminApiProductGateway(transport).update_variant(
        "8100000000001", "45100000000001", price=Decimal("18.50")
    )

    sent = transport.requests[0][1]["variants"][0]
    assert "inventoryPolicy" not in sent
    assert sent["price"] == "18.50"


async def test_changing_only_the_policy_does_not_send_a_price() -> None:
    transport = FakeTransport(_update_response(_variant_node()), CURRENCY_RESPONSE)

    await AdminApiProductGateway(transport).update_variant(
        "8100000000001", "45100000000001", inventory_policy=InventoryPolicy.CONTINUE
    )

    assert "price" not in transport.requests[0][1]["variants"][0]


async def test_the_update_returns_what_shopify_stored() -> None:
    stored = _variant_node(price="18.50", inventoryPolicy="CONTINUE", updatedAt="2026-01-15T10:00:00Z")
    gateway = AdminApiProductGateway(FakeTransport(_update_response(stored), CURRENCY_RESPONSE))

    variant = await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("18.50"))

    assert variant.price == Decimal("18.50")
    assert variant.inventory_policy is InventoryPolicy.CONTINUE
    assert variant.currency_code == "EUR"


async def test_the_shop_currency_is_asked_for_once() -> None:
    transport = FakeTransport(
        _update_response(_variant_node()),
        CURRENCY_RESPONSE,
        _update_response(_variant_node()),
    )
    gateway = AdminApiProductGateway(transport)

    await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("18.50"))
    await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("17.50"))

    assert transport.documents.count(SHOP_CURRENCY_QUERY) == 1


async def test_an_update_after_a_read_does_not_ask_for_the_currency() -> None:
    transport = FakeTransport(_products_response(), _update_response(_variant_node()))
    gateway = AdminApiProductGateway(transport)

    await gateway.list_products()
    await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("18.50"))

    assert SHOP_CURRENCY_QUERY not in transport.documents


@pytest.mark.parametrize(
    "code", ["PRODUCT_VARIANT_DOES_NOT_EXIST", "PRODUCT_DOES_NOT_EXIST", "MUST_BE_FOR_THIS_PRODUCT"]
)
async def test_user_errors_that_mean_not_found_raise_variant_not_found(code: str) -> None:
    errors = [{"field": ["variants", "0", "id"], "message": "Not found", "code": code}]
    gateway = AdminApiProductGateway(FakeTransport(_update_response(user_errors=errors)))

    with pytest.raises(VariantNotFoundError):
        await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("18.50"))


async def test_any_other_user_error_is_a_rejected_update() -> None:
    """A 200 with userErrors has failed, whatever the transport said."""
    errors = [{"field": ["variants", "0", "price"], "message": "Price is too high", "code": "INVALID_INPUT"}]
    gateway = AdminApiProductGateway(FakeTransport(_update_response(user_errors=errors)))

    with pytest.raises(VariantUpdateRejectedError, match="Price is too high"):
        await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("18.50"))


async def test_an_identifier_that_is_not_numeric_is_not_found_without_asking_shopify() -> None:
    transport = FakeTransport()

    with pytest.raises(VariantNotFoundError):
        await AdminApiProductGateway(transport).update_variant(
            "8100000000001", "not-a-number", price=Decimal("1")
        )

    assert transport.requests == []


async def test_an_answer_without_the_variant_is_a_shopify_error() -> None:
    other = _variant_node(id="gid://shopify/ProductVariant/45100000000002")
    gateway = AdminApiProductGateway(FakeTransport(_update_response(other)))

    with pytest.raises(ShopifyError):
        await gateway.update_variant("8100000000001", "45100000000001", price=Decimal("18.50"))


# Through the router, so the status codes are checked with the real gateway.


@pytest.fixture
def gateway_client() -> Any:
    def build(*responses: dict[str, Any]) -> TestClient:
        gateway = AdminApiProductGateway(FakeTransport(*responses))
        application.dependency_overrides[get_product_gateway] = lambda: gateway
        return TestClient(application)

    yield build
    application.dependency_overrides.clear()


def test_a_refused_update_reaches_the_browser_as_a_bad_gateway(gateway_client: Any) -> None:
    errors = [{"field": ["price"], "message": "Price is too high", "code": "INVALID_INPUT"}]
    client = gateway_client(_update_response(user_errors=errors))

    response = client.patch("/api/products/8100000000001/variants/45100000000001", json={"price": "18.50"})

    assert response.status_code == 502


def test_a_variant_shopify_does_not_know_reaches_the_browser_as_not_found(gateway_client: Any) -> None:
    errors = [{"field": ["id"], "message": "Not found", "code": "PRODUCT_VARIANT_DOES_NOT_EXIST"}]
    client = gateway_client(_update_response(user_errors=errors))

    response = client.patch("/api/products/8100000000001/variants/45100000000009", json={"price": "18.50"})

    assert response.status_code == 404


def test_the_catalog_reaches_the_browser_with_the_contract_shape(gateway_client: Any) -> None:
    client = gateway_client(_products_response())

    body = client.get("/api/products").json()

    assert body[0]["variants"][0]["price"] == "24.00"
    assert body[0]["variants"][0]["currency_code"] == "EUR"
    assert body[0]["variants"][0]["id"] == "45100000000001"


# The provided transport, where the gateway work touched it.


def _client_answering(response: httpx.Response) -> ShopifyGraphQLClient:
    client = ShopifyGraphQLClient("test-store.myshopify.com", "token", "2026-07")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response))
    return client


async def test_a_body_that_is_not_json_is_a_shopify_error() -> None:
    client = _client_answering(httpx.Response(200, text="<html>Down for maintenance</html>"))

    with pytest.raises(ShopifyError, match="not JSON"):
        await client.execute("{ shop { name } }")


async def test_numbers_in_a_response_are_never_floats() -> None:
    client = _client_answering(httpx.Response(200, content=json.dumps({"data": {"amount": 19.9}}).encode()))

    data = await client.execute("{ shop { name } }")

    assert data["amount"] == Decimal("19.9")
    assert isinstance(data["amount"], Decimal)


async def test_graphql_errors_with_a_200_are_a_shopify_error() -> None:
    """Throttling arrives like this: status 200, and an errors list."""
    body = {"errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]}
    client = _client_answering(httpx.Response(200, json=body))

    with pytest.raises(ShopifyError, match="Throttled"):
        await client.execute("{ shop { name } }")
