"""ISSUE-03 TS-004: 历史落盘 (M2 D011) + 不脱敏 (M5 决策 5).

接缝: Store 历史写 API (append_history/list_history) + 文件内容断言;
写入口归 Engine (发送即记录, 副作用经 Store), 打 testbed 真 HTTP.
"""

import asyncio
import json

import pytest
import yaml

from api_client.engine import Engine
from api_client.resolve import build_request
from api_client.store import Body, Environment, Item, KV, MultipartPart, Store


def _send(store: Store, item: Item, *, collection="demo", slug="echo", env=None, config=None):
    """解析并发送, 返回事件列表 (排干)."""
    resolved = build_request(item, env, config)

    async def main() -> list[dict]:
        return [
            event
            async for event in Engine(store).execute(
                resolved,
                item_ref=f"{collection}/{slug}",
                env=env.name if env else None,
                collection=collection,
                slug=slug,
            )
        ]

    return asyncio.run(main())


def _history_files(store: Store, collection="demo", slug="echo"):
    base = store.data_dir / ".local" / "history" / collection / slug
    return sorted(base.glob("*.yaml")) if base.is_dir() else []


def _read_history(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --- TC-014: 文本传输全保留 append 落盘 (M2 D011) ---


def test_history_text_roundtrip_fully_recorded(tmp_path, testbed_url):
    """文本请求+响应 (状态行/头/体/耗时) 全保留; 连发两次 = 两个历史文件 (append)."""
    store = Store(tmp_path)
    item = Item(
        name="echo",
        method="POST",
        url=f"{testbed_url}/echo?a=1",
        headers=[KV("X-Trace", "t-1")],
        body=Body("json", text='{"hello": "world"}'),
    )
    events = _send(store, item)
    assert events[-1]["status"] == 200

    files = _history_files(store)
    assert len(files) == 1
    record = _read_history(files[0])

    request = record["request"]
    assert request["method"] == "POST"
    assert request["url"] == f"{testbed_url}/echo?a=1"
    assert {"key": "X-Trace", "value": "t-1"} in request["headers"]
    assert request["body"] == {"type": "json", "text": '{"hello": "world"}'}

    response = record["response"]
    assert response["status"] == 200
    assert response["body"]["kind"] == "text"
    echoed = json.loads(response["body"]["text"])
    assert echoed["body"] == {"hello": "world"}
    assert any(h["key"].lower() == "content-type" for h in response["headers"])
    assert isinstance(record["duration_ms"], int)

    _send(store, item)  # append: 再发一次多一个文件, 旧文件不动
    files = _history_files(store)
    assert len(files) == 2


# --- TC-015: 非文本/超大 body 只落元信息 (M2 D011) ---


def test_history_binary_response_metadata_only(tmp_path, testbed_url):
    """/large 返回 application/octet-stream: 响应体只落 content-type/大小, 无 text."""
    store = Store(tmp_path)
    item = Item(name="bin", method="GET", url=f"{testbed_url}/large?bytes=1000")
    events = _send(store, item, slug="bin")
    assert events[-1]["status"] == 200

    (path,) = _history_files(store, slug="bin")
    record = _read_history(path)
    body = record["response"]["body"]
    assert body["kind"] == "binary"
    assert body["content_type"] == "application/octet-stream"
    assert body["size"] == 1000
    assert "text" not in body


# --- TC-016: multipart 落文件引用路径+大小, 不内联文件内容 (M2 D011/D009) ---


def test_history_multipart_file_reference_not_inlined(tmp_path, testbed_url):
    store = Store(tmp_path)
    upload = tmp_path / "files" / "secret-payload.txt"
    upload.parent.mkdir(parents=True, exist_ok=True)  # Store 已建 files/
    upload.write_bytes(b"file-bytes-must-not-appear-in-history")
    item = Item(
        name="upload",
        method="POST",
        url=f"{testbed_url}/echo",
        body=Body(
            "multipart",
            parts=[
                MultipartPart(name="note", value="inline-text"),
                MultipartPart(
                    name="upload", file="files/secret-payload.txt", content_type="text/plain"
                ),
            ],
        ),
    )
    events = _send(store, item, slug="upload")
    assert events[-1]["status"] == 200

    (path,) = _history_files(store, slug="upload")
    raw = path.read_text(encoding="utf-8")
    assert "file-bytes-must-not-appear-in-history" not in raw.split("request:")[1].split("response:")[0]
    record = _read_history(path)
    parts = record["request"]["body"]["parts"]
    assert parts[0] == {"name": "note", "value": "inline-text"}
    assert parts[1]["file"] == "files/secret-payload.txt"  # 引用原样存储
    assert parts[1]["size"] == len(b"file-bytes-must-not-appear-in-history")


# --- TC-017: 不脱敏 (M5 决策 5): secret 明文出现在历史 ---


def test_history_keeps_secret_plaintext(tmp_path, testbed_url):
    """环境 secrets 值经 {{var}} 解析进请求头, 历史文件中该值明文可读."""
    store = Store(tmp_path)
    env = Environment(
        name="dev",
        vars={"host": testbed_url},
        secrets={"token": "s3cr3t-plaintext-token"},
        merged={"host": testbed_url, "token": "s3cr3t-plaintext-token"},
    )
    item = Item(
        name="bearer",
        method="GET",
        url="{{host}}/echo",
        headers=[KV("Authorization", "Bearer {{token}}")],
    )
    events = _send(store, item, slug="bearer", env=env)
    assert events[-1]["status"] == 200  # 解析后请求真实到达 (回显可证)

    (path,) = _history_files(store, slug="bearer")
    raw = path.read_text(encoding="utf-8")
    assert "s3cr3t-plaintext-token" in raw  # 明文, 无任何掩码
    record = _read_history(path)
    assert {
        "key": "Authorization",
        "value": "Bearer s3cr3t-plaintext-token",
    } in record["request"]["headers"]


def test_history_keeps_bearer_auth_plaintext(tmp_path, testbed_url):
    """auth 字段 (bearer) 在发送时应用, 历史记实际发送的头: token 明文可读.
    (冒烟抓到的缺口: 快照若取解析前 headers 会丢认证凭证.)"""
    store = Store(tmp_path)
    item = Item(
        name="bearer",
        method="GET",
        url=f"{testbed_url}/auth/bearer",
        auth={"type": "bearer", "token": "demo-token"},
    )
    events = _send(store, item, slug="bearer")
    assert events[-1]["status"] == 200

    (path,) = _history_files(store, slug="bearer")
    assert "demo-token" in path.read_text(encoding="utf-8")
    record = _read_history(path)
    assert {
        "key": "Authorization",
        "value": "Bearer demo-token",
    } in record["request"]["headers"]


# --- TC-018: SSE 连接关闭后聚合落盘, 未关闭不落 (M2 D011) ---


def test_history_sse_aggregated_after_close(tmp_path, testbed_url):
    """/sse?count=3 正常关闭: 三个事件聚合为一个文本体落盘."""
    store = Store(tmp_path)
    item = Item(name="sse", method="GET", url=f"{testbed_url}/sse?count=3&interval=0.01")
    events = _send(store, item, slug="sse")
    assert events[-1]["status"] == 200

    (path,) = _history_files(store, slug="sse")
    record = _read_history(path)
    body = record["response"]["body"]
    assert body["kind"] == "text"
    assert body["content_type"].startswith("text/event-stream")
    for seq in range(3):
        assert json.dumps({"seq": seq, "total": 3}) in body["text"]


def test_history_sse_not_written_when_stream_broken(tmp_path, testbed_url):
    """SSE 未关闭不落: interval=5s > 读超时 4s, 流中途超时不聚合落盘."""
    store = Store(tmp_path)
    item = Item(name="sse-slow", method="GET", url=f"{testbed_url}/sse?count=3&interval=5")
    events = _send(store, item, slug="sse-slow")
    assert events[-1]["error"]["code"] == "TIMEOUT"
    assert _history_files(store, slug="sse-slow") == []


# --- GET /history/{collection}/{slug} 只读端点 (M2 D011) ---


def test_history_endpoint_lists_entries(tmp_path, testbed_url):
    """发送一次后经 API 读回: 按时序返回条目, 含文件名与请求/响应; 无记录回空列表."""
    from fastapi.testclient import TestClient

    from api_client.web.app import create_app

    store = Store(tmp_path)
    item = Item(name="echo", method="GET", url=f"{testbed_url}/echo?hello=world")
    _send(store, item)

    client = TestClient(create_app("tok", data_dir=tmp_path))
    auth = {"X-Auth-Token": "tok", "Host": "localhost"}
    resp = client.get("/history/demo/echo", headers=auth)
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["file"].endswith(".yaml")
    assert entries[0]["request"]["method"] == "GET"
    assert entries[0]["response"]["status"] == 200

    empty = client.get("/history/demo/never-sent", headers=auth)
    assert empty.status_code == 200
    assert empty.json()["entries"] == []
