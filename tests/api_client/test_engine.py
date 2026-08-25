"""ISSUE-03 TS-002: Engine 打 testbed 真 HTTP (M3 D014-2, 不 mock httpx).

接缝: engine.execute(request, item_ref=..., env=...) -> 执行事件流 (meta/chunk/done, M4 D003).
覆盖: M1 D003 (五种认证), M2 D008/D009 (字段形状/multipart), M3 D006/D013 (Engine 内嵌/内置常量).
"""

import asyncio

import pytest

from api_client.engine import Engine
from api_client.resolve import ResolvedRequest


def _collect(engine: Engine, request: ResolvedRequest, **kwargs) -> list[dict]:
    """同步包装: 排干执行事件流."""

    async def main() -> list[dict]:
        return [event async for event in engine.execute(request, **kwargs)]

    return asyncio.run(main())


# --- TC-005: 五种认证真实往返 (M1 D003, testbed demo 凭证) ---


def test_engine_digest_auth_roundtrip(testbed_url):
    """digest: 401 质询 -> 重算 response 再请求 -> 200 (testbed 手搓 RFC 7616)."""
    request = ResolvedRequest(
        name="digest",
        method="GET",
        url=f"{testbed_url}/auth/digest",
        auth={"type": "digest", "username": "demo", "password": "digest-pass"},
    )
    events = _collect(Engine(), request, item_ref="demo/auth-digest", env=None)
    assert events[0]["type"] == "meta"
    done = events[-1]
    assert done["type"] == "done"
    assert done["status"] == 200


def test_engine_basic_auth_roundtrip(testbed_url):
    request = ResolvedRequest(
        name="basic",
        method="GET",
        url=f"{testbed_url}/auth/basic",
        auth={"type": "basic", "username": "demo", "password": "demo-pass"},
    )
    events = _collect(Engine(), request, item_ref="demo/auth-basic", env=None)
    assert events[-1]["status"] == 200


def test_engine_bearer_auth_roundtrip(testbed_url):
    request = ResolvedRequest(
        name="bearer",
        method="GET",
        url=f"{testbed_url}/auth/bearer",
        auth={"type": "bearer", "token": "demo-token"},
    )
    events = _collect(Engine(), request, item_ref="demo/auth-bearer", env=None)
    assert events[-1]["status"] == 200


def test_engine_apikey_auth_header_and_query(testbed_url):
    """apikey 两种携带: header / query (M1 D003, testbed /auth/apikey 双通道)."""
    header_req = ResolvedRequest(
        name="apikey-header",
        method="GET",
        url=f"{testbed_url}/auth/apikey",
        auth={"type": "apikey", "key": "X-API-Key", "value": "demo-key", "in": "header"},
    )
    assert _collect(Engine(), header_req, item_ref="demo/apikey-h", env=None)[-1]["status"] == 200

    query_req = ResolvedRequest(
        name="apikey-query",
        method="GET",
        url=f"{testbed_url}/auth/apikey",
        auth={"type": "apikey", "key": "api_key", "value": "demo-key", "in": "query"},
    )
    assert _collect(Engine(), query_req, item_ref="demo/apikey-q", env=None)[-1]["status"] == 200


def test_engine_no_auth_roundtrip(testbed_url):
    """auth none/缺省: 不带凭证, 401 如实回传 (不伪造认证)."""
    request = ResolvedRequest(
        name="none", method="GET", url=f"{testbed_url}/auth/basic", auth={"type": "none"}
    )
    events = _collect(Engine(), request, item_ref="demo/no-auth", env=None)
    assert events[-1]["status"] == 401


# --- TC-006: POST /echo 回显 method/url/query/headers/body ---


def test_engine_echo_roundtrip(testbed_url):
    """事件流: meta -> chunk(回显体) -> done; 回显证实 method/query/headers/body 原样到达,
    disabled 的 params/headers 不发送."""
    import json

    from api_client.store import Body, KV

    request = ResolvedRequest(
        name="echo",
        method="POST",
        url=f"{testbed_url}/echo",
        params=[KV("a", "1"), KV("a", "2"), KV("skip", "x", disabled=True)],  # 重复键合法
        headers=[KV("X-Trace", "t-1"), KV("X-Skip", "s", disabled=True)],
        body=Body("json", text='{"hello": "world"}'),
    )
    events = _collect(Engine(), request, item_ref="demo/echo", env="dev")

    meta = events[0]
    assert meta["type"] == "meta"
    assert meta["method"] == "POST"
    assert meta["resolved_url"] == f"{testbed_url}/echo"
    assert meta["env"] == "dev"

    chunks = [e for e in events if e["type"] == "chunk"]
    assert len(chunks) == 1
    assert chunks[0]["index"] == 0
    echoed = json.loads(chunks[0]["data"])
    assert echoed["method"] == "POST"
    assert echoed["query"] == {"a": "2"}  # 重复键都发送; testbed dict() 去重取末值
    assert "skip" not in echoed["query"]
    assert echoed["headers"]["x-trace"] == "t-1"
    assert "x-skip" not in echoed["headers"]
    assert echoed["body"] == {"hello": "world"}

    done = events[-1]
    assert done["type"] == "done"
    assert done["status"] == 200
    assert done["item"] == "demo/echo"
    assert isinstance(done["duration_ms"], int)
    assert done["assertions"] == []  # 断言求值属 ISSUE-04


# --- TC-007: multipart 文件引用 (相对路径, M2 D009) ---


def test_engine_multipart_file_upload(testbed_url, tmp_path):
    """内联文本 + 仓库相对路径文件引用: testbed 回显 content-type 含 multipart boundary."""
    import json

    from api_client.store import Body, MultipartPart, Store

    upload = tmp_path / "files" / "hello.txt"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"file-content-via-relative-path")

    request = ResolvedRequest(
        name="upload",
        method="POST",
        url=f"{testbed_url}/echo",
        body=Body(
            "multipart",
            parts=[
                MultipartPart(name="note", value="inline-text"),
                MultipartPart(name="upload", file="files/hello.txt", content_type="text/plain"),
            ],
        ),
    )
    engine = Engine(Store(tmp_path))  # store 提供仓库根: 相对路径解析基准
    events = _collect(engine, request, item_ref="demo/upload", env=None)

    done = events[-1]
    assert done["status"] == 200
    echoed = json.loads([e for e in events if e["type"] == "chunk"][0]["data"])
    content_type = echoed["body"]["content_type"]
    assert content_type.startswith("multipart/form-data; boundary=")
    assert "file-content-via-relative-path" in echoed["body"]["text"]
    assert "inline-text" in echoed["body"]["text"]


# --- TC-008: /sse?count=5 -> 5 个 chunk 事件 (SSE 流式, M3 D006) ---


def test_engine_sse_five_chunks(testbed_url):
    """text/event-stream 逐帧转 chunk 事件: 帧序保留 (index 递增), done 200.

    与 TC-009 对照: read 超时是 "等下一字节的间隔上限", SSE 事件间隔
    (interval=0.01s) 远小于 READ_TIMEOUT_SECONDS, 流不被总长掐断.
    """
    import json

    request = ResolvedRequest(
        name="sse", method="GET", url=f"{testbed_url}/sse?count=5&interval=0.01"
    )
    events = _collect(Engine(), request, item_ref="demo/sse", env=None)

    chunks = [e for e in events if e["type"] == "chunk"]
    assert len(chunks) == 5
    assert [c["index"] for c in chunks] == [0, 1, 2, 3, 4]
    assert [json.loads(c["data"])["seq"] for c in chunks] == [0, 1, 2, 3, 4]

    done = events[-1]
    assert done["type"] == "done"
    assert done["status"] == 200
    assert "error" not in done


# --- TC-009: /delay/5 超内置读超时 -> 超时事件且不悬挂 (M3 D013) ---


def test_engine_read_timeout_event(testbed_url):
    """/delay/5 (服务端睡 5s) > READ_TIMEOUT_SECONDS (4s): done 带 TIMEOUT error,
    流正常收尾 (meta -> done, 无 chunk), 不悬挂."""
    import time

    request = ResolvedRequest(name="slow", method="GET", url=f"{testbed_url}/delay/5")
    start = time.monotonic()
    events = _collect(Engine(), request, item_ref="demo/slow", env=None)
    elapsed = time.monotonic() - start

    assert elapsed < 30  # 悬挂即慢到离谱; pytest-timeout=300 兜底
    done = events[-1]
    assert done["type"] == "done"
    assert done["status"] is None  # 响应头都没等到
    assert done["error"]["code"] == "TIMEOUT"
    assert not [e for e in events if e["type"] == "chunk"]


# --- TC-010: /large 超响应大小上限 -> 上限事件 (M3 D013) ---


def test_engine_response_too_large_event(testbed_url):
    """/large?bytes=6MB > MAX_RESPONSE_BYTES (5MB): done 带 RESPONSE_TOO_LARGE error,
    状态码已拿到 (响应头先到), 超限即中断读取."""
    request = ResolvedRequest(
        name="large",
        method="GET",
        url=f"{testbed_url}/large?bytes={6 * 1024 * 1024}",
    )
    events = _collect(Engine(), request, item_ref="demo/large", env=None)

    done = events[-1]
    assert done["type"] == "done"
    assert done["status"] == 200
    assert done["error"]["code"] == "RESPONSE_TOO_LARGE"


# --- 防挂钉死: 未知认证类型 (ISSUE-03 前置修复) ---


def test_engine_unknown_auth_type_raises_instead_of_hanging():
    """钉死防挂路径: 未知认证类型在 HTTP 段之前抛 ValueError.

    修复前 _run 的收尾 (done + 哨兵) 不在 finally 内, ValueError 使 task 静默死亡,
    execute() 的 queue.get() 永久阻塞 (pytest 挂起温床). 本测试限时断言:
    execute() 以 ValueError 返回而非挂起, 且 done 事件带 error 字段 (可观察).
    若防挂回归, wait_for 超时抛 TimeoutError, 测试快速失败而非无限挂起.
    """
    request = ResolvedRequest(
        name="bad-auth",
        method="GET",
        url="http://127.0.0.1:1/never-reached",  # 认证解析先于网络, 此地址不可达
        auth={"type": "hmac"},  # 不在五种认证内 (M1 D003)
    )

    async def main() -> list[dict]:
        events: list[dict] = []

        async def consume() -> None:
            async for event in Engine().execute(request, item_ref="demo/bad-auth", env=None):
                events.append(event)

        with pytest.raises(ValueError, match="未知认证类型"):
            await asyncio.wait_for(consume(), timeout=10)
        return events

    events = asyncio.run(main())
    done = events[-1]
    assert done["type"] == "done"
    assert "error" in done  # 异常路径 done 带 error, 失败可观察
