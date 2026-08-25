"""ISSUE-04 TS-001/TS-004: collection/item/env list/show 渲染 + pretty 回退 (M4 D001/D002).

接缝: fake HTTP 回放 REST 端点 canned 响应; CLI subprocess.
CLI 透传服务端响应体渲染 (薄壳, 不做形状变换).
"""

from support import run_cli, stderr_error, stdout_json

COLLECTIONS = [
    {"ref": "demo", "name": "Demo Collection", "item_count": 3},
    {"ref": "billing", "name": "Billing", "item_count": 5},
]
COLLECTION_CONFIG = {"vars": {"host": "localhost:9000"}, "defaults": {"auth": None, "headers": []}}
ITEMS = [
    {"ref": "demo/get-json", "method": "GET", "url": "http://{{host}}/json"},
    {"ref": "demo/sse-stream", "method": "GET", "url": "http://{{host}}/stream"},
]
ITEM = {"name": "get-json", "method": "GET", "url": "http://{{host}}/json", "assert": [{"status": 200}]}
ENVS = [{"name": "dev"}, {"name": "prod"}]
ENV = {"name": "dev", "vars": {"host": "localhost:9000"}, "secrets": {}, "merged": {"host": "localhost:9000"}}


def test_collection_list_renders_json_array(service_data_dir, fake_service):
    """collection list 输出单 JSON 数组 (ref/name/item_count) (TC-001)."""
    fake_service.add("GET", "/collections", 200, COLLECTIONS)
    proc = run_cli(["collection", "list"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == COLLECTIONS


def test_collection_show_renders_single_object(service_data_dir, fake_service):
    """collection show <ref> 输出单 JSON 对象 (TC-001)."""
    fake_service.add("GET", "/collections/demo/collection", 200, COLLECTION_CONFIG)
    proc = run_cli(["collection", "show", "demo"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == COLLECTION_CONFIG


def test_item_list_renders_json_array(service_data_dir, fake_service):
    """item list <c> 输出 ref/method/url 数组 (TC-002)."""
    fake_service.add("GET", "/collections/demo/items", 200, ITEMS)
    proc = run_cli(["item", "list", "demo"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == ITEMS


def test_item_show_renders_single_object(service_data_dir, fake_service):
    """item show <item-ref> 输出单 JSON 对象 (TC-002)."""
    fake_service.add("GET", "/collections/demo/items/get-json", 200, ITEM)
    proc = run_cli(["item", "show", "demo/get-json"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == ITEM


def test_env_list_and_show(service_data_dir, fake_service):
    """env list 输出数组; env show <name> 输出单对象 (TC-003)."""
    fake_service.add("GET", "/environments", 200, ENVS)
    fake_service.add("GET", "/environments/dev", 200, ENV)
    proc = run_cli(["env", "list"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == ENVS
    proc = run_cli(["env", "show", "dev"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == ENV


def test_item_show_not_found_exit_4_with_candidates(service_data_dir, fake_service):
    """不存在资源 -> 404 -> exit 4 + stderr 错误 + candidates 兜底 (TC-004)."""
    fake_service.add("GET", "/collections/demo/items/get-jsn", 404, {"detail": "请求条目不存在"})
    fake_service.add("GET", "/collections/demo/items", 200, {"items": [{"slug": "get-json"}, {"slug": "sse-stream"}]})
    proc = run_cli(["item", "show", "demo/get-jsn"], service_data_dir)
    assert proc.returncode == 4
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"] == "ITEM_NOT_FOUND"
    assert error["details"]["candidates"] == ["get-json"]


def test_env_show_not_found_exit_4(service_data_dir, fake_service):
    """env show 不存在 -> ENV_NOT_FOUND exit 4 (TC-004)."""
    fake_service.add("GET", "/environments/stag", 404, {"detail": "环境不存在"})
    fake_service.add("GET", "/environments", 200, {"environments": [{"name": "dev"}, {"name": "stage"}]})
    proc = run_cli(["env", "show", "stag"], service_data_dir)
    assert proc.returncode == 4
    error = stderr_error(proc)
    assert error["code"] == "ENV_NOT_FOUND"
    assert error["details"]["candidates"] == ["stage"]


def test_resources_pretty_falls_back_json(service_data_dir, fake_service):
    """非流式 --output pretty 可回退 JSON (值 JSON 渲染, M4 明示残留) (TC-009)."""
    fake_service.add("GET", "/collections", 200, COLLECTIONS)
    proc = run_cli(["collection", "list", "--output", "pretty"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == COLLECTIONS  # 回退形态仍是合法 JSON
