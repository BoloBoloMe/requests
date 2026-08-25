"""Assert: 响应 + 断言定义 -> 逐条断言结果 (M3 D008, M6 决策 1/2/3).

纯函数求值器, 无 I/O (D014-1). 双形态 (M6 决策 1):
- 结构化断言 (默认): `target + op + expect` 三元组, 或 `target + schema`
  (jsonschema 整体校验). target 集 = status / elapsed_ms / header.<名>
  (大小写不敏感) / body / body.<jmespath>;
  op 集 = eq ne lt lte gt gte contains not_contains matches exists (exists 无 expect).
- Python 逃生舱: `{"python": "<代码>"}`, exec 注入 response 视图, 全量 Python 无沙箱.

非 JSON 体降级 (M6 决策 3): `body.<路径>` 一律解析失败, 裸 body (= 原始文本)
+ contains/not_contains/matches/eq 兜底; "体非 JSON" 与 "路径不存在" 文案区分.

求值语义照 `docs/changes/api-client/prototypes/assertion-dsl/dsl.py` 重写 (不复制).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import jmespath
import jsonschema

OPS = ("eq", "ne", "lt", "lte", "gt", "gte", "contains", "not_contains", "matches", "exists")


@dataclass
class Response:
    """一次执行的响应快照 (断言关心的面); body 为 JSON 体解析视图."""

    status: int
    headers: dict[str, str]
    body_text: str
    elapsed_ms: float

    @property
    def body(self) -> Any:
        """JSON 体解析为对象; 非 JSON 体保持原始文本 (M6 决策 3 降级前提)."""
        try:
            return json.loads(self.body_text)
        except (json.JSONDecodeError, TypeError):
            return self.body_text


@dataclass
class Result:
    """单条断言结果: assertion 定义 / ok / actual / message (M4 D003 done.assertions 形状)."""

    assertion: dict
    ok: bool
    actual: Any = None
    message: str = ""


class _Miss:
    """target 解析失败: 携带失败原因文案 (决策 3: "体非 JSON" 与 "路径不存在" 区分)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


def resolve(response: Response, target: str) -> Any:
    """把 target 解析为实际值; 解析失败返回 _Miss(原因文案)."""
    if target == "status":
        return response.status
    if target == "elapsed_ms":
        return response.elapsed_ms
    if target.startswith("header."):
        name = target[len("header.") :].lower()
        for key, value in response.headers.items():
            if key.lower() == name:
                return value
        return _Miss(f"响应头不存在: {name}")
    if target == "body":
        return response.body
    if target.startswith("body."):
        body = response.body
        if isinstance(body, str):  # 非 JSON 体, 路径无意义 (M6 决策 3)
            return _Miss("体非 JSON 不可取路径")
        try:
            value = jmespath.search(target[len("body.") :], body)
        except jmespath.exceptions.JMESPathError:
            return _Miss("路径不存在")
        return _Miss("路径不存在") if value is None else value
    return _Miss(f"未知 target: {target!r}")


def compare(op: str, actual: Any, expect: Any) -> tuple[bool, str]:
    """单个比较; 返回 (是否通过, 失败原因)."""
    if op == "exists":
        return True, ""
    if op == "eq":
        return actual == expect, f"期望 {expect!r}"
    if op == "ne":
        return actual != expect, f"期望非 {expect!r}"
    if op in ("lt", "lte", "gt", "gte"):
        # 数值比较拒布尔: bool 是 int 子类, 须显式排除 (True > 0 是伪通过)
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False, f"实际值 {actual!r} 非数值, 不可比大小"
        if op == "lt":
            return actual < expect, f"期望 lt {expect!r}"
        if op == "lte":
            return actual <= expect, f"期望 lte {expect!r}"
        if op == "gt":
            return actual > expect, f"期望 gt {expect!r}"
        return actual >= expect, f"期望 gte {expect!r}"
    if op in ("contains", "not_contains"):
        try:
            hit = expect in actual
        except TypeError:
            return False, f"实际值 {actual!r} 不支持包含判断"
        return (
            hit if op == "contains" else not hit
        ), f"期望{'不' if op == 'not_contains' else ''}包含 {expect!r}"
    if op == "matches":
        if not isinstance(actual, str):
            return False, f"实际值 {actual!r} 非字符串, 不可正则"
        return re.search(str(expect), actual) is not None, f"期望匹配 /{expect}/"
    return False, f"未知 op: {op}"


class ResponseView:
    """注入 Python 断言的响应视图 (M6 决策 1: .status/.headers/.body/.text/.elapsed_ms)."""

    def __init__(self, resp: Response):
        self.status = resp.status
        self.headers = dict(resp.headers)
        self.text = resp.body_text
        self.body = resp.body
        self.elapsed_ms = resp.elapsed_ms


def _eval_python(response: Response, code: str) -> Result:
    """exec 断言代码, 无沙箱 (M6 决策 1: 自用, RCE 权重不成立).
    AssertionError = 断言失败 (取其消息); 其他异常 = 错误 (类型+消息)."""
    assertion = {"python": code}
    try:
        exec(code, {"__builtins__": __builtins__}, {"response": ResponseView(response)})
    except AssertionError as exc:
        message = f"assert 失败: {exc}" if str(exc) else "assert 失败 (无消息)"
        return Result(assertion, False, message=message)
    except Exception as exc:  # noqa: BLE001 — 逃生舱报告一切异常为错误
        return Result(assertion, False, message=f"{type(exc).__name__}: {exc}")
    return Result(assertion, True)


def evaluate(response: Response, assertions: list[dict]) -> list[Result]:
    """逐条求值; 顺序执行, 不短路. 单条求值异常降级为失败结果, 不中断后续."""
    results: list[Result] = []
    for a in assertions:
        if "python" in a:
            results.append(_eval_python(response, str(a["python"])))
            continue
        target = str(a.get("target", ""))
        try:
            actual = resolve(response, target)
            if "schema" in a:
                if isinstance(actual, _Miss):
                    results.append(Result(a, False, message=actual.reason))
                    continue
                try:
                    jsonschema.validate(actual, a["schema"])
                    results.append(Result(a, True))
                except jsonschema.ValidationError as exc:
                    results.append(Result(a, False, message=exc.message))
                continue
            op = str(a.get("op", ""))
            if isinstance(actual, _Miss):
                results.append(Result(a, False, message=actual.reason))
                continue
            ok, reason = compare(op, actual, a.get("expect"))
            results.append(Result(a, ok, actual=actual, message="" if ok else reason))
        except Exception as exc:  # 定义畸形 (坏 schema/坏正则等): 单条失败, 不中断
            results.append(Result(a, False, message=f"{type(exc).__name__}: {exc}"))
    return results
