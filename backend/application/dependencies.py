from typing import Annotated

from fastapi import Depends, HTTPException, status

from application.services.shop_token_store import shop_token_store
from application.settings import Settings, get_settings
from application.shopify.admin_api_gateway import AdminApiProductGateway
from application.shopify.gateway import ProductGateway
from application.shopify.graphql_client import ShopifyGraphQLClient
from application.shopify.in_memory_gateway import InMemoryProductGateway

_in_memory_gateway = InMemoryProductGateway()
_graphql_clients: dict[tuple[str, str], ShopifyGraphQLClient] = {}


def get_product_gateway() -> ProductGateway:
    """Pick the catalog this request talks to.

    In mock mode every request shares one in-memory catalog. Otherwise the
    access token comes from the shop that installed the application, falling
    back to the one in the environment so that the project can be pointed at a
    store without going through the installation flow first.
    """
    settings = get_settings()
    if settings.use_mock_shopify:
        return _in_memory_gateway

    shop_domain = settings.shopify_store_domain
    access_token = shop_token_store.get(shop_domain) or settings.shopify_admin_access_token
    if not shop_domain or not access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No store is connected. Install the application through "
                "/auth/install?shop=your-store.myshopify.com, or set "
                "USE_MOCK_SHOPIFY=true to use the in-memory catalog."
            ),
        )

    client = _graphql_clients.get((shop_domain, access_token))
    if client is None:
        client = ShopifyGraphQLClient(
            store_domain=shop_domain,
            access_token=access_token,
            api_version=settings.shopify_api_version,
            timeout_seconds=settings.request_timeout_seconds,
        )
        _graphql_clients[(shop_domain, access_token)] = client
    return AdminApiProductGateway(client)


async def close_graphql_clients() -> None:
    for client in _graphql_clients.values():
        await client.aclose()
    _graphql_clients.clear()


ProductGatewayDependency = Annotated[ProductGateway, Depends(get_product_gateway)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
