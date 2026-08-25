"""ISSUE-02 TS-001/TS-002/TS-004: Store 纯单测 (M3 D014-1, tmp_path 数据目录, 无网络/无服务).

接缝: Store 公开 API; 出进皆为领域对象 (M3 D008).
覆盖: M2 D001-D008/D010 (布局/YAML 子集/seq 排序/字段形状/环境/secrets/state/集合默认).
"""

import pytest
import yaml

from api_client.store import (
    Body,
    CollectionConfig,
    CollectionDefaults,
    Item,
    KV,
    MultipartPart,
    NotFoundError,
    Store,
    item_from_dict,
)


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "repo")


def _full_item(body: Body) -> Item:
    """全字段条目: 覆盖 M2 D008 字段形状 (含 {{var}} 插值/auth/assert)."""
    return Item(
        name="创建订单",
        method="POST",
        url="https://{{host}}/api/orders",
        seq=3,
        params=[
            KV("page", "1"),
            KV("page", "2"),  # params 允许重复键
            KV("debug", "on", disabled=True),
        ],
        headers=[
            KV("X-Trace", "{{$uuid}}"),
            KV("X-Debug", "off", disabled=True),
        ],
        body=body,
        auth={"type": "bearer", "token": "{{token}}"},
        assertions=[
            {"target": "status", "op": "eq", "expect": 201},
            {"target": "body.ok", "op": "exists"},
            {"python": "assert response.status == 201"},
        ],
    )


BODIES = [
    Body("none"),
    Body("json", text='{"a": 1}'),
    Body("text", text="hello {{name}}"),
    Body("form-urlencoded", params=[KV("a", "1"), KV("b", "yes")]),
    Body(
        "multipart",
        parts=[
            MultipartPart(name="note", value=" inline "),
            MultipartPart(name="upload", file="files/a.bin", content_type="application/octet-stream"),
        ],
    ),
]


# --- TC-002: seq 排序平局文件名 tiebreak (M2 D003) ---


def test_list_items_sorts_by_seq_then_filename(store):
    """seq 整数定序, 平局按文件名 (slug) tiebreak; 文件名不含序号."""
    store.write_item("demo", "b-late", Item(name="b", method="GET", url="http://x/", seq=2))
    store.write_item("demo", "z-tie", Item(name="z", method="GET", url="http://x/", seq=1))
    store.write_item("demo", "a-tie", Item(name="a", method="GET", url="http://x/", seq=1))
    entries = store.list_items("demo")
    assert [e.slug for e in entries] == ["a-tie", "z-tie", "b-late"]


# --- TC-003: 文件夹映射子目录 (M2 D001/D004) ---


def test_folder_maps_to_subdirectory(store, tmp_path):
    """folder=子目录: 文件落在 collections/<集合>/<文件夹>/<slug>.yaml, 读回等价."""
    item = Item(name="嵌套", method="GET", url="http://x/nested", seq=1)
    store.write_item("demo", "nested", item, folder="a/b")
    path = store.data_dir / "collections" / "demo" / "a" / "b" / "nested.yaml"
    assert path.is_file()
    assert store.read_item("demo", "nested", folder="a/b") == item
    assert [e.slug for e in store.list_items("demo", folder="a/b")] == ["nested"]


# --- TC-004: 原子写 (M3 D008) ---


def test_write_is_atomic_no_partial_residue(store, tmp_path):
    """tmp+rename: 写入后文件完整可读回等价, 目录无临时文件残留."""
    store.write_item("demo", "atomic", _full_item(BODY:=Body("text", text="v1")))
    store.write_item("demo", "atomic", _full_item(Body("text", text="v2")))  # 覆写
    item_dir = store.data_dir / "collections" / "demo"
    assert not list(item_dir.glob("*.tmp")), "不应有半写临时文件残留"
    got = store.read_item("demo", "atomic")
    assert got.body.text == "v2"
    assert got == _full_item(Body("text", text="v2"))


# --- TS-002 (环境/secrets/激活状态) ---


# TC-007: YAML 子集 — 值一律字符串 (M2 D002/F002)
def test_yaml_subset_values_stay_strings(store):
    """on/off/yes/no 读写均为字符串, 不解析为布尔; 手写未加引号标量亦不解析."""
    store.write_environment("dev", {"debug": "on", "verbose": "off", "flag": "yes", "neg": "no"})
    env = store.read_environment("dev")
    assert env.vars == {"debug": "on", "verbose": "off", "flag": "yes", "neg": "no"}
    assert all(isinstance(v, str) for v in env.vars.values())

    # 手写文件未加引号: 读侧仍按字符串解析 (布尔陷阱不回潮)
    raw = store.data_dir / "environments" / "hand.yaml"
    raw.write_text("version: 1\nvars:\n  a: on\n  b: off\n  c: true\n", encoding="utf-8")
    hand = store.read_environment("hand")
    assert hand.vars == {"a": "on", "b": "off", "c": "true"}


# TC-007b: YAML 子集 — 读侧禁锚点/别名 (M2 D002)
def test_yaml_subset_rejects_anchors_and_aliases(store):
    """手写含 &anchor / *alias 的 YAML: 读取即拒绝, 不得解析."""
    raw = store.data_dir / "environments" / "anch.yaml"
    raw.write_text("version: 1\nvars:\n  a: &x hello\n  b: *x\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        store.read_environment("anch")

    # 仅锚点无别名同样拒绝
    raw.write_text("version: 1\nvars:\n  a: &x hello\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        store.read_environment("anch")


# TC-001b: 畸形 payload 在归一化入口即 ValueError (CRUD 壳据此归 422)
def test_item_from_dict_rejects_malformed_shapes():
    base = {"name": "x", "method": "GET", "url": "http://x/"}
    with pytest.raises(ValueError):
        item_from_dict({**base, "params": "not-a-list"})
    with pytest.raises(ValueError):
        item_from_dict({**base, "headers": ["not-a-dict"]})
    with pytest.raises(ValueError):
        item_from_dict({**base, "headers": [{"value": "v"}]})  # 元素缺 key
    with pytest.raises(ValueError):
        item_from_dict({**base, "body": "not-a-dict"})


# TC-005: env 与 secrets 同 schema, 合并时 secrets 优先级最高 (M2 D005/D006)
def test_environment_secrets_merge_highest_priority(store):
    store.write_environment("dev", {"host": "http://dev", "token": "placeholder"})
    store.write_secrets("dev", {"token": "s3cret", "password": "pw"})
    env = store.read_environment("dev")
    assert env.vars == {"host": "http://dev", "token": "placeholder"}
    assert env.secrets == {"token": "s3cret", "password": "pw"}
    assert env.merged == {"host": "http://dev", "token": "s3cret", "password": "pw"}
    # 两文件同 schema 且分盘 (M2 D006)
    base = store.data_dir / "environments"
    assert (base / "dev.yaml").is_file()
    assert (base / "dev.secrets.yaml").is_file()


# 环境列表: 扫 environments/*.yaml, 排除 *.secrets.yaml, 文件名排序; 空仓库 → 空列表
def test_list_environments_excludes_secrets(store):
    assert store.list_environments() == []  # 空仓库不报错
    store.write_environment("prod", {"host": "http://prod"})
    store.write_environment("dev", {"host": "http://dev"})
    store.write_secrets("dev", {"token": "s3cret"})
    assert store.list_environments() == ["dev", "prod"]  # 字典序, 无 secrets 名


# TC-006: 激活环境存 .local/state.yaml, 未设时为空 (M2 D007)
def test_state_active_environment_roundtrip(store):
    assert store.get_active_environment() is None
    store.set_active_environment("dev")
    assert store.get_active_environment() == "dev"
    store.set_active_environment(None)
    assert store.get_active_environment() is None
    assert (store.data_dir / ".local" / "state.yaml").is_file()


# --- TS-004: 集合默认读写 (M2 D010) ---


# TC-012: _collection.yaml 的 vars/defaults (auth/headers) 读写往返
def test_collection_defaults_roundtrip(store):
    config = CollectionConfig(
        vars={"host": "https://api.example", "debug": "on"},
        defaults=CollectionDefaults(
            auth={"type": "bearer", "token": "{{token}}"},
            headers=[KV("Accept", "application/json"), KV("X-Debug", "off", disabled=True)],
        ),
    )
    store.write_collection("demo", config)
    assert (store.data_dir / "collections" / "demo" / "_collection.yaml").is_file()
    assert store.read_collection("demo") == config


def test_collection_config_missing_returns_empty(store):
    """未写过 _collection.yaml 的集合: 读回空配置 (布局初始化即合法状态)."""
    store.write_item("demo", "x", Item(name="x", method="GET", url="http://x/"))
    assert store.read_collection("demo") == CollectionConfig()


# --- TC-001: 条目 YAML 往返保字段形状 ---


@pytest.mark.parametrize("body", BODIES, ids=lambda b: b.type)
def test_item_roundtrip_preserves_field_shape(store, body):
    """条目写入后读回, 字段形状不丢: url 单字符串含 {{var}}, params/headers 有序 kv
    可 disabled, body.type 五态, version/auth/assert 字段 (M2 D008)."""
    item = _full_item(body)
    store.write_item("demo", "create-order", item)
    got = store.read_item("demo", "create-order")
    assert got == item
    assert got.version == 1
