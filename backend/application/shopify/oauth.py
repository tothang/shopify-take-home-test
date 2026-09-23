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

# Exactly one DNS label (max 63 chars) followed by .myshopify.com, nothing else.
_SHOP_DOMAIN_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com")


def is_valid_shop_domain(shop_domain: str) -> bool:
    """Return True when this really is a Shopify shop domain.

    - We send the client secret to this host, so only one exact shape is allowed.
    - fullmatch, because a trailing $ would also accept a final newline.
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

    - No grant_options[]=per-user, so Shopify issues an offline token.
    - It belongs to the shop and keeps working after the merchant logs out.
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

    Unlike webhooks:
    - Shopify signs the query string, not a body.
    - Message: all parameters except hmac, sorted, joined as name=value with &.
    - The digest is hex, not base64.
    - Any parameter added to the URL breaks the signature.
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

    - Raises ShopifyError on any failure.
    - transport is for tests.
    """
    # Checked again here because this is where the client secret gets sent.
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

    # The response body is kept out of error messages because they get logged.
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
