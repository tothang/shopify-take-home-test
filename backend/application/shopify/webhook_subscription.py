from application.shopify.errors import ShopifyError
from application.shopify.graphql_client import ShopifyGraphQLClient
from application.shopify.graphql_documents import WEBHOOK_SUBSCRIPTION_CREATE_MUTATION

PRODUCTS_UPDATE_TOPIC = "PRODUCTS_UPDATE"


async def register_products_update_webhook(client: ShopifyGraphQLClient, uri: str) -> str:
    """Ask Shopify to send products/update to uri, and return the subscription id.

    - Raises ShopifyError on userErrors, which arrive with a 200.
    - Example: Shopify cannot reach the address, such as http://localhost.
    """
    data = await client.execute(
        WEBHOOK_SUBSCRIPTION_CREATE_MUTATION,
        {"topic": PRODUCTS_UPDATE_TOPIC, "webhookSubscription": {"uri": uri}},
    )
    result = data.get("webhookSubscriptionCreate") or {}

    user_errors = result.get("userErrors") or []
    if user_errors:
        messages = "; ".join(error.get("message", "unknown error") for error in user_errors)
        raise ShopifyError(f"Shopify refused the webhook subscription: {messages}")

    subscription = result.get("webhookSubscription") or {}
    if not subscription.get("id"):
        raise ShopifyError("Shopify answered the webhook subscription without an identifier.")
    return subscription["id"]
