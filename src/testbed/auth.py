"""认证端点: basic / bearer / apikey."""

import base64
import binascii
import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer

router = APIRouter(prefix="/auth", tags=["auth"])

_BASIC_USERNAME = "demo"
_BASIC_PASSWORD = "demo-pass"
_BEARER_TOKEN = "demo-token"
_API_KEY = "demo-key"

_bearer_auth = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def _unauthorized(
    *, basic_challenge: bool = False, bearer_challenge: bool = False,
) -> Response:
    headers = {}
    if basic_challenge:
        headers["WWW-Authenticate"] = "Basic"
    if bearer_challenge:
        headers["WWW-Authenticate"] = "Bearer"
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
