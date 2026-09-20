from fastapi.testclient import TestClient


def test_health_reports_the_running_mode(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "using_mock_shopify" in body
    assert "shopify_api_version" in body
