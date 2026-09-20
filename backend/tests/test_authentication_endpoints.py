"""Contract tests for task 4. They fail until the installation flow is written."""

from fastapi.testclient import TestClient


def test_install_sends_the_merchant_to_shopify(client: TestClient) -> None:
    response = client.get(
        "/auth/install",
        params={"shop": "test-store.myshopify.com"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 303, 307}
    location = response.headers["location"]
    assert location.startswith("https://test-store.myshopify.com/admin/oauth/authorize")
    assert "state=" in location


def test_install_refuses_a_shop_domain_that_is_not_shopify(client: TestClient) -> None:
    response = client.get(
        "/auth/install",
        params={"shop": "example.com"},
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_the_callback_refuses_an_unsigned_request(client: TestClient) -> None:
    response = client.get(
        "/auth/callback",
        params={"code": "abc123", "shop": "test-store.myshopify.com", "state": "nonce-value"},
        follow_redirects=False,
    )

    assert response.status_code in {400, 401}
