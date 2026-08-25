"""tests/api_client_cli 测试设施: fake HTTP 服务 (M3 D014-4) + CLI subprocess 助手.

fake 服务回放 canned 路由并记录请求 (供断言 token 头/请求体); CLI 一律以
subprocess 调用 (`python -m api_client_cli`), 断言 stdout/stderr/退出码.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CLI_TOKEN = "fake-token"
FAKE_VERSION = "0.0.0-fake"


class _Handler(BaseHTTPRequestHandler):
    """按 server.fake.routes 回放; 未注册路由回 404 {"detail": "Not Found"}."""

    def _dispatch(self) -> None:
        fake: FakeService = self.server.fake  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        path, _, query = self.path.partition("?")
        fake.requests.append(
            {
                "method": self.command,
                "path": path,
                "query": query,
                "headers": dict(self.headers),
                "body": raw.decode("utf-8", "replace"),
            }
        )
        route = fake.routes.get((self.command, path))
        if route is None:
            fake.respond(self, 404, {"detail": "Not Found"})
            return
        if callable(route):
            route(self)
            return
        status, payload, content_type = route
        fake.respond(self, status, payload, content_type)

    do_GET = _dispatch
    do_POST = _dispatch
    do_PUT = _dispatch
    do_DELETE = _dispatch

    def log_message(self, *args) -> None:  # 静默访问日志
        pass


class FakeService:
    """本地 socket 假服务: routes[(method, path)] = (status, payload, content_type) 或 callable."""

    def __init__(self) -> None:
        self.routes: dict = {}
        self.requests: list[dict] = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.fake = self  # type: ignore[attr-defined]
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        # 默认 /health: 校验 token (对齐真服务 D004-4), 供 launch ready 判定与 status
        self.routes[("GET", "/health")] = self._health

    def _health(self, handler: _Handler) -> None:
        if handler.headers.get("X-Auth-Token") != CLI_TOKEN:
            self.respond(handler, 401, {"detail": "无效或缺失的 token"})
            return
        self.respond(handler, 200, {"status": "ok", "version": FAKE_VERSION})

    @staticmethod
    def respond(handler: _Handler, status: int, payload, content_type: str = "application/json") -> None:
        if isinstance(payload, (bytes, str)):
            raw = payload.encode() if isinstance(payload, str) else payload
        else:
            raw = json.dumps(payload, ensure_ascii=False).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)

    def add(self, method: str, path: str, status: int = 200, payload=None, content_type: str = "application/json") -> None:
        self.routes[(method, path)] = (status, payload, content_type)

    def start(self) -> "FakeService":
        self._thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def requests_to(self, path: str) -> list[dict]:
        return [r for r in self.requests if r["path"] == path]


def write_service_json(data_dir: Path, port: int, token: str = CLI_TOKEN, pid: int | None = None) -> Path:
    """手写 service.json 指向 fake 服务; pid 默认取 pytest 进程自身 (存活)."""
    local = data_dir / ".local"
    local.mkdir(parents=True, exist_ok=True)
    path = local / "service.json"
    path.write_text(json.dumps({"port": port, "token": token, "pid": pid if pid is not None else os.getpid()}))
    return path


def run_cli(args: list[str], data_dir: Path | None = None, timeout: float = 60) -> subprocess.CompletedProcess:
    """CLI subprocess 调用 (D014-4); --data-dir 置于子命令前 (全局位)."""
    cmd = [sys.executable, "-m", "api_client_cli"]
    if data_dir is not None:
        cmd += ["--data-dir", str(data_dir)]
    cmd += args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def stdout_json(proc: subprocess.CompletedProcess):
    """stdout 解析为 JSON (单对象或逐行 NDJSON 由调用方区分)."""
    return json.loads(proc.stdout)


def stdout_ndjson(proc: subprocess.CompletedProcess) -> list:
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def stderr_error(proc: subprocess.CompletedProcess) -> dict:
    """stderr 单行 {"error":{code,message,details}} 解析."""
    lines = [line for line in proc.stderr.splitlines() if line.strip()]
    assert lines, f"stderr 为空 (exit={proc.returncode}, stdout={proc.stdout!r})"
    assert len(lines) == 1, f"stderr 应为单行错误 JSON: {proc.stderr!r}"
    payload = json.loads(lines[0])
    assert set(payload) == {"error"}, f"stderr 错误形状非法: {payload!r}"
    return payload["error"]
