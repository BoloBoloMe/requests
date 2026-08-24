"""安全五件套 (M3 D004): Host 白名单 / token 校验 / 无 CORS / 日志脱敏 / CSP.

CORS 不放行 = 不装 CORSMiddleware (app 侧零配置即满足, 由测试护栏守住).
"""

import hmac
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as BaseRequest
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOKEN_HEADER = "X-Auth-Token"
CSP_VALUE = "script-src 'self'"
ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

access_logger = logging.getLogger("api_client.access")


def normalize_host(value: str) -> str:
    """剥离 Host 头端口部分: localhost:8000 -> localhost; [::1]:8000 -> ::1."""
    v = value.strip()
    if v.startswith("["):
        end = v.find("]")
        return v[1:end] if end != -1 else v
    if v.count(":") == 1:
        return v.rsplit(":", 1)[0]
    return v  # 无括号多冒号按 IPv6 字面量处理


def is_host_allowed(host_values: list[str]) -> bool:
    """Host 精确白名单 (D004-2): 缺失/重复 Host 头均拒绝, 防 endswith 绕过."""
    if len(host_values) != 1:
        return False
    return normalize_host(host_values[0]) in ALLOWED_HOSTS


class HostAllowlistMiddleware:
    """纯 ASGI 中间件: Host 不在白名单则 403 (防 DNS rebinding)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        hosts = [
            v.decode("latin-1") for k, v in scope["headers"] if k.lower() == b"host"
        ]
        if not is_host_allowed(hosts):
            response = Response('{"detail":"Host 头不在白名单"}', status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def make_token_dependency(expected: str) -> Callable[[Request], Awaitable[None]]:
    """构造 token 校验依赖: header 为主通道, SSE 握手 (Accept: text/event-stream)
    额外接受 ?token= (EventSource 无法自定义 header, M3 F002)."""

    async def require_token(request: Request) -> None:
        token = request.headers.get(TOKEN_HEADER)
        if token is None and "text/event-stream" in request.headers.get("accept", ""):
            token = request.query_params.get("token")
        if token is None or not hmac.compare_digest(token, expected):
            raise HTTPException(status_code=401, detail="无效或缺失的 token")

    return require_token


def redact_url(url: str) -> str:
    """访问日志脱敏: URL query 中 token 参数值替换为 *** (D004-4)."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    # 手工拼接: 占位符 *** 不应被 percent-encode
    redacted = "&".join(
        f"{k}=***" if k == "token" else f"{k}={v}" for k, v in pairs
    )
    return urlunsplit(parts._replace(query=redacted))


class AccessLogMiddleware(BaseHTTPMiddleware):
    """访问日志: 只记 method/脱敏 URL/状态码; 从不记请求头 (header token 天然不落日志)."""

    async def dispatch(self, request: BaseRequest, call_next) -> Response:
        response = await call_next(request)
        access_logger.info(
            "%s %s -> %d",
            request.method,
            redact_url(str(request.url)),
            response.status_code,
        )
        return response


class ContentSecurityPolicyMiddleware:
    """纯 ASGI 中间件: text/html 响应注入 CSP script-src 'self' (D004-6)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_csp(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message["headers"])
                content_type = headers.get("content-type", "")
                if (
                    content_type.startswith("text/html")
                    and "content-security-policy" not in headers
                ):
                    headers.append("content-security-policy", CSP_VALUE)
            await send(message)

        await self.app(scope, receive, send_with_csp)
