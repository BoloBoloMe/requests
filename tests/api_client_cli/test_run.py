"""ISSUE-03: run 集合批量执行 (M4 D003 不吞 chunk + summary, D002 三形态).

接缝: fake /collections/{c}/run 回放 2 条目事件流 + summary + report; CLI subprocess.
"""

import json

from support import CLI_TOKEN, run_cli, stdout_json, stdout_ndjson, stderr_error


def _meta(item: str) -> dict:
    return {
        "type": "meta",
        "timestamp": "2024-01-15T09:12:00Z",
        "item_ref": item,
        "item": item,
        "method": "GET",
        "resolved_url": "http://localhost:9000/json",
        "env": "dev",
    }


def _chunk(item: str, data: str) -> dict:
    return {"type": "chunk", "timestamp": "2024-01-15T09:12:01Z", "item": item, "index": 0, "data": data}


def _done(item: str, passed: bool) -> dict:
    return {
        "type": "done",
        "timestamp": "2024-01-15T09:12:02Z",
        "item": item,
        "status": 200,
        "duration_ms": 12,
        "assertions": [{"name": "body.ok", "expected": True, "actual": passed, "passed": passed}],
    }


def _summary(total: int, passed: int, failed: int) -> dict:
    return {"type": "summary", "timestamp": "2024-01-15T09:12:03Z", "total": total, "passed": passed, "failed": failed, "items": []}


REPORT = {"type": "report", "format": "junit", "content": "<testsuite/>"}

PASS_STREAM = [_meta("demo/get-json"), _chunk("demo/get-json", '{"ok": true}'), _done("demo/get-json", True)]
FAIL_STREAM = [_meta("demo/failing"), _chunk("demo/failing", '{"ok": false}'), _done("demo/failing", False)]
MIXED_STREAM = PASS_STREAM + FAIL_STREAM + [_summary(2, 1, 1), REPORT]
ALL_PASS_STREAM = PASS_STREAM + [_summary(1, 1, 0), REPORT]


def _canned_run(fake_service, events, collection: str = "demo"):
    ndjson = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events)
    fake_service.add("POST", f"/collections/{collection}/run", 200, ndjson, "application/x-ndjson")


def test_run_emits_chunk_per_item_no_swallow(service_data_dir, fake_service):
    """每个条目完整 meta/chunk/done (不吞 chunk), 末尾 summary + report (TC-001, M4 D003)."""
    _canned_run(fake_service, MIXED_STREAM)
    proc = run_cli(["run", "demo"], service_data_dir)
    assert proc.returncode == 1  # summary.failed=1
    events = stdout_ndjson(proc)
    assert events == MIXED_STREAM
    # 失败条目响应体可直接从 run 输出定位 (不重放 send)
    fail_chunks = [e for e in events if e["type"] == "chunk" and e["item"] == "demo/failing"]
    assert fail_chunks and fail_chunks[0]["data"] == '{"ok": false}'
    assert events[-2]["type"] == "summary" and events[-1]["type"] == "report"


def test_run_all_pass_exit_0(service_data_dir, fake_service):
    """summary.failed=0 -> exit 0 (TC-002)."""
    _canned_run(fake_service, ALL_PASS_STREAM)
    proc = run_cli(["run", "demo"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_ndjson(proc) == ALL_PASS_STREAM


def test_run_request_body_and_token(service_data_dir, fake_service):
    """run 请求体携 collection/env/vars, 头带 X-Auth-Token (TC-003)."""
    _canned_run(fake_service, ALL_PASS_STREAM)
    proc = run_cli(["run", "demo", "--env", "dev", "--var", "host=localhost:9000"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    calls = fake_service.requests_to("/collections/demo/run")
    assert len(calls) == 1
    assert calls[0]["headers"].get("X-Auth-Token") == CLI_TOKEN
    assert json.loads(calls[0]["body"]) == {"collection": "demo", "env": "dev", "vars": {"host": "localhost:9000"}}


def test_run_output_json_is_full_event_array(service_data_dir, fake_service):
    """--output json: 事件数组含全部条目事件 + summary + report (TC-004)."""
    _canned_run(fake_service, MIXED_STREAM)
    proc = run_cli(["run", "demo", "--output", "json"], service_data_dir)
    assert proc.returncode == 1
    assert stdout_json(proc) == MIXED_STREAM


def test_run_output_pretty_lines_start_with_type(service_data_dir, fake_service):
    """--output pretty: 每行 type 开头 + JSON (TC-005)."""
    _canned_run(fake_service, ALL_PASS_STREAM)
    proc = run_cli(["run", "demo", "--output", "pretty"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == len(ALL_PASS_STREAM)
    for line, event in zip(lines, ALL_PASS_STREAM):
        assert line.startswith(event["type"] + " ")
        assert json.loads(line[len(event["type"]) + 1 :]) == event


def test_run_not_found_exit_4(service_data_dir, fake_service):
    """run 集合 404 -> exit 4 + stderr 错误 + candidates 兜底 (TC-006)."""
    fake_service.add("POST", "/collections/dem/run", 404, {"detail": "集合不存在: dem"})
    fake_service.add("GET", "/collections", 200, {"collections": ["demo"]})
    proc = run_cli(["run", "dem"], service_data_dir)
    assert proc.returncode == 4
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"] == "COLLECTION_NOT_FOUND"
    assert error["details"]["candidates"] == ["demo"]


def test_run_unresolved_variables_no_stream_exit_2(service_data_dir, fake_service):
    """run UNRESOLVED_VARIABLES -> exit 2, 无事件流 (TC-007, M4 D006)."""
    fake_service.add("POST", "/collections/demo/run", 422, {"detail": {"code": "UNRESOLVED_VARIABLES", "missing": ["host"]}})
    proc = run_cli(["run", "demo"], service_data_dir)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "UNRESOLVED_VARIABLES"


def test_run_service_error_exit_3(service_data_dir, fake_service):
    """run 持续 500 -> 重试一次后 SERVICE_ERROR exit 3 (TC-008)."""
    fake_service.add("POST", "/collections/demo/run", 500, {"detail": "boom"})
    proc = run_cli(["run", "demo"], service_data_dir)
    assert proc.returncode == 3
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "SERVICE_ERROR"
