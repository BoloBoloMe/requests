"""原型共享的响应样例 — 取自测试后端 (src/testbed/) 真实形状."""

import json

from dsl import Response

FIXTURES = [
    (
        "POST /things 201 创建成功",
        Response(
            status=201,
            headers={"content-type": "application/json", "x-request-id": "a1b2c3"},
            body_text=json.dumps({"id": 1, "content": "买牛奶"}, ensure_ascii=False),
            elapsed_ms=12.4,
        ),
        [
            {"target": "status", "op": "eq", "expect": 201},
            {"target": "body.id", "op": "gte", "expect": 1},
            {"target": "body.content", "op": "eq", "expect": "买牛奶"},
        ],
    ),
    (
        "GET /things/999 404 不存在",
        Response(
            status=404,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"detail": "Not found"}, ensure_ascii=False),
            elapsed_ms=3.1,
        ),
        [
            {"target": "status", "op": "eq", "expect": 404},
            {"target": "body.detail", "op": "matches", "expect": "(?i)not found"},
        ],
    ),
    (
        "GET /dynamic/validate-now 422 校验失败",
        Response(
            status=422,
            headers={"content-type": "application/json"},
            body_text=json.dumps(
                {"valid": False, "reason": "timestamp drift 600s exceeds tolerance",
                 "server_now": "2025-01-01T00:00:00+00:00"},
                ensure_ascii=False,
            ),
            elapsed_ms=2.8,
        ),
        [
            {"target": "status", "op": "eq", "expect": 422},
            {"target": "body.valid", "op": "eq", "expect": False},
            {"target": "body", "schema": {
                "type": "object",
                "required": ["valid", "reason"],
                "properties": {"valid": {"const": False}, "reason": {"type": "string"}},
            }},
        ],
    ),
    (
        "GET /edge/delay/0.5 200 延迟端点",
        Response(
            status=200,
            headers={"content-type": "application/json"},
            body_text=json.dumps({"delayed": 0.5}),
            elapsed_ms=512.7,
        ),
        [
            {"target": "status", "op": "eq", "expect": 200},
            {"target": "body.delayed", "op": "gte", "expect": 0.5},
            {"target": "elapsed_ms", "op": "lt", "expect": 2000},
            {"python": "assert abs(response.body['delayed'] - 0.5) < 1e-9, '延迟值不符'"},
        ],
    ),
]
