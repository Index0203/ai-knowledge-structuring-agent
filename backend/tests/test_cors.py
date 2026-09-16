from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_lan_origin_is_allowed_without_configuration() -> None:
    response = client.get("/health", headers={"Origin": "http://192.168.1.10:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://192.168.1.10:3000"


def test_private_range_origins_are_allowed() -> None:
    for origin in ("http://10.141.82.65:3000", "http://172.16.0.4:3000", "http://localhost:3000"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin


def test_public_origin_is_not_allowed() -> None:
    response = client.get("/health", headers={"Origin": "https://example.com"})

    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_a_lan_origin_is_accepted() -> None:
    response = client.options(
        "/api/v1/uploads",
        headers={
            "Origin": "http://10.0.0.5:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://10.0.0.5:3000"
