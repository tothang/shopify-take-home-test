"""The installation flow end to end, with Shopify's side replaced.

The provided tests check the pieces: the shop domain, the authorization URL,
the callback signature. These check how they are put together: that the state
really binds the callback to the browser that started it, that a callback
which fails any check never reaches the token exchange, and that a failed
webhook registration does not undo an installation.
"""

import hashlib
import hmac
import json
from collections.abc import Iterator
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from application.routers import authentication
from application.services.shop_token_store import shop_token_store
from application.settings import get_settings
from application.shopify.errors import ShopifyError
from application.shopify.oauth import exchange_code_for_access_token, is_valid_shop_domain
from application.shopify.webhook_subscription import register_products_update_webhook

SHOP = "test-store.myshopify.com"


class FakeShopify:
    """Stands in for the two calls the callback makes to Shopify."""

    def __init__(self) -> None:
        self.exchanged_codes: list[str] = []
        self.registered_uris: list[str] = []
        self.exchange_error: ShopifyError | None = None
        self.registration_error: ShopifyError | None = None

    async def exchange(self, *, shop_domain: str, code: str, **_: object) -> str:
        self.exchanged_codes.append(code)
        if self.exchange_error is not None:
            raise self.exchange_error
        return "shpat_issued_token"

    async def register(self, client: object, uri: str) -> str:
        self.registered_uris.append(uri)
        if self.registration_error is not None:
            raise self.registration_error
        return "gid://shopify/WebhookSubscription/1"


@pytest.fixture
def shopify(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeShopify]:
    fake = FakeShopify()
    monkeypatch.setattr(authentication, "exchange_code_for_access_token", fake.exchange)
    monkeypatch.setattr(authentication, "register_products_update_webhook", fake.register)
    yield fake
    shop_token_store.forget(SHOP)


def _start_installation(client: TestClient) -> str:
    """Open the install link and return the state Shopify would hand back."""
    response = client.get("/auth/install", params={"shop": SHOP}, follow_redirects=False)
    assert response.status_code == 302
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def _signed_callback(state: str, **overrides: str) -> dict[str, str]:
    parameters = {"code": "the-code", "shop": SHOP, "state": state, "timestamp": "1770000000", **overrides}
    message = "&".join(f"{name}={value}" for name, value in sorted(parameters.items()))
    secret = get_settings().shopify_api_secret.encode("utf-8")
    parameters["hmac"] = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
    return parameters


def test_a_completed_installation_saves_the_token_and_returns_to_the_console(
    client: TestClient, shopify: FakeShopify
) -> None:
    state = _start_installation(client)

    response = client.get("/auth/callback", params=_signed_callback(state), follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == get_settings().frontend_url
    assert shop_token_store.get(SHOP) == "shpat_issued_token"
    assert shopify.exchanged_codes == ["the-code"]


def test_the_state_cookie_is_cleared_once_used(client: TestClient, shopify: FakeShopify) -> None:
    """A state is good for one installation. Replaying the callback must fail."""
    state = _start_installation(client)
    callback = _signed_callback(state)
    client.get("/auth/callback", params=callback, follow_redirects=False)

    replay = client.get("/auth/callback", params=callback, follow_redirects=False)

    assert replay.status_code == 403
    assert shopify.exchanged_codes == ["the-code"]


def test_the_install_link_sets_a_state_cookie_that_matches_the_url(client: TestClient) -> None:
    response = client.get("/auth/install", params={"shop": SHOP}, follow_redirects=False)

    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    cookie = SimpleCookie(response.headers["set-cookie"])[authentication.STATE_COOKIE_NAME]
    assert cookie.value == state
    assert cookie["httponly"]
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/auth"


def test_every_install_gets_a_new_state(client: TestClient) -> None:
    assert _start_installation(client) != _start_installation(client)


def test_a_state_that_does_not_match_never_reaches_the_token_exchange(
    client: TestClient, shopify: FakeShopify
) -> None:
    _start_installation(client)

    # Correctly signed by Shopify, but carrying some other installation's state.
    response = client.get(
        "/auth/callback", params=_signed_callback("a-state-from-elsewhere"), follow_redirects=False
    )

    assert response.status_code == 403
    assert shopify.exchanged_codes == []
    assert shop_token_store.get(SHOP) is None


def test_a_callback_in_a_browser_that_did_not_start_the_installation_is_refused(
    client: TestClient, shopify: FakeShopify
) -> None:
    """The attack the state exists for: someone else's installation, finished by the merchant."""
    state = _start_installation(client)
    client.cookies.clear()

    response = client.get("/auth/callback", params=_signed_callback(state), follow_redirects=False)

    assert response.status_code == 403
    assert shopify.exchanged_codes == []


def test_a_badly_signed_callback_never_reaches_the_token_exchange(
    client: TestClient, shopify: FakeShopify
) -> None:
    state = _start_installation(client)
    parameters = _signed_callback(state)
    parameters["code"] = "a-code-swapped-in-afterwards"

    response = client.get("/auth/callback", params=parameters, follow_redirects=False)

    assert response.status_code == 401
    assert shopify.exchanged_codes == []


def test_a_repeated_parameter_is_refused(client: TestClient, shopify: FakeShopify) -> None:
    state = _start_installation(client)
    parameters = list(_signed_callback(state).items()) + [("shop", "other-store.myshopify.com")]

    response = client.get("/auth/callback", params=parameters, follow_redirects=False)

    assert response.status_code == 400
    assert shopify.exchanged_codes == []


def test_a_failed_token_exchange_stores_nothing(client: TestClient, shopify: FakeShopify) -> None:
    shopify.exchange_error = ShopifyError("Shopify refused the access token request with status 400.")
    state = _start_installation(client)

    response = client.get("/auth/callback", params=_signed_callback(state), follow_redirects=False)

    assert response.status_code == 502
    assert "Start the installation again" in response.json()["detail"]
    assert shop_token_store.get(SHOP) is None
    assert shopify.registered_uris == []


def test_a_failed_webhook_registration_does_not_break_the_installation(
    client: TestClient, shopify: FakeShopify
) -> None:
    """With the application on localhost, this is what always happens."""
    shopify.registration_error = ShopifyError("Shopify refused the webhook subscription: Address is invalid")
    state = _start_installation(client)

    response = client.get("/auth/callback", params=_signed_callback(state), follow_redirects=False)

    assert response.status_code == 303
    assert shop_token_store.get(SHOP) == "shpat_issued_token"


def test_the_webhook_points_at_the_application(client: TestClient, shopify: FakeShopify) -> None:
    state = _start_installation(client)

    client.get("/auth/callback", params=_signed_callback(state), follow_redirects=False)

    assert shopify.registered_uris == ["http://localhost:8000/webhooks/shopify/products-update"]


def test_a_shop_domain_in_capitals_is_accepted(client: TestClient) -> None:
    response = client.get(
        "/auth/install", params={"shop": "Test-Store.MyShopify.com"}, follow_redirects=False
    )

    assert response.status_code == 302
    assert urlparse(response.headers["location"]).netloc == SHOP


def test_install_without_credentials_says_so(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_API_KEY", "")
    get_settings.cache_clear()

    response = client.get("/auth/install", params={"shop": SHOP}, follow_redirects=False)

    assert response.status_code == 503


def test_a_trailing_newline_is_not_a_shop_domain() -> None:
    """A regular expression anchored with $ would have let this through."""
    assert is_valid_shop_domain(f"{SHOP}\n") is False


# The token exchange itself, with Shopify answering through a mock transport.


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def test_the_exchange_posts_the_code_and_returns_the_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "shpat_real", "scope": "read_products"})

    token = await exchange_code_for_access_token(
        SHOP, "the-key", "the-secret", "the-code", transport=_transport(handler)
    )

    assert token == "shpat_real"
    assert str(seen[0].url) == f"https://{SHOP}/admin/oauth/access_token"
    assert json.loads(seen[0].content) == {
        "client_id": "the-key",
        "client_secret": "the-secret",
        "code": "the-code",
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": "invalid_request"}),
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(200, text="<html>maintenance</html>"),
        httpx.Response(200, json={"scope": "read_products"}),
        httpx.Response(200, json=["not", "an", "object"]),
    ],
    ids=["refused", "server-error", "not-json", "no-token", "wrong-shape"],
)
async def test_a_failed_exchange_raises_shopify_error(response: httpx.Response) -> None:
    with pytest.raises(ShopifyError):
        await exchange_code_for_access_token(
            SHOP, "the-key", "the-secret", "the-code", transport=_transport(lambda _: response)
        )


async def test_an_unreachable_shop_raises_shopify_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ShopifyError):
        await exchange_code_for_access_token(
            SHOP, "the-key", "the-secret", "the-code", transport=_transport(handler)
        )


async def test_the_secret_is_never_sent_to_a_host_that_is_not_shopify() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "stolen"})

    with pytest.raises(ShopifyError):
        await exchange_code_for_access_token(
            "attacker.example.com", "the-key", "the-secret", "the-code", transport=_transport(handler)
        )
    assert seen == []


# The webhook registration, with the GraphQL transport replaced.


class FakeGraphQLClient:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.variables: dict | None = None

    async def execute(self, document: str, variables: dict | None = None) -> dict:
        self.variables = variables
        return self._data


async def test_registration_asks_for_products_update_at_the_given_uri() -> None:
    client = FakeGraphQLClient(
        {"webhookSubscriptionCreate": {"webhookSubscription": {"id": "gid://1"}, "userErrors": []}}
    )

    subscription_id = await register_products_update_webhook(client, "https://example.test/hook")

    assert subscription_id == "gid://1"
    assert client.variables == {
        "topic": "PRODUCTS_UPDATE",
        "webhookSubscription": {"uri": "https://example.test/hook"},
    }


async def test_user_errors_make_the_registration_fail() -> None:
    """A 200 with userErrors is still a failure."""
    client = FakeGraphQLClient(
        {
            "webhookSubscriptionCreate": {
                "webhookSubscription": None,
                "userErrors": [{"field": ["webhookSubscription", "uri"], "message": "Address is invalid"}],
            }
        }
    )

    with pytest.raises(ShopifyError, match="Address is invalid"):
        await register_products_update_webhook(client, "http://localhost:8000/hook")
