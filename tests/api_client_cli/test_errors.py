"""ISSUE-02 TS-004/005/006: 错误映射 + 退出码 + candidates 纠错 + 未解析变量硬失败.

服务端错误两种形状都覆盖: 裁决形状 {"error":{code,message,details}} 透传;
FastAPI 兜底形状 {"detail": ...} 由 CLI 解析映射 (08 当前形状, 协调点).
"""

from support import FakeService, run_cli, stderr_error


def test_send_collection_not_found_passthrough_exit_4(service_data_dir, fake_service):
    """服务端 {"error":{...}} 带 details.candidates -> 原样透传 stderr, stdout 空, exit 4 (TC-006/TC-009)."""
    fake_service.add(
        "POST",
        "/execute",
        404,
        {"error": {"code": "COLLECTION_NOT_FOUND", "message": "集合不存在: dem", "details": {"candidates": ["demo"]}}},
    )
    proc = run_cli(["send", "dem/get-json"], service_data_dir)
    assert proc.returncode == 4
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"] == "COLLECTION_NOT_FOUND"
    assert error["message"] == "集合不存在: dem"
    assert error["details"]["candidates"] == ["demo"]


def test_send_service_error_retry_exhausted_exit_3(service_data_dir, fake_service):
    """/execute 持续 500 -> 重试一次后仍败 -> SERVICE_ERROR exit 3, stdout 空 (TC-007)."""
    fake_service.add("POST", "/execute", 500, {"detail": "boom"})
    proc = run_cli(["send", "demo/get-json"], service_data_dir)
    assert proc.returncode == 3
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "SERVICE_ERROR"
    assert len(fake_service.requests_to("/execute")) == 2, "5xx 应恰重试一次"


def test_send_unreachable_service_exit_3(service_data_dir, fake_service):
    """/execute 连接被对端持续断开 -> 重试一次后仍败 -> SERVICE_ERROR exit 3 (TC-007)."""
    def drop(handler):
        handler.connection.close()  # 不响应即断开: RemoteProtocolError

    fake_service.routes[("POST", "/execute")] = drop
    proc = run_cli(["send", "demo/get-json"], service_data_dir)
    assert proc.returncode == 3
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "SERVICE_ERROR"
    assert len(fake_service.requests_to("/execute")) == 2, "传输失败应恰重试一次"


def test_send_malformed_item_ref_usage_error(service_data_dir, fake_service):
    """畸形 item-ref (缺斜杠) -> USAGE_ERROR exit 2, 不发请求 (TC-008)."""
    proc = run_cli(["send", "noslash"], service_data_dir)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "USAGE_ERROR"
    assert fake_service.requests_to("/execute") == []


def test_send_malformed_var_usage_error(service_data_dir, fake_service):
    """--var 缺 '=' -> USAGE_ERROR exit 2, 不发请求 (TC-008 同类)."""
    proc = run_cli(["send", "demo/get-json", "--var", "novalue"], service_data_dir)
    assert proc.returncode == 2
    assert stderr_error(proc)["code"] == "USAGE_ERROR"
    assert fake_service.requests_to("/execute") == []


def test_send_not_found_client_candidates_fallback(service_data_dir, fake_service):
    """服务端无 candidates (FastAPI 形状) -> CLI 经清单端点 difflib+子串兜底 (TC-010)."""
    fake_service.add("POST", "/execute", 404, {"detail": "集合不存在: dem"})
    fake_service.add("GET", "/collections", 200, {"collections": ["demo", "billing"]})
    proc = run_cli(["send", "dem/get-json"], service_data_dir)
    assert proc.returncode == 4
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"] == "COLLECTION_NOT_FOUND"
    assert error["details"]["candidates"] == ["demo"]


def test_send_item_not_found_candidates_from_items(service_data_dir, fake_service):
    """条目 404 -> 经 item list 取 slug 清单, get-jsn 纠错出 get-json (TC-010, dogfood 场景)."""
    fake_service.add("POST", "/execute", 404, {"detail": "请求条目不存在: demo//get-jsn"})
    fake_service.add("GET", "/collections/demo/items", 200, {"items": [{"slug": "get-json"}, {"slug": "sse-stream"}]})
    proc = run_cli(["send", "demo/get-jsn"], service_data_dir)
    assert proc.returncode == 4
    error = stderr_error(proc)
    assert error["code"] == "ITEM_NOT_FOUND"
    assert error["details"]["candidates"] == ["get-json"]


def test_send_unresolved_variables_no_stream_exit_2(service_data_dir, fake_service):
    """UNRESOLVED_VARIABLES -> stderr 错误对象 + details.missing, 无事件流 (stdout 空), exit 2 (TC-011, M4 D006)."""
    fake_service.add("POST", "/execute", 422, {"detail": {"code": "UNRESOLVED_VARIABLES", "missing": ["host"]}})
    proc = run_cli(["send", "demo/get-json"], service_data_dir)
    assert proc.returncode == 2
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"] == "UNRESOLVED_VARIABLES"
    assert error["details"]["missing"] == ["host"]
