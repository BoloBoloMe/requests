"""Resolve: 请求条目 + 环境 -> 可执行请求 (M3 D008).

藏: 变量优先级 (M2 D012: 集合 vars < 环境 vars < 环境 secrets; D-AFK-011 追加:
调用方一次性 vars 覆盖层最高), 集合级默认继承
(M2 D010: headers 按名合并请求覆盖同名, auth 整体覆盖), 动态变量白名单
(M1 D010: {{$now}}/{{$uuid}}). 插值在 url/params/headers/body/auth 全字段生效
(M1 D009); 解析后残留 {{var}} 硬失败 UNRESOLVED_VARIABLES (M4 D006).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .store import Body, CollectionConfig, Environment, Item, KV, MultipartPart

_VAR_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


class UnresolvedVariablesError(Exception):
    """解析后仍残留 {{var}} (M4 D006): missing 列出全部缺失变量名."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"未解析变量: {', '.join(missing)}")


@dataclass
class ResolvedRequest:
    """可执行请求: 全部字段已完成插值与默认继承."""

    name: str
    method: str
    url: str
    params: list[KV] = field(default_factory=list)
    headers: list[KV] = field(default_factory=list)
    body: Body = field(default_factory=Body)
    auth: dict | None = None


def _default_now_fn() -> datetime:
    return datetime.now(timezone.utc)


def _default_uuid_fn() -> str:
    return str(uuid.uuid4())


def build_request(
    item: Item,
    env: Environment | None = None,
    config: CollectionConfig | None = None,
    *,
    vars: dict[str, str] | None = None,
    now_fn: Callable[[], datetime] | None = None,
    uuid_fn: Callable[[], str] | None = None,
) -> ResolvedRequest:
    """纯函数: 条目 + 环境 (+集合配置) -> 可执行请求.

    vars 为调用方一次性覆盖层 (D-AFK-011): 优先级最高, 只影响本次解析, 不落盘.
    now_fn/uuid_fn 注入便于测试; 缺省为 UTC 当前时间 / UUIDv4 (M1 D010).
    """
    now_fn = now_fn or _default_now_fn
    uuid_fn = uuid_fn or _default_uuid_fn

    # 变量优先级 (M2 D012 + D-AFK-011): 集合 vars < 环境 vars < 环境 secrets < 本次 vars
    variables: dict[str, str] = {}
    if config is not None:
        variables.update(config.vars)
    if env is not None:
        variables.update(env.vars)
        variables.update(env.secrets)
    if vars is not None:
        variables.update(vars)

    missing: set[str] = set()

    def substitute(text: str) -> str:
        def replace(match: re.Match) -> str:
            name = match.group(1).strip()
            if name == "$now":
                return now_fn().isoformat()
            if name == "$uuid":
                return uuid_fn()
            if name in variables:
                return variables[name]
            missing.add(name)
            return match.group(0)

        return _VAR_RE.sub(replace, text)

    url = substitute(item.url)
    params = [KV(kv.key, substitute(kv.value), kv.disabled) for kv in item.params]
    headers = [KV(kv.key, substitute(kv.value), kv.disabled) for kv in item.headers]

    # 集合级默认继承 (M2 D010): headers 按名合并 (大小写不敏感), 请求覆盖同名
    if config is not None:
        request_names = {kv.key.lower() for kv in headers}
        inherited = [
            KV(kv.key, substitute(kv.value), kv.disabled)
            for kv in config.defaults.headers
            if kv.key.lower() not in request_names
        ]
        headers = inherited + headers

    def substitute_any(value: Any) -> Any:
        """auth 等嵌套结构: 递归对字符串值插值 (M1 D009 全字段)."""
        if isinstance(value, str):
            return substitute(value)
        if isinstance(value, dict):
            return {k: substitute_any(v) for k, v in value.items()}
        if isinstance(value, list):
            return [substitute_any(v) for v in value]
        return value

    # body 全形态插值 (M1 D009): json/text 文本, form-urlencoded params, multipart parts
    body = item.body
    if body.type in ("json", "text"):
        body = Body(body.type, text=substitute(body.text))
    elif body.type == "form-urlencoded":
        body = Body(
            body.type,
            params=[KV(kv.key, substitute(kv.value), kv.disabled) for kv in body.params],
        )
    elif body.type == "multipart":
        body = Body(
            body.type,
            parts=[
                MultipartPart(
                    name=part.name,
                    value=None if part.value is None else substitute(part.value),
                    file=None if part.file is None else substitute(part.file),
                    content_type=None
                    if part.content_type is None
                    else substitute(part.content_type),
                )
                for part in body.parts
            ],
        )

    # auth 整体覆盖 (M2 D010): 请求定义则全用请求的, 否则继承集合默认
    auth_raw = item.auth if item.auth is not None else (config.defaults.auth if config else None)
    auth = substitute_any(auth_raw) if auth_raw is not None else None

    if missing:
        raise UnresolvedVariablesError(sorted(missing))

    return ResolvedRequest(
        name=item.name,
        method=item.method,
        url=url,
        params=params,
        headers=headers,
        body=body,
        auth=auth,
    )
