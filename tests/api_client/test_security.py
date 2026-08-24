"""ISSUE-01 TS-003/TS-004: 安全五件套参数化单测 (D004/D005, D014-6) 与服务骨架冒烟.

TestClient 默认 host=testserver 会触发 Host 白名单拒绝, 薄测一律显式传 Host: localhost.
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from api_client.web.app import create_app

TOKEN = "test-token"
HOST = {"Host": "localhost"}
AUTH = {"X-Auth-Token": TOKEN}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(TOKEN))


# --- TC-004: Host 白名单 (精确匹配, 拒绝伪造与重复头) ---


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "[::1]", "localhost:8000", "127.0.0.1:8000", "[::1]:8000"],
)
def test_host_allowlist_allows_loopback(client, host):
    r = client.get("/health", headers={"Host": host, **AUTH})
    assert r.status_code == 200


def test_host_allowlist_rejects_spoofed_host(client):
    """endswith/包含匹配可被 localhost.evil.com 绕过, 必须精确匹配 (D004-2)."""
    for host in ["localhost.evil.com", "127.0.0.1.evil.com", "evil.com"]:
        r = client.get("/health", headers={"Host": host, **AUTH})
        assert r.status_code == 403, host


def test_host_allowlist_rejects_duplicate_host_headers(client):
    r = client.get(
        "/health",
        headers=[("Host", "localhost"), ("Host", "localhost"), ("X-Auth-Token", TOKEN)],
    )
    assert r.status_code == 403


# --- TC-005: token 校验 (header 主通道, SSE 握手 query 副通道) ---


def test_token_header_required(client):
    assert client.get("/health", headers=HOST).status_code == 401
    assert client.get("/health", headers={**HOST, "X-Auth-Token": "wrong"}).status_code == 401
    assert client.get("/health", headers={**HOST, **AUTH}).status_code == 200


def test_query_token_rejected_on_non_sse(client):
    """非 SSE 握手一律不认 query token (D004-4)."""
    assert client.get(f"/health?token={TOKEN}", headers=HOST).status_code == 401


def test_sse_handshake_accepts_query_token(client):
    """SSE 握手 (Accept: text/event-stream) 额外接受 ?token= (M3 F002)."""
    r = client.get(
        f"/health?token={TOKEN}",
        headers={**HOST, "Accept": "text/event-stream"},
    )
    assert r.status_code == 200


# --- TC-006: 不配置 CORS, 无任何 Access-Control-Allow-* 放行头 ---


def test_no_cors_headers(client):
    r = client.get("/health", headers={**HOST, **AUTH, "Origin": "http://evil.example"})
    assert r.status_code == 200
    assert not [h for h in r.headers if h.lower().startswith("access-control-allow")]

    preflight = client.options(
        "/health",
        headers={
            **HOST,
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert not [h for h in preflight.headers if h.lower().startswith("access-control-allow")]


# --- TC-007: 访问日志脱敏 (URL query token 与 header token 均不出现) ---


def test_access_log_redacts_token(caplog):
    secret = "s3cret-token-plaintext"
    app: FastAPI = create_app(secret)
    c = TestClient(app)
    with caplog.at_level(logging.INFO, logger="api_client.access"):
        c.get(f"/health?token={secret}", headers={**HOST, "Accept": "text/event-stream"})
        c.get("/health", headers={**HOST, "X-Auth-Token": secret})
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert logged, "应有访问日志"
    assert secret not in logged
    assert "token=***" in logged


# --- TC-008: /health 需 token ---


def test_health_requires_token(client):
    """匿名/错 token 401, 带对 token 200 (D004-4)."""
    assert client.get("/health", headers=HOST).status_code == 401
    assert client.get("/health", headers={**HOST, "X-Auth-Token": "wrong"}).status_code == 401
    assert client.get("/health", headers={**HOST, **AUTH}).status_code == 200


# --- TC-009: 真进程 serve/stop 冒烟 ---


def _wait_service_json(data_dir: Path, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        path = data_dir / ".local" / "service.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except ValueError:
                pass
        time.sleep(0.05)
    raise TimeoutError("service.json 未出现")


def test_serve_and_stop_via_cli(tmp_path):
    """真起服务: /health 带 token 200 无 token 401; stop 后 pid 不存活 (D011-7)."""
    data_dir = tmp_path / "repo"
    data_dir.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-m", "api_client", "serve", "--data-dir", str(data_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        info = _wait_service_json(data_dir)
        base = f"http://127.0.0.1:{info['port']}"
        with httpx.Client(trust_env=False) as http:
            r = http.get(f"{base}/health", headers={"X-Auth-Token": info["token"]})
            assert r.status_code == 200
            assert http.get(f"{base}/health").status_code == 401

        stop = subprocess.run(
            [sys.executable, "-m", "api_client", "stop", "--data-dir", str(data_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert stop.returncode == 0, stop.stderr
        proc.wait(timeout=15)
        with pytest.raises(ProcessLookupError):
            os.kill(info["pid"], 0)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


# --- D004-6: text/html 响应注入 CSP script-src 'self' ---


def test_csp_header_on_html_responses():
    app = create_app(TOKEN)

    @app.get("/html-probe", response_class=HTMLResponse)
    async def html_probe() -> str:
        return "<html><body>probe</body></html>"

    c = TestClient(app)
    r = c.get("/html-probe", headers=HOST)
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == "script-src 'self'"

    # 非 html 响应不注入
    r = c.get("/health", headers={**HOST, **AUTH})
    assert "content-security-policy" not in r.headers
