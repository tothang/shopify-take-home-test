"""Contract tests for task 4. They fail until the installation flow is written."""

from urllib.parse import parse_qs, urlparse

import pytest

from application.shopify.oauth import (
    build_authorization_url,
    is_valid_shop_domain,
    verify_callback_signature,
)

SECRET = "test-application-secret"
CALLBACK_PARAMETERS = {
    "code": "abc123",
    "hmac": "ba15b9a222210d2bbbac050fe4040110f105493133badaa945795cb22de21aac",
    "shop": "test-store.myshopify.com",
    "state": "nonce-value",
    "timestamp": "1770000000",
}


@pytest.mark.parametrize(
    "shop_domain",
    [
        "test-store.myshopify.com",
        "a1.myshopify.com",
    ],
)
def test_real_shop_domains_are_accepted(shop_domain: str) -> None:
    assert is_valid_shop_domain(shop_domain) is True


@pytest.mark.parametrize(
    "shop_domain",
    [
        "",
        "example.com",
        "test-store.myshopify.com.example.com",
        "example.com/test-store.myshopify.com",
        "test-store.myshopify.com/admin",
        "https://test-store.myshopify.com",
        "test store.myshopify.com",
        "-store.myshopify.com",
        "test-store.myshopify.com?redirect=example.com",
    ],
)
def test_anything_else_is_rejected(shop_domain: str) -> None:
    assert is_valid_shop_domain(shop_domain) is False


def test_the_authorization_url_carries_what_shopify_needs() -> None:
    url = build_authorization_url(
        shop_domain="test-store.myshopify.com",
        api_key="the-api-key",
        scopes="read_products,write_products",
        redirect_url="http://localhost:8000/auth/callback",
        state="nonce-value",
    )

    parsed = urlparse(url)
    parameters = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "test-store.myshopify.com"
    assert parsed.path == "/admin/oauth/authorize"
    assert parameters["client_id"] == ["the-api-key"]
    assert parameters["scope"] == ["read_products,write_products"]
    assert parameters["redirect_uri"] == ["http://localhost:8000/auth/callback"]
    assert parameters["state"] == ["nonce-value"]


def test_a_callback_signed_by_shopify_is_accepted() -> None:
    assert verify_callback_signature(SECRET, CALLBACK_PARAMETERS) is True


def test_a_tampered_parameter_is_rejected() -> None:
    tampered = dict(CALLBACK_PARAMETERS, shop="other-store.myshopify.com")

    assert verify_callback_signature(SECRET, tampered) is False


def test_an_added_parameter_is_rejected() -> None:
    extended = dict(CALLBACK_PARAMETERS, redirect="http://example.com")

    assert verify_callback_signature(SECRET, extended) is False


def test_another_secret_is_rejected() -> None:
    assert verify_callback_signature("another-secret", CALLBACK_PARAMETERS) is False


def test_a_callback_without_a_signature_is_rejected() -> None:
    without_signature = {key: value for key, value in CALLBACK_PARAMETERS.items() if key != "hmac"}

    assert verify_callback_signature(SECRET, without_signature) is False
