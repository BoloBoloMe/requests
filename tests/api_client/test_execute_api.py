"""ISSUE-03 TS-003: POST /execute 按 Accept 协商 SSE/NDJSON + 断连不取消 (M3 D007).

接缝: FastAPI 壳 TestClient 薄测 (D014-3) + TC-013 真进程真 HTTP.
事件模型与 TS-002 engine 相同 (meta/chunk/done, M4 D003), 只是编码不同.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api_client.store import Item, Store
from api_client.web.app import create_app

TOKEN = "test-token"


def _write_echo_item(data_dir, testbed_url) -> None:
    store = Store(data_dir)
    store.write_item(
        "demo",
        "echo",
        Item(name="echo", method="GET", url=f"{testbed_url}/echo?hello=world"),
    )


def _auth() -> dict[str, str]:
    # Host 白名单中间件要求回环 Host (同 test_crud_api 惯例)
    return {"X-Auth-Token": TOKEN, "Host": "localhost"}


def _collect_ndjson(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _collect_sse(response) -> list[dict]:
    """解析 SSE 帧: event: <type> + data: <json>, 帧间空行分隔."""
    events = []
    event_type = None
    for line in response.text.splitlines():
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            events.append({"event": event_type, **json.loads(line[len("data:"):].strip())})
    return events


# --- TC-011: Accept 协商 (M3 D007, 单一事件模型两种编码) ---


def test_execute_negotiates_ndjson_by_accept(tmp_path, testbed_url):
    """Accept: application/x-ndjson -> 逐行 JSON, 每行一个完整事件."""
    _write_echo_item(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/execute",
        json={"collection": "demo", "item": "echo"},
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _collect_ndjson(response)
    assert [e["type"] for e in events] == ["meta", "chunk", "done"]


def test_execute_negotiates_sse_by_accept(tmp_path, testbed_url):
    """Accept: text/event-stream -> SSE 帧 (event:/data: 对), 同一事件模型."""
    _write_echo_item(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/execute",
        json={"collection": "demo", "item": "echo"},
        headers={**_auth(), "Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _collect_sse(response)
    assert [e["type"] for e in events] == ["meta", "chunk", "done"]
    assert [e["event"] for e in events] == ["meta", "chunk", "done"]


# --- TC-012: done 事件字段 (M4 D003) ---


def test_execute_done_event_fields(tmp_path, testbed_url):
    """done 含 status/duration_ms/item; meta 含 method/resolved_url (M4 D003)."""
    _write_echo_item(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/execute",
        json={"collection": "demo", "item": "echo"},
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    events = _collect_ndjson(response)
    meta, done = events[0], events[-1]
    assert meta["type"] == "meta"
    assert meta["method"] == "GET"
    assert meta["resolved_url"] == f"{testbed_url}/echo?hello=world"
    assert done["type"] == "done"
    assert done["status"] == 200
    assert isinstance(done["duration_ms"], int)
    assert done["item"] == "demo/echo"


# --- TC-013: 客户端断连不取消执行, 历史仍落盘 (M3 D006, 真进程真 HTTP) ---


def _wait_service_json(data_dir, timeout=30) -> dict:
    import time

    deadline = time.monotonic() + timeout
    service_json = data_dir / ".local" / "service.json"
    while time.monotonic() < deadline:
        try:
            return json.loads(service_json.read_text())
        except (OSError, ValueError):
            time.sleep(0.1)
    raise RuntimeError("apic serve 未就绪 (service.json 未出现)")


def test_execute_client_disconnect_does_not_cancel(tmp_path, testbed_url):
    """真进程: 客户端读完第一帧即断开, 执行继续跑到底 (testbed 50 帧 x 0.2s),
    SSE 连接被服务端正常关闭后, 已收事件聚合落盘 (M2 D011 + M3 D006)."""
    import os
    import signal
    import subprocess
    import time

    import httpx

    store = Store(tmp_path)
    store.write_item(
        "demo",
        "stream",
        Item(name="stream", method="GET", url=f"{testbed_url}/sse?count=50&interval=0.2"),
    )
    proc = subprocess.Popen(
        ["uv", "run", "apic", "serve", "--data-dir", str(tmp_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # 独立进程组, 清理按组杀 (同 conftest 惯例)
    )
    try:
        service = _wait_service_json(tmp_path)
        base = f"http://127.0.0.1:{service['port']}"
        headers = {
            "X-Auth-Token": service["token"],
            "Accept": "text/event-stream",
        }
        with httpx.Client(trust_env=False, timeout=30) as http:
            with http.stream(
                "POST",
                f"{base}/execute",
                json={"collection": "demo", "item": "stream"},
                headers=headers,
            ) as resp:
                assert resp.status_code == 200
                first = next(iter(resp.iter_lines()))
                assert first == "event: meta"
            # 离开 with = 客户端断开; 不断言取消, 只观察历史落盘

        history_dir = tmp_path / ".local" / "history" / "demo" / "stream"
        deadline = time.monotonic() + 30
        files = []
        while time.monotonic() < deadline:
            files = sorted(history_dir.glob("*.yaml")) if history_dir.is_dir() else []
            if files:
                break
            time.sleep(0.2)
        assert files, "断连后执行未完成或历史未落盘"
        import yaml

        record = yaml.safe_load(files[0].read_text(encoding="utf-8"))
        assert record["response"]["status"] == 200
        text = record["response"]["body"]["text"]
        # 50 帧全部收到并聚合: 首帧与末帧都在文本体内
        assert json.dumps({"seq": 0, "total": 50}) in text
        assert json.dumps({"seq": 49, "total": 50}) in text
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
