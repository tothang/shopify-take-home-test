from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from application.dependencies import get_product_gateway
from application.main import application
from application.settings import get_settings
from application.shopify.in_memory_gateway import InMemoryProductGateway

# Every setting is fixed here so the suite gives the same result whatever the
# developer put in their own .env. Environment variables take priority over
# the file, so setting all of them leaves nothing for the file to decide.
TEST_ENVIRONMENT = {
    "SHOPIFY_STORE_DOMAIN": "test-store.myshopify.com",
    "SHOPIFY_ADMIN_ACCESS_TOKEN": "",
    "SHOPIFY_API_VERSION": "2026-07",
    "SHOPIFY_WEBHOOK_SECRET": "test-webhook-secret",
    "SHOPIFY_API_KEY": "test-api-key",
    "SHOPIFY_API_SECRET": "test-api-secret",
    "SHOPIFY_APPLICATION_URL": "http://localhost:8000",
    "SHOPIFY_SCOPES": "read_products,write_products,read_inventory",
    "USE_MOCK_SHOPIFY": "true",
    "ALLOWED_ORIGINS": "http://localhost:5173",
    "REQUEST_TIMEOUT_SECONDS": "10",
}


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name, value in TEST_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def gateway() -> InMemoryProductGateway:
    return InMemoryProductGateway()


@pytest.fixture
def client(gateway: InMemoryProductGateway) -> Iterator[TestClient]:
    application.dependency_overrides[get_product_gateway] = lambda: gateway
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture
async def async_client(gateway: InMemoryProductGateway) -> AsyncIterator[AsyncClient]:
    application.dependency_overrides[get_product_gateway] = lambda: gateway
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    application.dependency_overrides.clear()
