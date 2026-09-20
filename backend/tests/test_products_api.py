"""Contract tests for tasks 1 and 2. They fail until those tasks are done."""

from fastapi.testclient import TestClient

PRODUCT_ID = "8100000000001"
VARIANT_ID = "45100000000001"
VARIANT_PATH = f"/api/products/{PRODUCT_ID}/variants/{VARIANT_ID}"


def test_list_products_returns_products_with_variants(client: TestClient) -> None:
    response = client.get("/api/products")

    assert response.status_code == 200
    products = response.json()
    assert len(products) == 3

    first_variant = products[0]["variants"][0]
    assert set(first_variant) >= {
        "id",
        "product_id",
        "title",
        "price",
        "currency_code",
        "inventory_quantity",
        "inventory_policy",
        "updated_at",
    }
    assert first_variant["price"] == "24.00"
    assert first_variant["inventory_policy"] in {"DENY", "CONTINUE"}


def test_update_variant_changes_the_price(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"price": "18.50"})

    assert response.status_code == 200
    assert response.json()["price"] == "18.50"

    products = client.get("/api/products").json()
    stored = next(variant for variant in products[0]["variants"] if variant["id"] == VARIANT_ID)
    assert stored["price"] == "18.50"


def test_update_variant_turns_on_continue_selling(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"inventory_policy": "CONTINUE"})

    assert response.status_code == 200
    assert response.json()["inventory_policy"] == "CONTINUE"


def test_update_variant_accepts_both_fields_at_once(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"price": "31.00", "inventory_policy": "CONTINUE"})

    assert response.status_code == 200
    body = response.json()
    assert body["price"] == "31.00"
    assert body["inventory_policy"] == "CONTINUE"


def test_update_variant_reports_an_unknown_variant_as_not_found(client: TestClient) -> None:
    response = client.patch(f"/api/products/{PRODUCT_ID}/variants/404404404", json={"price": "18.50"})

    assert response.status_code == 404


def test_update_variant_rejects_an_empty_body(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={})

    assert response.status_code == 422


def test_update_variant_rejects_a_price_below_zero(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"price": "-1.00"})

    assert response.status_code == 422


def test_update_variant_rejects_an_unknown_inventory_policy(client: TestClient) -> None:
    response = client.patch(VARIANT_PATH, json={"inventory_policy": "SOMETIMES"})

    assert response.status_code == 422
