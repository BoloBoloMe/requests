"""ISSUE-03: 认证端点 basic/bearer/apikey 切片测试."""

import base64

import pytest
from fastapi.testclient import TestClient

from testbed.app import app

client = TestClient(app)


def _basic_header(username: str, password: str) -> str:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


class TestBasicAuth:
    def test_basic_correct_credentials_returns_username(self):
        response = client.get(
            "/auth/basic",
            headers={"Authorization": _basic_header("demo", "demo-pass")},
        )
        assert response.status_code == 200
        assert response.json() == {"username": "demo"}

    @pytest.mark.parametrize(
        "auth_header",
        [
            _basic_header("demo", "wrong-pass"),
            _basic_header("wrong-user", "demo-pass"),
            "",
            "Basic invalid-base64!!!",
        ],
    )
    def test_basic_wrong_credentials_returns_401_with_challenge(self, auth_header):
        headers = {"Authorization": auth_header} if auth_header else {}
        response = client.get("/auth/basic", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}
        assert "Basic" in response.headers.get("WWW-Authenticate", "")


class TestBearerAuth:
    def test_bearer_correct_token_returns_200(self):
        response = client.get(
            "/auth/bearer",
            headers={"Authorization": "Bearer demo-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @pytest.mark.parametrize(
        "auth_header",
        [
            "Bearer wrong-token",
            "Bearer",
            "Basic demo-token",
            "",
        ],
    )
    def test_bearer_wrong_or_missing_token_returns_401(self, auth_header):
        headers = {"Authorization": auth_header} if auth_header else {}
        response = client.get("/auth/bearer", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}
        assert "Bearer" in response.headers.get("WWW-Authenticate", "")


class TestApiKeyAuth:
    def test_apikey_correct_via_header_returns_200(self):
        response = client.get(
            "/auth/apikey",
            headers={"X-API-Key": "demo-key"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_apikey_correct_via_query_returns_200(self):
        response = client.get("/auth/apikey?api_key=demo-key")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @pytest.mark.parametrize(
        "headers, query",
        [
            ({"X-API-Key": "wrong-key"}, ""),
            ({"X-API-Key": ""}, ""),
            ({}, "api_key=wrong-key"),
            ({}, "api_key="),
            ({}, ""),
        ],
    )
    def test_apikey_wrong_or_missing_returns_401(self, headers, query):
        url = "/auth/apikey"
        if query:
            url = f"{url}?{query}"
        response = client.get(url, headers=headers)
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}
