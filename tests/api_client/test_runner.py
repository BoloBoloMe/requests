"""ISSUE-05: Runner 批量运行 + JUnit 报告 (M3 D008/D013, M4 D003, M2 D011).

TS-001 接缝: runner.run_collection(store, engine, collection) -> Run (异步迭代出
事件流), 打 testbed 真 HTTP (D014-2, 不 mock httpx).
TS-002 接缝: runner.junit_xml(results) -> str 纯函数.
TS-003 接缝: TestClient 薄测 POST /collections/{c}/run (协商/404/401).

3 条目集合: echo 通过 / status-404 断言失败 / bearer 通过 (seq 定序).
统计口径: passed/failed 按断言 ok 计数 (断言失败或传输失败计 failed,
ISSUE-10 CLI 消费 summary 时同口径).
"""

import asyncio
import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from api_client.engine import Engine
from api_client.runner import junit_xml, run_collection
from api_client.store import CollectionConfig, Item, KV, Store
from api_client.web.app import create_app

TOKEN = "test-token"


def _write_three_item_collection(data_dir, testbed_url) -> None:
    """echo (断言 200 通过) / missing (status/404 断言 200 失败) / bearer (通过)."""
    store = Store(data_dir)
    store.write_item(
        "demo",
        "echo",
        Item(
            name="echo",
            method="GET",
            url=f"{testbed_url}/echo?hello=world",
            seq=1,
            assertions=[{"target": "status", "op": "eq", "expect": 200}],
        ),
    )
    store.write_item(
        "demo",
        "missing",
        Item(
            name="missing",
            method="GET",
            url=f"{testbed_url}/status/404",
            seq=2,
            assertions=[{"target": "status", "op": "eq", "expect": 200}],
        ),
    )
    store.write_item(
        "demo",
        "bearer",
        Item(
            name="bearer",
            method="GET",
            url=f"{testbed_url}/auth/bearer",
            seq=3,
            auth={"type": "bearer", "token": "demo-token"},
            assertions=[{"target": "status", "op": "eq", "expect": 200}],
        ),
    )


def _collect(run) -> list[dict]:
    """同步包装: 排干批量事件流."""

    async def main() -> list[dict]:
        return [event async for event in run]

    return asyncio.run(main())


def _run_events(tmp_path, testbed_url) -> list[dict]:
    _write_three_item_collection(tmp_path, testbed_url)
    store = Store(tmp_path)
    return _collect(run_collection(store, Engine(store), "demo"))


# --- TS-001 TC-001/TC-004: 完整事件流, 顺序执行, 不吞 chunk ---


def test_runner_emits_full_events_per_item_no_chunk_swallow(tmp_path, testbed_url):
    """事件序 = meta/chunk/done x3 + summary, 按 seq 顺序执行; 失败条目响应体
    在 run 事件流中可完整定位 (M4 D003 不吞 chunk, 禁止要求重放 send)."""
    events = _run_events(tmp_path, testbed_url)
    assert [e["type"] for e in events] == ["meta", "chunk", "done"] * 3 + ["summary"]

    # 顺序执行 (M3 D013): meta 按 seq 序, 时间戳非递减 (条目 2 不早于条目 1)
    metas = [e for e in events if e["type"] == "meta"]
    assert [m["item"] for m in metas] == ["demo/echo", "demo/missing", "demo/bearer"]
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)

    # 不吞 chunk: 三条目响应体全部可定位, 失败条目含 testbed /status/404 响应体
    chunks = {e["item"]: e["data"] for e in events if e["type"] == "chunk"}
    assert set(chunks) == {"demo/echo", "demo/missing", "demo/bearer"}
    assert json.loads(chunks["demo/missing"]) == {"status": 404}
    assert "hello=world" in chunks["demo/echo"]


# --- TS-001 TC-002: 断言失败不中断后续条目 ---


def test_runner_assert_failure_does_not_interrupt(tmp_path, testbed_url):
    """中间条目断言失败 (done.status == "assert_failed"), 后续条目照常执行."""
    events = _run_events(tmp_path, testbed_url)
    dones = [e for e in events if e["type"] == "done"]
    assert [d["item"] for d in dones] == ["demo/echo", "demo/missing", "demo/bearer"]
    assert dones[0]["status"] == 200
    assert dones[1]["status"] == "assert_failed"
    assert dones[2]["status"] == 200


# --- TS-001 TC-003: summary 统计与断言结果一致 ---


def test_runner_summary_counts_match_assertions(tmp_path, testbed_url):
    """summary: total=3, passed=2, failed=1 (口径: 按断言 ok 计数);
    items 逐条带 item/status/passed, 与 done 事件一致."""
    events = _run_events(tmp_path, testbed_url)
    summary = events[-1]
    assert summary["type"] == "summary"
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["items"] == [
        {"item": "demo/echo", "status": 200, "passed": True},
        {"item": "demo/missing", "status": "assert_failed", "passed": False},
        {"item": "demo/bearer", "status": 200, "passed": True},
    ]


# --- TS-002 TC-005/006/007: JUnit 报告可解析且结构类 pytest --junitxml ---


def test_junit_report_parseable_and_structured(tmp_path, testbed_url):
    """junit_xml(results): xml.etree 可解析; testsuite 属性 tests/failures/errors/time,
    testcase 带 name/classname/time, 失败条目含 failure (消息=断言消息), 通过条目无."""
    _write_three_item_collection(tmp_path, testbed_url)
    store = Store(tmp_path)
    run = run_collection(store, Engine(store), "demo")
    _collect(run)
    report = junit_xml(run.results, suite_name="demo")

    # TC-005: 可被 xml.etree 解析
    root = ET.fromstring(report)

    # TC-006/TC-007: 结构类 pytest --junitxml
    assert root.tag == "testsuite"
    assert root.get("tests") == "3"
    assert root.get("failures") == "1"
    assert root.get("errors") == "0"
    assert float(root.get("time")) >= 0.0

    cases = root.findall("testcase")
    assert len(cases) == 3
    assert [c.get("name") for c in cases] == ["echo", "missing", "bearer"]
    assert all(c.get("classname") == "demo" for c in cases)
    assert all(float(c.get("time")) >= 0.0 for c in cases)

    # 失败条目: failure 元素消息 = 断言消息 (status eq 200 实际 404 -> "期望 200")
    failure = cases[1].find("failure")
    assert failure is not None
    assert "200" in failure.get("message")
    # 通过条目无 failure
    assert cases[0].find("failure") is None
    assert cases[2].find("failure") is None


# --- 返工 1 [重要]: 单条目意外异常不中断整批 (D-AFK-009) ---


def test_runner_unexpected_item_error_does_not_interrupt(tmp_path, testbed_url):
    """3 条目中第 2 条 auth.type 非法 (Engine 抛 ValueError): 该条记失败
    (done.status=null + error.code=UNEXPECTED_ERROR, 与既有 error.code 词汇一致),
    后续第 3 条照常执行, 事件流仍含 x3 done + summary 正常收尾."""
    _write_three_item_collection(tmp_path, testbed_url)
    store = Store(tmp_path)
    # 覆盖第 2 条为非法认证类型: resolve 不校验 auth.type, 异常在执行段爆发
    store.write_item(
        "demo",
        "missing",
        Item(
            name="bad-auth",
            method="GET",
            url=f"{testbed_url}/echo",
            seq=2,
            auth={"type": "hmac"},  # 不在五种认证内 (M1 D003)
        ),
    )
    run = run_collection(store, Engine(store), "demo")
    events = _collect(run)

    # 第 2 条无 chunk (认证解析先于网络), 其余条目事件完整
    assert [e["type"] for e in events] == [
        "meta", "chunk", "done",
        "meta", "done",
        "meta", "chunk", "done",
        "summary",
    ]
    dones = [e for e in events if e["type"] == "done"]
    assert dones[1]["status"] is None
    assert dones[1]["error"]["code"] == "UNEXPECTED_ERROR"
    # 第 3 条照常执行
    assert dones[2]["status"] == 200

    summary = events[-1]
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["items"][1] == {"item": "demo/missing", "status": None, "passed": False}

    # JUnit 口径: status=null 计 errors (与传输失败同口径)
    root = ET.fromstring(junit_xml(run.results, suite_name="demo"))
    assert root.get("tests") == "3"
    assert root.get("errors") == "1"
    assert root.get("failures") == "0"


# --- 返工 2: JUnit errors 分支 (传输失败条目 -> <error>, 不进 failures) ---


def test_junit_transmission_failure_counts_as_error(tmp_path):
    """指向不存在端口的条目 (连接拒绝, done.status=null): testsuite errors=1
    且该 testcase 含 <error> 元素, failures=0 且无 <failure>."""
    store = Store(tmp_path)
    store.write_item(
        "demo",
        "down",
        Item(name="down", method="GET", url="http://127.0.0.1:1/never-reached", seq=1),
    )
    run = run_collection(store, Engine(store), "demo")
    events = _collect(run)
    done = next(e for e in events if e["type"] == "done")
    assert done["status"] is None  # 传输失败三态钉死

    root = ET.fromstring(junit_xml(run.results, suite_name="demo"))
    assert root.get("tests") == "1"
    assert root.get("errors") == "1"
    assert root.get("failures") == "0"
    case = root.find("testcase")
    assert case.find("error") is not None
    assert case.find("failure") is None


# --- 返工 3: SSE 路径 report 帧内容可解析 ---


def _parse_sse_frames(text: str) -> list[tuple[str, str]]:
    """SSE 文本 -> [(event, data)] 帧列表 (data 多行以 \\n 连接)."""
    frames: list[tuple[str, str]] = []
    for block in text.split("\n\n"):
        event, data_lines = "", []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip(" "))
        if event:
            frames.append((event, "\n".join(data_lines)))
    return frames


def test_run_sse_report_frame_xml_parseable(tmp_path, testbed_url):
    """SSE 事件流末尾 report 帧: data 中 XML 可被 xml.etree 解析 (NDJSON 已覆盖)."""
    _write_three_item_collection(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run",
        headers={**_auth(), "Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    frames = _parse_sse_frames(response.text)
    event, data = frames[-1]
    assert event == "report"
    report = json.loads(data)
    assert report["format"] == "junit"
    root = ET.fromstring(report["content"])
    assert root.tag == "testsuite"
    assert root.get("tests") == "3"


# --- 返工 4: ?env= 与缺省激活环境 ---


def _write_env_collection(data_dir, testbed_url) -> None:
    """单条目集合: header X-Token 插值 {{token}}, 由环境变量供值."""
    store = Store(data_dir)
    store.write_item(
        "demo",
        "echo",
        Item(
            name="echo",
            method="GET",
            url=f"{testbed_url}/echo",
            seq=1,
            headers=[KV(key="X-Token", value="{{token}}")],
        ),
    )
    store.write_environment("dev", {"token": "dev-secret"})
    store.write_environment("prod", {"token": "prod-secret"})


def test_run_env_param_overrides_active(tmp_path, testbed_url):
    """?env=prod 指定环境生效 (激活为 dev): 实际发送 header 取 prod 变量值."""
    _write_env_collection(tmp_path, testbed_url)
    Store(tmp_path).set_active_environment("dev")
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run?env=prod",
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["env"] == "prod"
    chunk = next(e for e in events if e["type"] == "chunk")
    assert json.loads(chunk["data"])["headers"]["x-token"] == "prod-secret"


def test_run_default_uses_active_environment(tmp_path, testbed_url):
    """env_name 缺省读激活环境 (M2 D007): meta.env 为激活名, header 取其变量值."""
    _write_env_collection(tmp_path, testbed_url)
    store = Store(tmp_path)
    store.set_active_environment("dev")
    events = _collect(run_collection(store, Engine(store), "demo"))
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["env"] == "dev"
    chunk = next(e for e in events if e["type"] == "chunk")
    assert json.loads(chunk["data"])["headers"]["x-token"] == "dev-secret"


# --- D-AFK-011: 请求体 {env?, vars?} (M10 契约): vars 覆盖层最高优先, body env 优先于 query ---


def test_run_vars_override_env(tmp_path, testbed_url):
    """请求体 vars 覆盖环境同名字段 (D-AFK-011): 实际发送 header 取覆盖值.
    同时覆盖 run_collection 直连接缝的 vars 透传."""
    _write_env_collection(tmp_path, testbed_url)
    Store(tmp_path).set_active_environment("dev")

    # 直连接缝: run_collection(vars=...)
    events = _collect(
        run_collection(Store(tmp_path), Engine(Store(tmp_path)), "demo", vars={"token": "once-direct"})
    )
    chunk = next(e for e in events if e["type"] == "chunk")
    assert json.loads(chunk["data"])["headers"]["x-token"] == "once-direct"

    # HTTP 接缝: 请求体 vars
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run?env=dev",
        json={"vars": {"token": "once-token"}},
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    chunk = next(e for e in events if e["type"] == "chunk")
    assert json.loads(chunk["data"])["headers"]["x-token"] == "once-token"


def test_run_body_env_overrides_query(tmp_path, testbed_url):
    """请求体 env 优先于 ?env= query (兼容保留 query): body prod 胜 query dev."""
    _write_env_collection(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run?env=dev",
        json={"env": "prod"},
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["env"] == "prod"
    chunk = next(e for e in events if e["type"] == "chunk")
    assert json.loads(chunk["data"])["headers"]["x-token"] == "prod-secret"


def test_run_vars_invalid_shape_422(tmp_path, testbed_url):
    """vars 形状非法 (非 dict / 值非 str) -> 422, 不产生事件流."""
    _write_env_collection(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    for bad_vars in (["not-a-dict"], {"token": 1}):
        response = client.post(
            "/collections/demo/run",
            json={"vars": bad_vars},
            headers=_auth(),
        )
        assert response.status_code == 422, bad_vars


# --- 返工 5: 空集合 run 钉死 (200 + 空 summary/testsuite, 不 404) ---


def test_run_empty_collection_returns_empty_summary(tmp_path):
    """空集合 run: 200, 事件流仅 summary + report; summary total=0,
    testsuite tests=0 且无 testcase (行为钉死, 此时不 404)."""
    Store(tmp_path).write_collection("empty", CollectionConfig())
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/empty/run",
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert [e["type"] for e in events] == ["summary", "report"]
    summary = events[0]
    assert summary["total"] == 0
    assert summary["passed"] == 0
    assert summary["failed"] == 0
    assert summary["items"] == []
    root = ET.fromstring(events[1]["content"])
    assert root.get("tests") == "0"
    assert root.get("failures") == "0"
    assert root.get("errors") == "0"
    assert root.findall("testcase") == []


# --- TS-003 TC-008/009: run API 薄壳 (协商/report 事件/404/401) ---


def _auth() -> dict[str, str]:
    # Host 白名单中间件要求回环 Host (同 test_execute_api 惯例)
    return {"X-Auth-Token": TOKEN, "Host": "localhost"}


def test_run_ends_with_report_event(tmp_path, testbed_url):
    """NDJSON: 事件流 = meta/chunk/done x3 + summary + report (format=junit,
    content 为可解析 XML)."""
    _write_three_item_collection(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run",
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert [e["type"] for e in events] == ["meta", "chunk", "done"] * 3 + [
        "summary",
        "report",
    ]
    report = events[-1]
    assert report["format"] == "junit"
    root = ET.fromstring(report["content"])
    assert root.tag == "testsuite"
    assert root.get("tests") == "3"
    assert root.get("failures") == "1"


def test_run_negotiates_sse_by_accept(tmp_path, testbed_url):
    """Accept: text/event-stream -> SSE 帧, 同一事件模型 (含 report 帧)."""
    _write_three_item_collection(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run",
        headers={**_auth(), "Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    event_types = [
        line[len("event:"):].strip()
        for line in response.text.splitlines()
        if line.startswith("event:")
    ]
    assert event_types == ["meta", "chunk", "done"] * 3 + ["summary", "report"]


def test_run_unknown_collection_404(tmp_path, testbed_url):
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post("/collections/nope/run", headers=_auth())
    assert response.status_code == 404


def test_run_requires_token_401(tmp_path):
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post("/collections/demo/run", headers={"Host": "localhost"})
    assert response.status_code == 401


# --- G1: 未解析变量条目跳过 (不再整批 exit 2; send 单条硬失败不变) ---


def _write_skip_collection(data_dir, testbed_url) -> None:
    """echo (通过) / unresolved (URL 残留 {{nope}}, 跳过) / missing (断言失败)."""
    store = Store(data_dir)
    store.write_item(
        "demo",
        "echo",
        Item(
            name="echo",
            method="GET",
            url=f"{testbed_url}/echo?hello=world",
            seq=1,
            assertions=[{"target": "status", "op": "eq", "expect": 200}],
        ),
    )
    store.write_item(
        "demo",
        "unresolved",
        Item(
            name="unresolved",
            method="GET",
            url=f"{testbed_url}/echo?x={{{{nope}}}}",
            seq=2,
            assertions=[{"target": "status", "op": "eq", "expect": 200}],
        ),
    )
    store.write_item(
        "demo",
        "missing",
        Item(
            name="missing",
            method="GET",
            url=f"{testbed_url}/status/404",
            seq=3,
            assertions=[{"target": "status", "op": "eq", "expect": 200}],
        ),
    )


def test_runner_unresolved_item_skipped_not_fatal(tmp_path, testbed_url):
    """G1: 未解析变量条目跳过 (无 meta/chunk, 合成 done status=null +
    error.code=UNRESOLVED_VARIABLES), 其余条目照常; summary total=3
    passed=1 failed=2; JUnit errors 计该条目."""
    _write_skip_collection(tmp_path, testbed_url)
    store = Store(tmp_path)
    run = run_collection(store, Engine(store), "demo")
    events = _collect(run)

    # 事件序: echo 完整 meta/chunk/done, unresolved 仅 done, missing 完整三事件
    assert [e["type"] for e in events] == [
        "meta", "chunk", "done",  # echo
        "done",  # unresolved (跳过, 不发 HTTP)
        "meta", "chunk", "done",  # missing
        "summary",
    ]
    skipped = events[3]
    assert skipped["item"] == "demo/unresolved"
    assert skipped["status"] is None
    assert skipped["duration_ms"] == 0
    assert skipped["assertions"] == []
    assert skipped["error"]["code"] == "UNRESOLVED_VARIABLES"
    assert "nope" in skipped["error"]["message"]

    summary = events[-1]
    assert (summary["total"], summary["passed"], summary["failed"]) == (3, 1, 2)
    assert summary["items"][1] == {
        "item": "demo/unresolved",
        "status": None,
        "passed": False,
    }

    # JUnit: skipped 计入 errors (status=None 口径), missing 计入 failures
    root = ET.fromstring(junit_xml(run.results, suite_name="demo"))
    assert root.get("tests") == "3"
    assert root.get("failures") == "1"
    assert root.get("errors") == "1"
    cases = root.findall("testcase")
    assert [c.get("name") for c in cases] == ["echo", "unresolved", "missing"]
    assert cases[1].find("error") is not None


def test_run_api_unresolved_item_returns_200_stream(tmp_path, testbed_url):
    """G1 API 面: 未解析变量条目不再 422 整批硬失败, 200 出流 (CLI exit 1
    由 event_failed 对 done.error/summary.failed 自动生效)."""
    _write_skip_collection(tmp_path, testbed_url)
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run",
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert events[-2]["type"] == "summary"
    assert (events[-2]["total"], events[-2]["failed"]) == (3, 2)
    skipped = [e for e in events if e.get("error", {}).get("code") == "UNRESOLVED_VARIABLES"]
    assert len(skipped) == 1 and skipped[0]["item"] == "demo/unresolved"
    # report 仍正常收尾 (跳过不中断整批)
    assert events[-1]["type"] == "report"


def test_run_all_unresolved_items_still_streams(tmp_path, testbed_url):
    """G1 边界: 全部条目未解析 -> 仍出事件流 (每条目一个 done) + summary/report,
    不 422 (整批跳过语义, 非硬失败)."""
    store = Store(tmp_path)
    store.write_item(
        "demo",
        "bad",
        Item(name="bad", method="GET", url="{{nope}}/x", seq=1, assertions=[]),
    )
    client = TestClient(create_app(TOKEN, data_dir=tmp_path))
    response = client.post(
        "/collections/demo/run",
        headers={**_auth(), "Accept": "application/x-ndjson"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert [e["type"] for e in events] == ["done", "summary", "report"]
    assert events[0]["error"]["code"] == "UNRESOLVED_VARIABLES"
    assert events[1]["failed"] == 1
