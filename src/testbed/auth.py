"""认证端点: basic / bearer / apikey / digest."""

import base64
import binascii
import hashlib
import json
import os
import re

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer

router = APIRouter(prefix="/auth", tags=["auth"])

_BASIC_USERNAME = "demo"
_BASIC_PASSWORD = "demo-pass"
_BEARER_TOKEN = "demo-token"
_API_KEY = "demo-key"

_DIGEST_REALM = "testbed"
_DIGEST_USER = "demo"
_DIGEST_PASSWORD = "digest-pass"
# 测试后端不做防重放, 仅记录本次进程内已发放的 nonce 以支持质询/响应往返.
_DIGEST_NONCES: set[str] = set()

_bearer_auth = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def _unauthorized(
    *,
    basic_challenge: bool = False,
    bearer_challenge: bool = False,
    digest_challenge: bool = False,
) -> Response:
    headers = {}
    if basic_challenge:
        headers["WWW-Authenticate"] = "Basic"
    if bearer_challenge:
        headers["WWW-Authenticate"] = "Bearer"
    if digest_challenge:
        nonce = _make_digest_nonce()
        headers["WWW-Authenticate"] = (
            f'Digest realm="{_DIGEST_REALM}", nonce="{nonce}", '
            'qop="auth", algorithm="MD5"'
        )
    return Response(
        content=json.dumps({"error": "unauthorized"}),
        status_code=401,
        media_type="application/json",
        headers=headers,
    )


@router.get("/basic", response_model=None)
def auth_basic(request: Request) -> dict | Response:
    """HTTP Basic 认证, demo 凭证写死."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return _unauthorized(basic_challenge=True)
    encoded = auth[len("Basic "):]
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return _unauthorized(basic_challenge=True)
    if ":" not in decoded:
        return _unauthorized(basic_challenge=True)
    username, password = decoded.split(":", 1)
    if username != _BASIC_USERNAME or password != _BASIC_PASSWORD:
        return _unauthorized(basic_challenge=True)
    return {"username": username}


@router.get("/bearer", response_model=None)
def auth_bearer(token=Depends(_bearer_auth)) -> dict | Response:
    """HTTP Bearer token 认证."""
    if token is None or token.credentials != _BEARER_TOKEN:
        return _unauthorized(bearer_challenge=True)
    return {"ok": True}


@router.get("/apikey", response_model=None)
def auth_apikey(
    header_key: str | None = Depends(_api_key_header),
    query_key: str | None = Depends(_api_key_query),
) -> dict | Response:
    """API Key 认证: 支持 X-API-Key header 或 api_key query 参数."""
    key = header_key if header_key is not None else query_key
    if key != _API_KEY:
        return _unauthorized()
    return {"ok": True}


def _make_digest_nonce() -> str:
    """生成并登记一个 nonce, 供后续响应校验."""
    nonce = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    _DIGEST_NONCES.add(nonce)
    return nonce


def _digest_challenge() -> Response:
    return _unauthorized(digest_challenge=True)


def _parse_digest_params(auth_value: str) -> dict[str, str]:
    """解析 Authorization: Digest 后的键值对 (支持带引号与不带引号)."""
    params: dict[str, str] = {}
    # 形如: username="demo", realm="testbed", nonce="...", uri="/auth/digest",
    #       response="...", qop="auth", nc=00000001, cnonce="..."
    for match in re.finditer(r'(\w+)=("([^"]*)"|([^,]*))', auth_value):
        key = match.group(1)
        value = match.group(3) if match.group(3) is not None else match.group(4)
        params[key] = value.strip()
    return params


def _verify_digest_response(request: Request, params: dict[str, str]) -> bool:
    """按 RFC 7616 (MD5, qop=auth) 重算 response 并比对."""
    username = params.get("username", "")
    realm = params.get("realm", "")
    nonce = params.get("nonce", "")
    uri = params.get("uri", "")
    qop = params.get("qop", "")
    nc = params.get("nc", "")
    cnonce = params.get("cnonce", "")
    response = params.get("response", "")

    if username != _DIGEST_USER:
        return False
    if realm != _DIGEST_REALM:
        return False
    if qop != "auth":
        return False
    if nonce not in _DIGEST_NONCES:
        # 未质询过的 nonce 直接拒绝, 与最小实现一致.
        return False

    expected_uri = request.url.path
    query = request.url.query
    if query:
        expected_uri = f"{expected_uri}?{query}"
    if uri != expected_uri:
        return False

    ha1 = hashlib.md5(
        f"{username}:{realm}:{_DIGEST_PASSWORD}".encode()
    ).hexdigest()
    ha2 = hashlib.md5(f"{request.method}:{uri}".encode()).hexdigest()
    expected = hashlib.md5(
        f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()
    ).hexdigest()
    return expected == response


@router.get("/digest", response_model=None)
def auth_digest(request: Request) -> dict | Response:
    """HTTP Digest 认证 (RFC 7616 最小子集: MD5, qop=auth), demo 凭证写死."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Digest "):
        return _digest_challenge()

    params = _parse_digest_params(auth[len("Digest "):])
    if _verify_digest_response(request, params):
        return {"ok": True}
    return _digest_challenge()
