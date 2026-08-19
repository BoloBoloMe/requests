"""ISSUE-03 / ISSUE-04: 认证端点 basic/bearer/apikey/digest 切片测试."""

import base64
import hashlib
import re

import httpx
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


class TestDigestAuth:
    def _build_digest_auth_header(
        self,
        *,
        nonce: str,
        uri: str,
        username: str = "demo",
        password: str = "digest-pass",
        method: str = "GET",
        nc: str = "00000001",
        cnonce: str = "abc123",
    ) -> str:
        realm = "testbed"
        qop = "auth"
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        response = hashlib.md5(
            f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()
        ).hexdigest()
        return (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{response}", qop="{qop}", nc={nc}, '
            f'cnonce="{cnonce}"'
        )

    def test_digest_unauthorized_returns_challenge(self):
        response = client.get("/auth/digest")
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}
        www_auth = response.headers.get("WWW-Authenticate", "")
        assert www_auth.startswith("Digest ")
        assert "realm=\"" in www_auth
        assert "nonce=\"" in www_auth
        assert "qop=\"auth\"" in www_auth

    def test_digest_correct_credentials_returns_200(self):
        response = client.get(
            "/auth/digest",
            auth=httpx.DigestAuth("demo", "digest-pass"),
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_digest_wrong_password_returns_401(self):
        response = client.get(
            "/auth/digest",
            auth=httpx.DigestAuth("demo", "wrong-pass"),
        )
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}

    def test_digest_mismatched_uri_returns_401(self):
        challenge = client.get("/auth/digest")
        assert challenge.status_code == 401
        www_auth = challenge.headers["WWW-Authenticate"]
        nonce_match = re.search(r'nonce="([^"]+)"', www_auth)
        assert nonce_match is not None
        nonce = nonce_match.group(1)

        # 构造合法字段但 uri 与真实请求路径不符的 Authorization 头.
        auth_header = self._build_digest_auth_header(nonce=nonce, uri="/auth/digest")
        response = client.get(
            "/auth/digest?foo=bar",
            headers={"Authorization": auth_header},
        )
        assert response.status_code == 401
