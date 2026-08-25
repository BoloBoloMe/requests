"""ISSUE-03 TS-001: Resolve 纯单测 (M3 D014-1: 无网络/无服务, 纯函数).

接缝: resolve.build_request(item, env, config, now_fn/uuid_fn 注入).
覆盖: M2 D012 (变量优先级), M2 D010 (集合级默认继承), M1 D009/D010 (插值全字段/动态变量白名单),
M4 D006 (未解析变量硬失败 UNRESOLVED_VARIABLES).
"""

from datetime import datetime, timezone
import uuid

import pytest

from api_client.resolve import UnresolvedVariablesError, build_request
from api_client.store import (
    CollectionConfig,
    CollectionDefaults,
    Environment,
    Item,
    KV,
)

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
UUID_FIXED = "11111111-2222-4333-8444-555555555555"


def _now_fn() -> datetime:
    return NOW


def _uuid_fn() -> str:
    return UUID_FIXED


def _header(req, key: str) -> str | None:
    for kv in req.headers:
        if kv.key == key:
            return kv.value
    return None


# --- TC-001: 变量优先级 集合 vars < 环境 vars < 环境 secrets (M2 D012) ---


def test_resolve_secrets_override_env():
    """同名变量: secrets 覆盖环境 vars, 环境 vars 覆盖集合 vars."""
    item = Item(
        name="x",
        method="GET",
        url="http://{{host}}/p",
        headers=[KV("X-Token", "{{token}}")],
    )
    config = CollectionConfig(vars={"host": "collection-host", "token": "collection-token"})
    env = Environment(
        name="dev",
        vars={"host": "env-host", "token": "env-token"},
        secrets={"token": "secret-token"},
    )
    req = build_request(item, env, config)
    assert req.url == "http://env-host/p"  # 环境 vars 覆盖集合 vars
    assert _header(req, "X-Token") == "secret-token"  # secrets 最高优先级


# --- TC-002: 集合级默认继承 (M2 D010): headers 按名合并请求覆盖同名, auth 整体覆盖 ---


def test_resolve_collection_defaults_headers_merge():
    """默认 headers 按名合并 (大小写不敏感), 请求同名覆盖; 请求独有保留."""
    config = CollectionConfig(
        defaults=CollectionDefaults(
            headers=[KV("Accept", "application/json"), KV("X-Debug", "on")],
        )
    )
    item = Item(
        name="x",
        method="GET",
        url="http://x/",
        headers=[KV("x-debug", "off"), KV("X-Req", "1")],  # 小写同名覆盖默认
    )
    req = build_request(item, None, config)
    assert _header(req, "Accept") == "application/json"
    assert _header(req, "x-debug") == "off"  # 请求覆盖同名默认 (大小写不敏感)
    assert _header(req, "X-Debug") is None  # 被覆盖的默认不再出现
    assert _header(req, "X-Req") == "1"


def test_resolve_collection_defaults_auth_override():
    """auth 整体覆盖: 请求定义了 auth 则全用请求的; 未定义则继承集合默认."""
    config = CollectionConfig(
        defaults=CollectionDefaults(auth={"type": "bearer", "token": "default-{{token}}"})
    )
    env = Environment(name="dev", vars={"token": "tok"})

    inherited = build_request(
        Item(name="x", method="GET", url="http://x/", auth=None), env, config
    )
    assert inherited.auth == {"type": "bearer", "token": "default-tok"}  # 继承且插值

    overridden = build_request(
        Item(
            name="x",
            method="GET",
            url="http://x/",
            auth={"type": "basic", "username": "u", "password": "{{token}}"},
        ),
        env,
        config,
    )
    assert overridden.auth == {"type": "basic", "username": "u", "password": "tok"}


# --- M1 D009: 插值在 url/params/headers/body/auth 全字段生效 ---


def test_resolve_interpolates_all_fields():
    """url/params/headers/body(json/text/form/multipart)/auth 全部字段插值."""
    from api_client.store import Body, MultipartPart

    env = Environment(name="dev", vars={"host": "h", "v": "V"})
    item = Item(
        name="x",
        method="POST",
        url="http://{{host}}/p",
        params=[KV("q", "{{v}}"), KV("skip", "{{v}}", disabled=True)],
        headers=[KV("X-A", "{{v}}")],
        body=Body(
            "multipart",
            parts=[
                MultipartPart(name="note", value="hi {{v}}"),
                MultipartPart(name="f", file="files/{{v}}.bin", content_type="text/plain"),
            ],
        ),
        auth={"type": "bearer", "token": "{{v}}"},
    )
    req = build_request(item, env)
    assert req.url == "http://h/p"
    assert [(kv.key, kv.value, kv.disabled) for kv in req.params] == [
        ("q", "V", False),
        ("skip", "V", True),  # disabled 行同样插值 (发送侧再跳过)
    ]
    assert _header(req, "X-A") == "V"
    assert req.body.parts[0].value == "hi V"
    assert req.body.parts[1].file == "files/V.bin"
    assert req.auth == {"type": "bearer", "token": "V"}

    # form-urlencoded 与 json/text 体
    form = build_request(
        Item(name="f", method="POST", url="http://x/",
             body=Body("form-urlencoded", params=[KV("a", "{{v}}")])),
        env,
    )
    assert form.body.params[0].value == "V"
    text = build_request(
        Item(name="t", method="POST", url="http://x/", body=Body("json", text='{"k": "{{v}}"}')),
        env,
    )
    assert text.body.text == '{"k": "V"}'


# --- TC-003: 动态变量白名单 {{$now}}/{{$uuid}} (M1 D010, M2 D012 $ 命名空间独占) ---


def test_resolve_dynamic_variables_whitelist():
    """{{$now}} 求值为注入的 ISO 时间戳, {{$uuid}} 为注入的 UUIDv4;
    其余 $ 前缀变量不被识别 -> 残留硬失败 (M2 D012: $ 前缀禁止静态定义)."""
    item = Item(
        name="x",
        method="GET",
        url="http://x/",
        params=[KV("ts", "{{$now}}"), KV("id", "{{$uuid}}")],
    )
    req = build_request(item, None, None, now_fn=_now_fn, uuid_fn=_uuid_fn)
    assert req.params[0].value == NOW.isoformat()
    assert req.params[1].value == UUID_FIXED

    with pytest.raises(UnresolvedVariablesError) as exc_info:
        build_request(
            Item(name="x", method="GET", url="http://x/{{$random}}"),
            None,
            None,
            now_fn=_now_fn,
            uuid_fn=_uuid_fn,
        )
    assert exc_info.value.missing == ["$random"]


def test_resolve_dynamic_variables_default_fns():
    """缺省 now_fn/uuid_fn: 现场求值 ISO 时间戳与 UUIDv4 格式."""
    req = build_request(Item(name="x", method="GET", url="http://x/{{$now}}/{{$uuid}}"))
    _, ts, uid = req.url.rsplit("/", 2)[0], *req.url.rsplit("/", 2)[1:]
    datetime.fromisoformat(ts)  # 可解析即 ISO
    parsed = uuid.UUID(uid)
    assert parsed.version == 4


# --- TC-004: 解析后残留 {{var}} -> 硬失败 UNRESOLVED_VARIABLES (M4 D006) ---


def test_resolve_unresolved_variables_hard_fail():
    """url/headers/body 任一字段残留即抛 UnresolvedVariablesError, missing 列全量缺失名."""
    from api_client.store import Body

    env = Environment(name="dev", vars={"known": "v"})
    item = Item(
        name="x",
        method="POST",
        url="http://{{host}}/{{known}}",
        headers=[KV("X-A", "{{token}}")],
        body=Body("text", text="hi {{who}}"),
    )
    with pytest.raises(UnresolvedVariablesError) as exc_info:
        build_request(item, env)
    assert exc_info.value.missing == ["host", "token", "who"]  # 已解析的 known 不在列
