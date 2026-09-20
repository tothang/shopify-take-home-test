from typing import Any

import httpx

from application.shopify.errors import ShopifyError


class ShopifyGraphQLClient:
    """Thin transport around the Shopify Admin GraphQL endpoint.

    It owns one connection pool for the lifetime of the process. Call aclose
    during application shutdown.
    """

    def __init__(
        self,
        store_domain: str,
        access_token: str,
        api_version: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not store_domain or not access_token:
            raise ShopifyError(
                "Shopify credentials are missing. "
                "Install the application into a store through /auth/install, "
                "or set SHOPIFY_STORE_DOMAIN and SHOPIFY_ADMIN_ACCESS_TOKEN by hand, "
                "or set USE_MOCK_SHOPIFY=true to run against the in-memory catalog."
            )
        self._endpoint = f"https://{store_domain}/admin/api/{api_version}/graphql.json"
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def execute(self, document: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = await self._client.post(
                self._endpoint,
                json={"query": document, "variables": variables or {}},
            )
        except httpx.HTTPError as error:
            raise ShopifyError(f"Shopify request failed: {error}") from error

        if response.status_code >= 400:
            raise ShopifyError(f"Shopify returned status {response.status_code}: {response.text}")

        payload = response.json()
        if payload.get("errors"):
            raise ShopifyError(f"Shopify returned GraphQL errors: {payload['errors']}")

        data = payload.get("data")
        if data is None:
            raise ShopifyError("Shopify returned a response without a data section.")
        return data

    async def aclose(self) -> None:
        await self._client.aclose()
