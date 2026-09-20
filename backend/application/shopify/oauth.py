"""The application installation flow.

Task 4 asks you to implement every function in this file. A merchant installs
the application by opening the install endpoint with their shop domain. The
application sends them to Shopify to approve the access scopes, Shopify sends
them back to the callback endpoint with a code, and the application exchanges
that code for a permanent access token.

The tests in tests/test_oauth.py define the expected behavior.
"""

from collections.abc import Mapping

AUTHORIZATION_PATH = "/admin/oauth/authorize"
ACCESS_TOKEN_PATH = "/admin/oauth/access_token"


def is_valid_shop_domain(shop_domain: str) -> bool:
    """Return True when this really is a Shopify shop domain.

    Task 4: the shop domain arrives as a query parameter, from anyone who can
    open a link. Everything after it uses that value to build a URL the
    application then calls. Decide what a shop domain is allowed to look like
    and reject everything else.
    """
    raise NotImplementedError("Task 4: validate the shop domain.")


def build_authorization_url(
    shop_domain: str,
    api_key: str,
    scopes: str,
    redirect_url: str,
    state: str,
) -> str:
    """Return the Shopify URL the merchant is sent to in order to approve.

    Task 4: the parameters Shopify expects are documented under the
    authorization code grant. The state value comes back untouched in the
    callback, which is the point of it.
    """
    raise NotImplementedError("Task 4: build the authorization URL.")


def verify_callback_signature(secret: str, query_parameters: Mapping[str, str]) -> bool:
    """Return True when the callback really came from Shopify.

    Task 4: this signature is not the same as the webhook one. Read the
    documentation rather than reusing the webhook code, and note what has to
    happen to the parameters before they are signed.
    """
    raise NotImplementedError("Task 4: verify the callback signature.")


async def exchange_code_for_access_token(
    shop_domain: str,
    api_key: str,
    api_secret: str,
    code: str,
) -> str:
    """Trade the temporary code for a permanent Admin API access token.

    Task 4: one request to the shop. Return the token itself, and raise
    ShopifyError when the exchange fails.
    """
    raise NotImplementedError("Task 4: exchange the code for an access token.")
