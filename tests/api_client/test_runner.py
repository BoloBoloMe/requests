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
from api_client.store import Item, Store
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
