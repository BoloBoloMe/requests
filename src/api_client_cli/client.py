"""服务 client (M3 D011): ensure_running 幂等拉起 + service.json 服务发现 + 请求封装.

本模块是 CLI 导入核心库的唯一位置: 仅 api_client.launch (M3 D001/D002 唯一例外).
请求一律带 X-Auth-Token (D004-4); 请求级重试一次 (D011-4).
"""

import json
import os
import signal
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from api_client import launch

from .errors import CliError, server_error

# 请求级重试覆盖传输错误与对端无响应断开 (D011-4)
_RETRYABLE = (httpx.TransportError, httpx.RemoteProtocolError)
LOCAL_DIR = ".local"
SERVICE_JSON = "service.json"
STOP_TIMEOUT = 10.0


@dataclass(frozen=True)
class Connection:
    """服务发现结果: service.json {port, token, pid} + 存活标记."""

    port: int
    token: str
    pid: int
    alive: bool = True

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """非流式请求: 带 token, 传输失败或 5xx 重试一次 (D011-4)."""
        headers = {"X-Auth-Token": self.token, **kwargs.pop("headers", {})}
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                with httpx.Client(base_url=self.base_url, timeout=10.0, trust_env=False) as client:
                    response = client.request(method, path, headers=headers, **kwargs)
                if response.status_code < 500 or attempt == 1:
                    return response
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt == 1:
                    break
        if last_exc is not None:
            raise CliError("SERVICE_ERROR", f"服务不可达 ({self.base_url}): {last_exc}") from last_exc
        return response  # type: ignore[possibly-undefined]

    def stream_events(self, path: str, body: dict) -> Iterator[dict]:
        """POST + Accept NDJSON, 逐行产出事件; 建连阶段传输失败/5xx 重试一次.

        非 200 响应在事件流开始前抛 server_error 映射的 CliError.
        """
        headers = {"X-Auth-Token": self.token, "Accept": "application/x-ndjson"}
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                with httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(10.0, read=None), trust_env=False) as client:
                    with client.stream("POST", path, json=body, headers=headers) as response:
                        if response.status_code >= 500 and attempt == 0:
                            continue  # 建连即 5xx: 重试一次
                        if response.status_code != 200:
                            raise server_error(response.status_code, response.read().decode("utf-8", "replace"))
                        for line in response.iter_lines():
                            if line.strip():
                                yield json.loads(line)
                        return
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt == 1:
                    break
        raise CliError("SERVICE_ERROR", f"服务不可达 ({self.base_url}): {last_exc}") from last_exc


def read_service_json(data_dir: str | Path) -> dict | None:
    """读 <data-dir>/.local/service.json; 缺失/坏 JSON/缺键视为无效 (None)."""
    try:
        data = json.loads((Path(data_dir) / LOCAL_DIR / SERVICE_JSON).read_text())
        port, token, pid = data["port"], data["token"], data["pid"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(port, int) or not isinstance(token, str) or not isinstance(pid, int):
        return None
    return {"port": port, "token": token, "pid": pid}


def read_connection(data_dir: str | Path) -> Connection | None:
    """只读服务发现 (不拉起): service.json + kill(pid,0) 存活校验 (D011-4 stale 防护)."""
    data = read_service_json(data_dir)
    if data is None:
        return None
    return Connection(data["port"], data["token"], data["pid"], alive=launch.pid_alive(data["pid"]))


def connect(data_dir: str | Path) -> Connection:
    """幂等拉起 (服务在则不动作) + 服务发现; 供业务命令使用 (M3 D011/F004)."""
    try:
        launch.ensure_running(data_dir)
    except launch.LaunchError as exc:
        raise CliError("SERVICE_ERROR", str(exc)) from exc
    conn = read_connection(data_dir)
    if conn is None or not conn.alive:
        raise CliError("SERVICE_ERROR", f"服务发现信息缺失或进程已退出 ({data_dir})")
    return conn


def stop_service(data_dir: str | Path) -> int:
    """按 data-dir 定位停止 (D011-7): SIGTERM + 等待退出; 返回被停 pid.

    复用 launch.pid_alive (公开 API); 无可停止服务抛 CliError(SERVICE_ERROR).
    """
    conn = read_connection(data_dir)
    if conn is None:
        raise CliError("SERVICE_ERROR", f"无可停止的服务 ({Path(data_dir) / LOCAL_DIR / SERVICE_JSON} 缺失或损坏)")
    if not conn.alive:
        return conn.pid  # 已不在运行 (stale service.json), 幂等成功
    os.kill(conn.pid, signal.SIGTERM)
    deadline = time.monotonic() + STOP_TIMEOUT
    while time.monotonic() < deadline:
        if not launch.pid_alive(conn.pid):
            return conn.pid
        time.sleep(0.05)
    raise CliError("SERVICE_ERROR", f"服务 (pid {conn.pid}) 未在 {STOP_TIMEOUT:.0f}s 内退出")
