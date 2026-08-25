"""ISSUE-04: Assert 解释器 (M6 决策 1/2/3, M1 D008, M4 D003).

接缝: assertions.evaluate(response, assertions) -> list[Result] 纯函数 (D014-1,
不起服务不打网络); TS-003 为 execute 路由 + testbed 真响应集成.
"""

import pytest

from api_client.assertions import Response, evaluate


def _json_response(body: str, status: int = 200) -> Response:
    return Response(
        status=status,
        headers={"Content-Type": "application/json"},
        body_text=body,
        elapsed_ms=12.0,
    )


# --- TS-001 / TC-005: 非 JSON 体降级, 报错文案区分 (M6 决策 3) ---


def test_non_json_body_path_error_message_distinct():
    """先写的失败测试: 原型中两案混为一句 "target 解析失败", 重写须区分 (决策 3 实现注意).

    非 JSON 体的 body.<路径> -> "体非 JSON 不可取路径";
    JSON 体路径不存在 -> "路径不存在". 两句文案必须可区分.
    """
    plain = Response(status=200, headers={}, body_text="plain text", elapsed_ms=1.0)
    (non_json,) = evaluate(plain, [{"target": "body.foo", "op": "eq", "expect": "x"}])
    assert non_json.ok is False
    assert "体非 JSON" in non_json.message

    (missing,) = evaluate(_json_response('{"a": 1}'), [{"target": "body.foo", "op": "eq", "expect": 1}])
    assert missing.ok is False
    assert "路径不存在" in missing.message
    assert "体非 JSON" not in missing.message  # 两案文案不得混用


# --- TS-001 / TC-001: op 十种全覆盖 (M6 决策 1) ---


def _first(response: Response, assertion: dict):
    (result,) = evaluate(response, [assertion])
    return result


def test_ops_eq_ne():
    resp = _json_response('{"n": 3}')
    assert _first(resp, {"target": "body.n", "op": "eq", "expect": 3}).ok is True
    neq = _first(resp, {"target": "body.n", "op": "eq", "expect": 4})
    assert neq.ok is False and neq.actual == 3
    assert _first(resp, {"target": "body.n", "op": "ne", "expect": 4}).ok is True
    assert _first(resp, {"target": "body.n", "op": "ne", "expect": 3}).ok is False


def test_ops_numeric_comparison():
    resp = _json_response('{"n": 3}')
    assert _first(resp, {"target": "body.n", "op": "lt", "expect": 4}).ok is True
    assert _first(resp, {"target": "body.n", "op": "lt", "expect": 3}).ok is False
    assert _first(resp, {"target": "body.n", "op": "lte", "expect": 3}).ok is True
    assert _first(resp, {"target": "body.n", "op": "gt", "expect": 2}).ok is True
    assert _first(resp, {"target": "body.n", "op": "gt", "expect": 3}).ok is False
    assert _first(resp, {"target": "body.n", "op": "gte", "expect": 3}).ok is True


def test_numeric_comparison_rejects_bool():
    """bool 是 int 子类: True >= 1 是伪通过, 数值比较须拒布尔并说明原因."""
    resp = _json_response('{"flag": true}')
    result = _first(resp, {"target": "body.flag", "op": "gte", "expect": 1})
    assert result.ok is False
    assert "非数值" in result.message


def test_ops_contains_not_contains():
    resp = _json_response('{"tags": ["a", "b"], "s": "hello world"}')
    assert _first(resp, {"target": "body.tags", "op": "contains", "expect": "a"}).ok is True
    assert _first(resp, {"target": "body.tags", "op": "contains", "expect": "z"}).ok is False
    assert _first(resp, {"target": "body.s", "op": "not_contains", "expect": "z"}).ok is True
    assert _first(resp, {"target": "body.s", "op": "not_contains", "expect": "world"}).ok is False


def test_op_matches_regex():
    resp = _json_response('{"s": "abc-123"}')
    assert _first(resp, {"target": "body.s", "op": "matches", "expect": r"^[a-z]+-\d+$"}).ok is True
    assert _first(resp, {"target": "body.s", "op": "matches", "expect": r"^\d+$"}).ok is False


def test_unknown_op_fails_with_message():
    resp = _json_response('{"n": 1}')
    result = _first(resp, {"target": "body.n", "op": "approx", "expect": 1})
    assert result.ok is False
    assert "未知 op" in result.message


# --- TS-001 / TC-002: target 五类 (M6 决策 1) ---


def test_target_status_and_elapsed_ms():
    resp = Response(status=201, headers={}, body_text="{}", elapsed_ms=42.5)
    assert _first(resp, {"target": "status", "op": "eq", "expect": 201}).ok is True
    assert _first(resp, {"target": "elapsed_ms", "op": "lt", "expect": 100}).ok is True


def test_target_header_case_insensitive():
    """header.<名> 大小写不敏感: 定义小写名, 响应头原名大小写任意."""
    resp = Response(
        status=200,
        headers={"Content-Type": "application/json; charset=utf-8"},
        body_text="{}",
        elapsed_ms=1.0,
    )
    result = _first(resp, {"target": "header.content-type", "op": "contains", "expect": "json"})
    assert result.ok is True
    assert result.actual == "application/json; charset=utf-8"


def test_target_body_and_jmespath():
    """body = 整体体; body.<jmespath> 嵌套取值."""
    resp = _json_response('{"user": {"name": "ada", "tags": ["x"]}}')
    whole = _first(resp, {"target": "body", "op": "contains", "expect": "user"})
    assert whole.ok is True and whole.actual == {"user": {"name": "ada", "tags": ["x"]}}
    nested = _first(resp, {"target": "body.user.name", "op": "eq", "expect": "ada"})
    assert nested.ok is True and nested.actual == "ada"
    deep = _first(resp, {"target": "body.user.tags[0]", "op": "eq", "expect": "x"})
    assert deep.ok is True


# --- TS-001 / TC-003: schema 整体校验 (jsonschema.validate) ---


def test_schema_validation_pass_and_fail():
    resp = _json_response('{"id": 7, "content": "hi"}')
    schema = {
        "type": "object",
        "required": ["id", "content"],
        "properties": {"id": {"type": "integer"}, "content": {"type": "string"}},
    }
    assert _first(resp, {"target": "body", "schema": schema}).ok is True

    bad = _first(resp, {"target": "body", "schema": {**schema, "required": ["id", "missing"]}})
    assert bad.ok is False
    assert "missing" in bad.message  # 失败取 jsonschema 校验消息


# --- TS-001 / TC-004: exists 无 expect ---


def test_op_exists_without_expect():
    """exists 不需要 expect: 路径在即过, 不在即败 (路径不存在)."""
    resp = _json_response('{"a": {"b": null}, "n": 0}')
    assert _first(resp, {"target": "body.n", "op": "exists"}).ok is True
    missing = _first(resp, {"target": "body.zzz", "op": "exists"})
    assert missing.ok is False and "路径不存在" in missing.message


# --- TS-002 / TC-006-009: Python 逃生舱 (M6 决策 1, exec 无沙箱) ---

def test_python_assert_error_classification():
    """先写的失败测试: AssertionError = 断言失败 (取消息), 其他异常 = 错误 (类型+消息)."""
    resp = _json_response('{"id": 3}', status=201)

    failure = _first(resp, {"python": "assert response.status == 200, '状态码不对'"})
    assert failure.ok is False
    assert "assert 失败" in failure.message and "状态码不对" in failure.message

    error = _first(resp, {"python": "response.body['nope']"})
    assert error.ok is False
    assert "KeyError" in error.message and "nope" in error.message  # 类型+消息
    assert "assert 失败" not in error.message  # 两类不得混


def test_python_response_view_fields_injected():
    """TC-006: 注入视图五字段可访问 (.status/.headers/.body/.text/.elapsed_ms)."""
    resp = Response(
        status=201,
        headers={"X-Trace": "t-1"},
        body_text='{"id": 5}',
        elapsed_ms=7.5,
    )
    code = (
        "assert response.status == 201\n"
        "assert response.headers['X-Trace'] == 't-1'\n"
        "assert response.body['id'] == 5\n"
        "assert response.text == '{\"id\": 5}'\n"
        "assert response.elapsed_ms == 7.5"
    )
    result = _first(resp, {"python": code})
    assert result.ok is True


def test_python_assert_without_message_gets_default():
    """TC-007: 裸 assert False 无消息时给默认文案."""
    result = _first(_json_response("{}"), {"python": "assert False"})
    assert result.ok is False
    assert result.message == "assert 失败 (无消息)"


def test_python_escape_hatch_no_sandbox():
    """TC-009: 无沙箱 (M6 决策 1): exec 可执行任意 Python (import 标准库可用)."""
    result = _first(_json_response("{}"), {"python": "import os\nassert os.name"})
    assert result.ok is True


# --- TS-003 / TC-010: send 集成, done 事件带 assertions (M4 D003, testbed 真响应) ---

import json

from fastapi.testclient import TestClient

from api_client.store import Body, Item, Store
from api_client.web.app import create_app

_TOKEN = "test-token"


def _execute(client: TestClient, collection: str, slug: str) -> list[dict]:
    response = client.post(
        "/execute",
        json={"collection": collection, "item": slug},
        headers={
            "X-Auth-Token": _TOKEN,
            "Host": "localhost",  # Host 白名单中间件惯例 (同 test_execute_api)
            "Accept": "application/x-ndjson",
        },
    )
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_done_event_carries_assertions(tmp_path, testbed_url):
    """先写的失败测试: done 事件须带 assertions 结果 (修复前恒为 [] 占位).

    条目带断言打 testbed: POST /things 201 -> body.id gte 1 通过;
    每条结果形状 = assertion 定义/ok/actual/message (M4 D003).
    """
    store = Store(tmp_path)
    store.write_item(
        "demo",
        "create-thing",
        Item(
            name="create-thing",
            method="POST",
            url=f"{testbed_url}/things",
            body=Body("json", text='{"content": "hello"}'),
            assertions=[
                {"target": "status", "op": "eq", "expect": 201},
                {"target": "body.id", "op": "gte", "expect": 1},
                {"target": "body.content", "op": "eq", "expect": "hello"},
            ],
        ),
    )
    client = TestClient(create_app(_TOKEN, data_dir=tmp_path))
    done = _execute(client, "demo", "create-thing")[-1]

    assert done["type"] == "done"
    assert done["status"] == 201
    results = done["assertions"]
    assert len(results) == 3
    assert [r["ok"] for r in results] == [True, True, True]
    assert results[0]["assertion"] == {"target": "status", "op": "eq", "expect": 201}
    assert results[0]["actual"] == 201
    assert results[0]["message"] == ""


def test_done_event_status_404_assertion_passes(tmp_path, testbed_url):
    """/status/404 + status eq 404: HTTP 错误状态码 + 断言通过不冲突."""
    store = Store(tmp_path)
    store.write_item(
        "demo",
        "missing",
        Item(
            name="missing",
            method="GET",
            url=f"{testbed_url}/status/404",
            assertions=[{"target": "status", "op": "eq", "expect": 404}],
        ),
    )
    client = TestClient(create_app(_TOKEN, data_dir=tmp_path))
    done = _execute(client, "demo", "missing")[-1]
    assert done["status"] == 404
    assert done["assertions"][0]["ok"] is True


def test_done_event_assertion_failure_marks_status(tmp_path, testbed_url):
    """断言失败不中断执行: done.assertions 含失败条目, done.status 标记断言失败."""
    store = Store(tmp_path)
    store.write_item(
        "demo",
        "create-thing",
        Item(
            name="create-thing",
            method="POST",
            url=f"{testbed_url}/things",
            body=Body("json", text='{"content": "hello"}'),
            assertions=[{"target": "status", "op": "eq", "expect": 500}],
        ),
    )
    client = TestClient(create_app(_TOKEN, data_dir=tmp_path))
    done = _execute(client, "demo", "create-thing")[-1]
    assert done["status"] == "assert_failed"  # 断言失败标记 (ISSUE-04, 供 runner/CLI 消费)
    assert done["assertions"][0]["ok"] is False
    assert done["assertions"][0]["actual"] == 201


def test_assert_yaml_roundtrip_python_block_scalar(tmp_path, testbed_url):
    """TC-011 (M6 决策 2): assert: 键 YAML 往返, 多行 python 用 | 块标量,
    读回求值结果与写前一致."""
    assertions = [
        {"target": "status", "op": "eq", "expect": 201},
        {"python": "assert response.status == 201\nassert response.body['id'] >= 1"},
    ]
    store = Store(tmp_path)
    store.write_item(
        "demo",
        "create-thing",
        Item(
            name="create-thing",
            method="POST",
            url=f"{testbed_url}/things",
            body=Body("json", text='{"content": "hi"}'),
            assertions=assertions,
        ),
    )

    # 序列化形态: 多行 python 代码用 | 块标量 (决策 2, 人和 AI 都可写)
    raw = (tmp_path / "collections" / "demo" / "create-thing.yaml").read_text(encoding="utf-8")
    assert "python: |" in raw

    # 往返: 读回断言定义逐字一致
    item = store.read_item("demo", "create-thing")
    assert item.assertions == assertions

    # 求值一致: 经路由打 testbed, 两条断言全过
    client = TestClient(create_app(_TOKEN, data_dir=tmp_path))
    done = _execute(client, "demo", "create-thing")[-1]
    assert done["status"] == 201
    assert [r["ok"] for r in done["assertions"]] == [True, True]
    assert done["assertions"][1]["assertion"] == assertions[1]
