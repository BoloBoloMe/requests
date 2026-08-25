"""ISSUE-03 TS-004: history list/show 非流式查询 (M4 D002 单 JSON, M3 D010).

接缝: fake GET /history 回列表, GET /history/{id} 回单条; CLI subprocess.
"""

from support import run_cli, stderr_error, stdout_json

ENTRIES = [
    {
        "id": "h-002",
        "item_ref": "demo/failing",
        "env": "dev",
        "status": 200,
        "started_at": "2024-01-15T09:13:00Z",
        "duration_ms": 8,
        "assertions_passed": 1,
        "assertions_failed": 1,
    },
    {
        "id": "h-001",
        "item_ref": "demo/get-json",
        "env": "dev",
        "status": 200,
        "started_at": "2024-01-15T09:12:00Z",
        "duration_ms": 12,
        "assertions_passed": 2,
        "assertions_failed": 0,
    },
]


def test_history_list_renders_json_array(service_data_dir, fake_service):
    """history list 默认单 JSON 数组, 条目含 id/item_ref/status/started_at/duration_ms (TC-009)."""
    fake_service.add("GET", "/history", 200, ENTRIES)
    proc = run_cli(["history", "list"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    payload = stdout_json(proc)
    assert payload == ENTRIES
    for entry in payload:
        for field in ("id", "item_ref", "status", "started_at", "duration_ms"):
            assert field in entry


def test_history_show_renders_single_object(service_data_dir, fake_service):
    """history show <id> 输出单 JSON 对象 (TC-010)."""
    fake_service.add("GET", "/history/h-001", 200, ENTRIES[1])
    proc = run_cli(["history", "show", "h-001"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == ENTRIES[1]


def test_history_show_not_found_exit_4(service_data_dir, fake_service):
    """不存在的 id -> 404 -> exit 4 + stderr 错误, stdout 空 (TC-011)."""
    fake_service.add("GET", "/history/h-999", 404, {"detail": "历史条目不存在: h-999"})
    proc = run_cli(["history", "show", "h-999"], service_data_dir)
    assert proc.returncode == 4
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"].endswith("NOT_FOUND")


def test_history_list_output_ndjson_single_line(service_data_dir, fake_service):
    """非流式 ndjson 等同 json 单行 (M4 D002)."""
    fake_service.add("GET", "/history", 200, ENTRIES)
    proc = run_cli(["history", "list", "--output", "ndjson"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.splitlines()) == 1
    assert stdout_json(proc) == ENTRIES
