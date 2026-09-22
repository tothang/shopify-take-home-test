"""The application installation flow.

A merchant installs the application by opening the install endpoint with
their shop domain. The application sends them to Shopify to approve the
access scopes, Shopify sends them back to the callback endpoint with a code,
and the application exchanges that code for a permanent access token.
"""

import hashlib
import hmac
import re
from collections.abc import Mapping
from urllib.parse import urlencode

import httpx

from application.shopify.errors import ShopifyError

AUTHORIZATION_PATH = "/admin/oauth/authorize"
ACCESS_TOKEN_PATH = "/admin/oauth/access_token"

# One DNS label under myshopify.com and nothing else: no scheme, no path, no
# port, no query, no second domain after it. The label starts with a letter or
# a digit and is at most 63 characters, which is the limit for any DNS label.
_SHOP_DOMAIN_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com")


def is_valid_shop_domain(shop_domain: str) -> bool:
    """Return True when this really is a Shopify shop domain.

    The value arrives from anyone who can open a link, and the application
    then sends a client secret to whatever host it names. So this is an allow
    list of one shape, not a search for bad characters.

    fullmatch rather than match with a trailing $: the $ anchor also matches
    before a final newline, so "store.myshopify.com\\n" would slip through.
    """
    return bool(_SHOP_DOMAIN_PATTERN.fullmatch(shop_domain))


def build_authorization_url(
    shop_domain: str,
    api_key: str,
    scopes: str,
    redirect_url: str,
    state: str,
) -> str:
    """Return the Shopify URL the merchant is sent to in order to approve.

    No grant_options[]=per-user, so Shopify issues an offline token: one that
    belongs to the shop rather than to the person who clicked install, and
    that keeps working after they log out. A webhook-driven console needs that.
    """
    query = urlencode(
        {
            "client_id": api_key,
            "scope": scopes,
            "redirect_uri": redirect_url,
            "state": state,
        }
    )
    return f"https://{shop_domain}{AUTHORIZATION_PATH}?{query}"


def verify_callback_signature(secret: str, query_parameters: Mapping[str, str]) -> bool:
    """Return True when the callback really came from Shopify.

    Different from the webhook signature in every detail. Shopify signs the
    query string, not a body: every parameter except hmac itself, sorted by
    name and joined as name=value pairs with &. The digest is hex, not base64.

    Every other parameter is part of the message, so one that an attacker adds
    to the URL, a redirect for example, breaks the signature too.
    """
    provided_digest = query_parameters.get("hmac")
    if not provided_digest:
        return False

    message = "&".join(
        f"{name}={value}" for name, value in sorted(query_parameters.items()) if name != "hmac"
    )
    expected_digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_digest, provided_digest)


async def exchange_code_for_access_token(
    shop_domain: str,
    api_key: str,
    api_secret: str,
    code: str,
    *,
    timeout_seconds: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Trade the temporary code for a permanent Admin API access token.

    Raises ShopifyError when the exchange fails, whatever the reason. The
    transport argument exists for tests, so they can answer for Shopify.
    """
    # The caller has already checked this. This function is the one that sends
    # the client secret to the host, so it checks again rather than trusting it.
    if not is_valid_shop_domain(shop_domain):
        raise ShopifyError("Refused to send credentials to a host that is not a Shopify shop.")

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, transport=transport) as client:
            response = await client.post(
                f"https://{shop_domain}{ACCESS_TOKEN_PATH}",
                json={"client_id": api_key, "client_secret": api_secret, "code": code},
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as error:
        raise ShopifyError(f"The access token request failed: {error}") from error

    # The body is left out of these messages. It is harmless today, but they
    # end up in logs, and so would whatever Shopify decides to echo back.
    if response.status_code >= 400:
        raise ShopifyError(f"Shopify refused the access token request with status {response.status_code}.")

    try:
        body = response.json()
    except ValueError as error:
        raise ShopifyError(
            "Shopify answered the access token request with a body that is not JSON."
        ) from error

    access_token = body.get("access_token") if isinstance(body, dict) else None
    if not isinstance(access_token, str) or not access_token:
        raise ShopifyError("Shopify answered the access token request without an access token.")
    return access_token
