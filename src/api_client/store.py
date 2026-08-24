"""Store: 数据仓库读写唯一入口 (M3 D008).

出进皆为领域对象; 藏 YAML schema/seq 排序/secrets 合并/.local 状态/历史路径.
全部写走 tmp+rename 原子写 (防批量写与 Sync commit 交叠出半写文件).

YAML 子集约定 (M2 D002): 显式 version 字段; 禁用锚点/别名; vars/params/headers/
secrets 的 kv 值一律按字符串解析 (防 YAML 1.1 on/off/yes/no 布尔陷阱).

目录布局 (M2 D004):
    collections/<集合>/<文件夹>/<slug>.yaml
    collections/<集合>/_collection.yaml
    environments/<env>.yaml / environments/<env>.secrets.yaml
    files/
    .local/  (state.yaml 等本地状态, gitignored)
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FORMAT_VERSION = 1

BODY_TYPES = ("none", "json", "text", "form-urlencoded", "multipart")


class NotFoundError(Exception):
    """数据仓库中不存在所请求的资源 (集合/条目/环境)."""


class _StringSafeLoader(yaml.SafeLoader):
    """kv 值一律按字符串解析: 移除 bool 隐式解析器 (M2 D002/F002)."""


# 拷贝后剔除 bool resolver, 不污染全局 SafeLoader; on/off/yes/no/true/false 读为字符串
_StringSafeLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in pairs if tag != "tag:yaml.org,2002:bool"]
    for key, pairs in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class _SubsetDumper(yaml.SafeDumper):
    """禁用锚点/别名 (M2 D002); sort_keys=False 保字段书写顺序."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _dump_yaml(payload: dict) -> str:
    return yaml.dump(
        payload,
        Dumper=_SubsetDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = yaml.load(fh, Loader=_StringSafeLoader)
    if not isinstance(data, dict):
        raise ValueError(f"YAML 顶层应为 mapping: {path}")
    return data


def _atomic_write_text(path: Path, text: str) -> None:
    """tmp+rename 原子写 (M3 D008): 同目录临时文件 + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _as_bool(value: Any) -> bool:
    """disabled 读侧兼容: bool resolver 已移除, true/false 读为字符串."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


_NAME_RE = re.compile(r"^[^/\\]{1,200}$")


def _validate_name(kind: str, name: str) -> None:
    """名称即路径片段: 拒绝路径分隔符与 .., 防越出数据仓库."""
    if not _NAME_RE.match(name) or ".." in name or name.startswith("."):
        raise ValueError(f"非法{kind}名: {name!r}")


@dataclass
class KV:
    """有序 kv 对 (params/headers/form-urlencoded), 可 disabled (M2 D008)."""

    key: str
    value: str
    disabled: bool = False


@dataclass
class MultipartPart:
    """multipart part: 内联文本 (value) 或文件引用 (file + 可选 contentType) (M2 D009)."""

    name: str
    value: str | None = None
    file: str | None = None
    content_type: str | None = None


@dataclass
class Body:
    """请求体: type 五态 (M2 D008); json/text 用 text, form-urlencoded 用 params,
    multipart 用 parts."""

    type: str = "none"
    text: str = ""
    params: list[KV] = field(default_factory=list)
    parts: list[MultipartPart] = field(default_factory=list)


@dataclass
class Item:
    """请求条目 (M2 D008); version 恒为 FORMAT_VERSION (v1)."""

    name: str
    method: str
    url: str
    seq: int = 0
    params: list[KV] = field(default_factory=list)
    headers: list[KV] = field(default_factory=list)
    body: Body = field(default_factory=Body)
    auth: dict | None = None
    assertions: list[dict] = field(default_factory=list)
    version: int = FORMAT_VERSION


@dataclass
class ItemEntry:
    """集合列表条目: slug (文件名) + 领域对象."""

    slug: str
    item: Item


@dataclass
class CollectionDefaults:
    """集合级默认 (M2 D010): auth 整体覆盖; headers 按名合并 (解析属 ISSUE-03)."""

    auth: dict | None = None
    headers: list[KV] = field(default_factory=list)


@dataclass
class CollectionConfig:
    """`_collection.yaml`: 集合变量 vars + 集合级默认 defaults (M2 D010)."""

    vars: dict[str, str] = field(default_factory=dict)
    defaults: CollectionDefaults = field(default_factory=CollectionDefaults)


@dataclass
class Environment:
    """环境 (M2 D005/D006): vars 为环境变量, secrets 已按最高优先级并入 merged."""

    name: str
    vars: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)
    merged: dict[str, str] = field(default_factory=dict)


def _kv_to_yaml(kv: KV) -> dict:
    out: dict[str, Any] = {"key": kv.key, "value": str(kv.value)}
    if kv.disabled:
        out["disabled"] = True
    return out


def _kv_from_yaml(data: dict) -> KV:
    return KV(
        key=str(data["key"]),
        value=str(data.get("value", "")),
        disabled=_as_bool(data.get("disabled", False)),
    )


def _body_to_yaml(body: Body) -> dict:
    if body.type == "none":
        return {"type": "none"}
    if body.type in ("json", "text"):
        return {"type": body.type, "text": body.text}
    if body.type == "form-urlencoded":
        return {"type": body.type, "params": [_kv_to_yaml(kv) for kv in body.params]}
    if body.type == "multipart":
        parts = []
        for part in body.parts:
            entry: dict[str, Any] = {"name": part.name}
            if part.file is not None:
                entry["file"] = part.file
                if part.content_type is not None:
                    entry["contentType"] = part.content_type
            else:
                entry["value"] = part.value if part.value is not None else ""
            parts.append(entry)
        return {"type": body.type, "parts": parts}
    raise ValueError(f"未知 body.type: {body.type!r}")


def _body_from_yaml(data: Any) -> Body:
    if not data:
        return Body()
    body_type = data.get("type", "none")
    if body_type == "none":
        return Body()
    if body_type in ("json", "text"):
        return Body(body_type, text=str(data.get("text", "")))
    if body_type == "form-urlencoded":
        return Body(
            body_type,
            params=[_kv_from_yaml(kv) for kv in data.get("params", [])],
        )
    if body_type == "multipart":
        parts = [
            MultipartPart(
                name=str(p["name"]),
                value=None if p.get("value") is None else str(p["value"]),
                file=None if p.get("file") is None else str(p["file"]),
                content_type=None if p.get("contentType") is None else str(p["contentType"]),
            )
            for p in data.get("parts", [])
        ]
        return Body(body_type, parts=parts)
    raise ValueError(f"未知 body.type: {body_type!r}")


def item_to_dict(item: Item) -> dict:
    """领域对象 → 纯 dict (JSON 壳用); 形状与 YAML 一致, assert 键名保持 DSL 原名."""
    out: dict[str, Any] = {
        "version": item.version,
        "name": item.name,
        "method": item.method,
        "url": item.url,
        "seq": item.seq,
        "params": [_kv_to_yaml(kv) for kv in item.params],
        "headers": [_kv_to_yaml(kv) for kv in item.headers],
        "body": _body_to_yaml(item.body),
        "auth": item.auth,
        "assert": item.assertions,
    }
    return out


def item_from_dict(data: dict) -> Item:
    """纯 dict → 领域对象; 缺省补齐, 形状校验同读侧."""
    return Item(
        name=str(data["name"]),
        method=str(data["method"]),
        url=str(data["url"]),
        seq=int(data.get("seq", 0)),
        params=[_kv_from_yaml(kv) for kv in data.get("params", [])],
        headers=[_kv_from_yaml(kv) for kv in data.get("headers", [])],
        body=_body_from_yaml(data.get("body")),
        auth=data.get("auth"),
        assertions=list(data.get("assert", [])),
    )


class Store:
    """数据仓库读写唯一入口; 构造即初始化 M2 D004 布局."""

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        for sub in ("collections", "environments", "files", ".local"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)

    # --- 集合配置 `_collection.yaml` (M2 D010) ---

    def _collection_config_path(self, collection: str) -> Path:
        return self._collection_dir(collection) / "_collection.yaml"

    def write_collection(self, collection: str, config: CollectionConfig) -> None:
        payload: dict[str, Any] = {
            "version": FORMAT_VERSION,
            "vars": {str(k): str(v) for k, v in config.vars.items()},
            "defaults": {
                "auth": config.defaults.auth,
                "headers": [_kv_to_yaml(kv) for kv in config.defaults.headers],
            },
        }
        _atomic_write_text(self._collection_config_path(collection), _dump_yaml(payload))

    def read_collection(self, collection: str) -> CollectionConfig:
        """未写过 _collection.yaml 的集合读回空配置; 集合目录不存在才 404."""
        if not self._collection_dir(collection).is_dir():
            raise NotFoundError(f"集合不存在: {collection}")
        path = self._collection_config_path(collection)
        if not path.is_file():
            return CollectionConfig()
        data = _load_yaml(path)
        defaults_raw = data.get("defaults") or {}
        return CollectionConfig(
            vars={str(k): str(v) for k, v in (data.get("vars") or {}).items()},
            defaults=CollectionDefaults(
                auth=defaults_raw.get("auth"),
                headers=[_kv_from_yaml(kv) for kv in defaults_raw.get("headers", [])],
            ),
        )

    # --- 环境/secrets (M2 D005/D006) ---

    def _env_path(self, name: str, secrets: bool = False) -> Path:
        _validate_name("环境", name)
        suffix = ".secrets.yaml" if secrets else ".yaml"
        return self.data_dir / "environments" / f"{name}{suffix}"

    def _read_vars_file(self, path: Path) -> dict[str, str]:
        """version + vars 文件读侧: vars 值一律字符串 (loader 已钉死)."""
        if not path.is_file():
            raise NotFoundError(f"环境不存在: {path.stem}")
        data = _load_yaml(path)
        vars_raw = data.get("vars") or {}
        if not isinstance(vars_raw, dict):
            raise ValueError(f"vars 应为 mapping: {path}")
        return {str(k): str(v) for k, v in vars_raw.items()}

    def _write_vars_file(self, path: Path, vars_: dict[str, str]) -> None:
        payload = {"version": FORMAT_VERSION, "vars": {str(k): str(v) for k, v in vars_.items()}}
        _atomic_write_text(path, _dump_yaml(payload))

    def write_environment(self, name: str, vars: dict[str, str]) -> None:
        self._write_vars_file(self._env_path(name), vars)

    def write_secrets(self, name: str, secrets: dict[str, str]) -> None:
        """写 secrets 文件 (gitignored, M2 D006); .gitignore 规则属 ISSUE-06."""
        self._write_vars_file(self._env_path(name, secrets=True), secrets)

    # --- 激活环境状态 (M2 D007) ---

    def _state_path(self) -> Path:
        return self.data_dir / ".local" / "state.yaml"

    def get_active_environment(self) -> str | None:
        path = self._state_path()
        if not path.is_file():
            return None
        value = _load_yaml(path).get("active_environment")
        return None if value is None else str(value)

    def set_active_environment(self, name: str | None) -> None:
        if name is not None:
            _validate_name("环境", name)
        _atomic_write_text(
            self._state_path(), _dump_yaml({"version": FORMAT_VERSION, "active_environment": name})
        )

    def read_environment(self, name: str) -> Environment:
        """出参为领域对象: vars 与 secrets 分列, merged = secrets 合并后视图 (D006 优先级最高)."""
        vars_ = self._read_vars_file(self._env_path(name))
        secrets_path = self._env_path(name, secrets=True)
        secrets = self._read_vars_file(secrets_path) if secrets_path.is_file() else {}
        return Environment(name=name, vars=vars_, secrets=secrets, merged={**vars_, **secrets})

    # --- 路径计算 (布局藏于本模块内) ---

    def _collection_dir(self, collection: str) -> Path:
        _validate_name("集合", collection)
        return self.data_dir / "collections" / collection

    def _item_path(self, collection: str, slug: str, folder: str = "") -> Path:
        _validate_name("条目", slug)
        base = self._collection_dir(collection)
        if folder:
            for part in folder.split("/"):
                _validate_name("文件夹", part)
            base = base / folder
        return base / f"{slug}.yaml"

    # --- 集合/条目 (TS-001) ---

    def list_collections(self) -> list[str]:
        """集合名列表 (目录名), 字典序."""
        base = self.data_dir / "collections"
        return sorted(p.name for p in base.iterdir() if p.is_dir())

    def delete_item(self, collection: str, slug: str, folder: str = "") -> None:
        path = self._item_path(collection, slug, folder)
        if not path.is_file():
            raise NotFoundError(f"请求条目不存在: {collection}/{folder}/{slug}")
        path.unlink()

    def write_item(self, collection: str, slug: str, item: Item, folder: str = "") -> None:
        payload: dict[str, Any] = {
            "version": item.version,
            "name": item.name,
            "method": item.method,
            "url": item.url,
            "seq": item.seq,
            "params": [_kv_to_yaml(kv) for kv in item.params],
            "headers": [_kv_to_yaml(kv) for kv in item.headers],
            "body": _body_to_yaml(item.body),
        }
        if item.auth is not None:
            payload["auth"] = item.auth
        if item.assertions:
            payload["assert"] = item.assertions
        _atomic_write_text(
            self._item_path(collection, slug, folder), _dump_yaml(payload)
        )

    def list_items(self, collection: str, folder: str = "") -> list[ItemEntry]:
        """列文件夹内条目: seq 整数定序, 平局按文件名 (slug) tiebreak (M2 D003)."""
        base = self._collection_dir(collection)
        if not base.is_dir():
            raise NotFoundError(f"集合不存在: {collection}")
        if folder:
            for part in folder.split("/"):
                _validate_name("文件夹", part)
            base = base / folder
            if not base.is_dir():
                raise NotFoundError(f"文件夹不存在: {collection}/{folder}")
        entries = [
            ItemEntry(slug=path.name[: -len(".yaml")], item=self.read_item(collection, path.name[: -len(".yaml")], folder))
            for path in base.glob("*.yaml")
            if path.name != "_collection.yaml"
        ]
        entries.sort(key=lambda e: (e.item.seq, e.slug))
        return entries

    def read_item(self, collection: str, slug: str, folder: str = "") -> Item:
        path = self._item_path(collection, slug, folder)
        if not path.is_file():
            raise NotFoundError(f"请求条目不存在: {collection}/{folder}/{slug}")
        data = _load_yaml(path)
        return Item(
            name=str(data.get("name", "")),
            method=str(data.get("method", "GET")),
            url=str(data.get("url", "")),
            seq=int(data.get("seq", 0)),
            params=[_kv_from_yaml(kv) for kv in data.get("params", [])],
            headers=[_kv_from_yaml(kv) for kv in data.get("headers", [])],
            body=_body_from_yaml(data.get("body")),
            auth=data.get("auth"),
            assertions=list(data.get("assert", [])),
            version=int(data.get("version", FORMAT_VERSION)),
        )
