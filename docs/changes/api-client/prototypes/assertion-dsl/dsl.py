"""断言 DSL 原型 — 核心逻辑模块 (纯函数, 无 I/O).

待验证的问题:
1. DSL 形态: `target + op + expect` 三元组 (target = status/elapsed_ms/header.<名>/body[.<jmespath>]),
   外加 `schema` 整体校验, 这个组合能否覆盖日常断言 (状态码/头/体字段/数组长度/时延)?
2. 序列化形态: 断言列表存进集合文件 (YAML) 是否人和 AI 都可写?
3. 表达力缺口: 拿测试后端的真实响应样例跑, 记录表达不了的场景.

本模块即 DSL 求值器参考答案: 输入响应 + 断言列表, 输出逐条结果.
断言用 dict 表示 (对应 YAML 反序列化结果):

    {"target": "status",          "op": "eq",       "expect": 200}
    {"target": "elapsed_ms",      "op": "lt",       "expect": 500}
    {"target": "header.content-type", "op": "contains", "expect": "json"}
    {"target": "body.id",         "op": "gte",      "expect": 1}
    {"target": "body",            "schema": {...}}
    {"target": "body.items",      "op": "exists"}        # exists 无 expect

op 全集: eq ne lt lte gt gte contains not_contains matches exists

Python 逃生舱 (已拍板双保留, 自用无他人仓库, RCE 权重不成立):

    {"python": "assert response.body['id'] >= 1\nassert abs(response.elapsed_ms - 500) < 100"}

exec 命名空间注入 response (status/headers/body/text/elapsed_ms), 全量 Python 不做沙箱.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import jmespath
import jsonschema

MISSING = object()  # 路径解析失败哨兵

OPS = ("eq", "ne", "lt", "lte", "gt", "gte", "contains", "not_contains", "matches", "exists")


@dataclass
class Response:
    """一次执行的响应快照 (原型只保留断言关心的面)."""

    status: int
    headers: dict[str, str]
    body_text: str
    elapsed_ms: float

    @property
    def body(self) -> Any:
        try:
            return json.loads(self.body_text)
        except (json.JSONDecodeError, TypeError):
            return self.body_text


@dataclass
class Result:
    assertion: dict
    ok: bool
    actual: Any = None
    message: str = ""


def resolve(response: Response, target: str) -> Any:
    """把 target 解析为实际值; 失败返回 MISSING."""
    if target == "status":
        return response.status
    if target == "elapsed_ms":
        return response.elapsed_ms
    if target.startswith("header."):
        name = target[len("header.") :].lower()
        for k, v in response.headers.items():
            if k.lower() == name:
                return v
        return MISSING
    if target == "body":
        return response.body
    if target.startswith("body."):
        body = response.body
        if isinstance(body, str):  # 非 JSON 体, 路径无意义
            return MISSING
        try:
            value = jmespath.search(target[len("body.") :], body)
        except jmespath.exceptions.JMESPathError:
            return MISSING
        return MISSING if value is None else value
    return MISSING


def compare(op: str, actual: Any, expect: Any) -> tuple[bool, str]:
    """单个比较; 返回 (是否通过, 失败原因)."""
    if op == "exists":
        return True, ""
    if op == "eq":
        return actual == expect, f"期望 {expect!r}"
    if op == "ne":
        return actual != expect, f"期望非 {expect!r}"
    if op in ("lt", "lte", "gt", "gte"):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False, f"实际值 {actual!r} 非数值, 不可比大小"
        return {
            "lt": actual < expect,
            "lte": actual <= expect,
            "gt": actual > expect,
            "gte": actual >= expect,
        }[op], f"期望 {op} {expect!r}"
    if op in ("contains", "not_contains"):
        try:
            hit = expect in actual
        except TypeError:
            return False, f"实际值 {actual!r} 不支持包含判断"
        return (hit if op == "contains" else not hit), f"期望{'不' if op == 'not_contains' else ''}包含 {expect!r}"
    if op == "matches":
        if not isinstance(actual, str):
            return False, f"实际值 {actual!r} 非字符串, 不可正则"
        return re.search(str(expect), actual) is not None, f"期望匹配 /{expect}/"
    return False, f"未知 op: {op}"


class ResponseView:
    """注入 Python 断言的响应视图."""

    def __init__(self, resp: Response):
        self.status = resp.status
        self.headers = dict(resp.headers)
        self.text = resp.body_text
        self.body = resp.body
        self.elapsed_ms = resp.elapsed_ms


def _eval_python(response: Response, code: str) -> Result:
    """exec 断言代码; AssertionError=失败, 其他异常=错误, 均无沙箱."""
    a = {"python": code}
    try:
        exec(code, {"__builtins__": __builtins__}, {"response": ResponseView(response)})
    except AssertionError as e:
        return Result(a, False, message=f"assert 失败: {e}" if str(e) else "assert 失败 (无消息)")
    except Exception as e:  # noqa: BLE001 — 原型报告一切异常
        return Result(a, False, message=f"{type(e).__name__}: {e}")
    return Result(a, True, actual="<python 断言通过>")


def evaluate(response: Response, assertions: list[dict]) -> list[Result]:
    """逐条求值; 顺序执行, 不短路."""
    results: list[Result] = []
    for a in assertions:
        if "python" in a:
            results.append(_eval_python(response, a["python"]))
            continue
        target = a.get("target", "")
        actual = resolve(response, target)
        if "schema" in a:
            if actual is MISSING:
                results.append(Result(a, False, message="target 解析失败"))
                continue
            try:
                jsonschema.validate(actual, a["schema"])
                results.append(Result(a, True, actual="<schema 校验通过>"))
            except jsonschema.ValidationError as e:
                results.append(Result(a, False, actual=MISSING, message=e.message))
            continue
        op = a.get("op", "")
        if actual is MISSING:
            if op == "exists":
                results.append(Result(a, False, message="路径不存在"))
            else:
                results.append(Result(a, False, message=f"target {target!r} 解析失败"))
            continue
        ok, reason = compare(op, actual, a.get("expect"))
        results.append(Result(a, ok, actual=actual, message="" if ok else reason))
    return results


def to_yaml(assertions: list[dict]) -> str:
    """极简 YAML 发射器: 只支持本 DSL 用到的标量/字典/列表, 供目测序列化形态."""

    def scalar(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        return json.dumps(str(v), ensure_ascii=False)

    def emit_kv(head: str, k: str, v: Any, indent: int) -> list[str]:
        """一对 key-value; 多行字符串用块标量 |."""
        pad = "  " * indent
        if isinstance(v, str) and "\n" in v:
            return [f"{head}{k}: |"] + [f"{pad}  {line}" for line in v.splitlines()]
        if isinstance(v, (dict, list)) and v:
            return [f"{head}{k}:"] + emit(v, indent + 1)
        if isinstance(v, (dict, list)):
            return [f"{head}{k}: {'{}' if isinstance(v, dict) else '[]'}"]
        return [f"{head}{k}: {scalar(v)}"]

    def emit(value: Any, indent: int) -> list[str]:
        pad = "  " * indent
        if isinstance(value, dict):
            lines = []
            for k, v in value.items():
                lines.extend(emit_kv(pad, k, v, indent))
            return lines
        if isinstance(value, list):
            lines = []
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for k, v in item.items():
                        head = f"{pad}- " if first else f"{pad}  "
                        first = False
                        lines.extend(emit_kv(head, k, v, indent + 1))
                else:
                    lines.append(f"{pad}- {scalar(item)}")
            return lines
        return [f"{pad}{scalar(value)}"]

    return "\n".join(emit(assertions, 0))
