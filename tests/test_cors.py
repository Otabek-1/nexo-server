from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.cors import with_cors


def test_production_origin_receives_cors_headers_on_server_errors():
    api = FastAPI()

    @api.get("/fail")
    async def fail():
        raise RuntimeError("test failure")

    app = with_cors(api, "https://old-frontend.example")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/fail", headers={"Origin": "https://www.nexoo.space"})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "https://www.nexoo.space"


def test_cors_preflight_allows_production_origin_even_when_env_is_customized():
    api = FastAPI()
    app = with_cors(api, "https://old-frontend.example")

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/tests",
            headers={
                "Origin": "https://www.nexoo.space",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://www.nexoo.space"
