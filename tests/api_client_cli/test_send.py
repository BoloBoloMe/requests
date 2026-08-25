"""ISSUE-02: send 单请求执行 (M4 D002/D003/D004/D006).

接缝: fake service.json 指向 fake HTTP 服务回放 canned /execute; CLI subprocess.
"""

import json

from support import CLI_TOKEN, run_cli, stdout_json, stdout_ndjson

META = {
    "type": "meta",
    "timestamp": "2024-01-15T09:12:00Z",
    "item_ref": "demo/get-json",
    "item": "demo/get-json",
    "method": "GET",
    "resolved_url": "http://localhost:9000/json",
    "env": "dev",
}
CHUNK = {"type": "chunk", "timestamp": "2024-01-15T09:12:01Z", "item": "demo/get-json", "index": 0, "data": '{"hello": "world"}'}
DONE_OK = {
    "type": "done",
    "timestamp": "2024-01-15T09:12:02Z",
    "item": "demo/get-json",
    "status": 200,
    "duration_ms": 12,
    "assertions": [
        {"name": "status", "expected": 200, "actual": 200, "passed": True},
        {"name": "body.hello", "expected": "world", "actual": "world", "passed": True},
    ],
}
DONE_FAIL = {
    **DONE_OK,
    "assertions": [
        {"name": "status", "expected": 200, "actual": 200, "passed": True},
        {"name": "body.ok", "expected": True, "actual": False, "passed": False},
    ],
}


def _canned_execute(fake_service, events):
    ndjson = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events)
    fake_service.add("POST", "/execute", 200, ndjson, "application/x-ndjson")


def test_send_renders_ndjson_events_exit_0(service_data_dir, fake_service):
    """默认 ndjson: 输出恰为 meta/chunk/done 三条逐行事件 (字段逐字一致), exit 0 (TC-001)."""
    _canned_execute(fake_service, [META, CHUNK, DONE_OK])
    proc = run_cli(["send", "demo/get-json"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    assert stdout_ndjson(proc) == [META, CHUNK, DONE_OK]


def test_send_request_body_and_token(service_data_dir, fake_service):
    """请求体携带 collection/item/env/vars, 请求头带 X-Auth-Token (TC-002)."""
    _canned_execute(fake_service, [META, CHUNK, DONE_OK])
    proc = run_cli(
        ["send", "demo/get-json", "--env", "dev", "--var", "host=localhost:9000", "--var", "debug=1"],
        service_data_dir,
    )
    assert proc.returncode == 0, proc.stderr
    calls = fake_service.requests_to("/execute")
    assert len(calls) == 1
    assert calls[0]["headers"].get("X-Auth-Token") == CLI_TOKEN
    assert json.loads(calls[0]["body"]) == {
        "collection": "demo",
        "item": "get-json",
        "env": "dev",
        "vars": {"host": "localhost:9000", "debug": "1"},
    }


def test_send_assertion_failure_exit_1(service_data_dir, fake_service):
    """done.assertions 任一未通过 -> 事件流完整渲染 (stdout 有数据), exit 1 (TC-003)."""
    _canned_execute(fake_service, [META, CHUNK, DONE_FAIL])
    proc = run_cli(["send", "demo/get-json"], service_data_dir)
    assert proc.returncode == 1
    assert stdout_ndjson(proc) == [META, CHUNK, DONE_FAIL]
    assert proc.stderr == ""


def test_send_output_json_is_event_array(service_data_dir, fake_service):
    """--output json: 收集为事件数组 (含全部事件) (TC-004)."""
    _canned_execute(fake_service, [META, CHUNK, DONE_OK])
    proc = run_cli(["send", "demo/get-json", "--output", "json"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == [META, CHUNK, DONE_OK]


def test_send_output_pretty_lines_start_with_type(service_data_dir, fake_service):
    """--output pretty: 每行以事件 type 开头 + 完整 JSON (字段值 JSON 渲染, 禁 repr) (TC-005)."""
    _canned_execute(fake_service, [META, CHUNK, DONE_OK])
    proc = run_cli(["send", "demo/get-json", "--output", "pretty"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 3
    for line, event in zip(lines, [META, CHUNK, DONE_OK]):
        assert line.startswith(event["type"] + " ")
        assert json.loads(line[len(event["type"]) + 1 :]) == event
    # chunk.data 为合法 JSON 字符串渲染 (非 repr 单引号)
    chunk_line = lines[1]
    assert "'" not in chunk_line
