"""NOT_FOUND candidates 纠错 (M4 D004): 服务端 details.candidates 优先透传;
缺省时 CLI 经 inventory 端点取清单, difflib (cutoff 0.6) + 子串并集兜底.

属错误恢复/展示逻辑, 非业务执行逻辑 (M3 D001 允许边界, dogfood 第三轮修正).
"""

import difflib

from . import client
from .errors import CliError


def find_candidates(query: str, refs: list[str]) -> list[str]:
    """子串匹配 (大小写不敏感) ∪ difflib 近似 (cutoff 0.6), 排序输出."""
    lowered = query.lower()
    hits = [ref for ref in refs if lowered in ref.lower()]
    close = difflib.get_close_matches(query, refs, n=len(refs), cutoff=0.6) if refs else []
    return sorted(set(hits) | set(close))


def _list_names(conn: client.Connection, path: str, wrapper_key: str, item_key: str | None = None) -> list[str]:
    """inventory 端点取名称清单; 兼容数组与包装对象两种形状; 失败回空 (纠错兜底不致命)."""
    try:
        response = conn.request("GET", path)
        if response.status_code != 200:
            return []
        payload = response.json()
    except Exception:
        return []
    if isinstance(payload, dict):
        payload = payload.get(wrapper_key, [])
    if not isinstance(payload, list):
        return []
    names = []
    for entry in payload:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict) and item_key and isinstance(entry.get(item_key), str):
            names.append(entry[item_key])
    return names


def _inventory(conn: client.Connection, code: str, context: dict) -> tuple[list[str], str] | None:
    """按细分码取 (清单, 查询词); 无法取 (端点缺失等) 回 None."""
    if code == "COLLECTION_NOT_FOUND":
        return _list_names(conn, "/collections", "collections"), context.get("collection", "")
    if code == "ITEM_NOT_FOUND":
        collection = context.get("collection")
        if not collection:
            return None
        return _list_names(conn, f"/collections/{collection}/items", "items", "slug"), context.get("item", "")
    if code == "ENV_NOT_FOUND":
        return _list_names(conn, "/environments", "environments", "name"), context.get("env", "")
    return None


def with_candidates(error: CliError, conn: client.Connection, context: dict) -> CliError:
    """NOT_FOUND 类错误补 details.candidates: 服务端已给则透传, 否则客户端兜底计算."""
    if not error.code.endswith("NOT_FOUND"):
        return error
    details = dict(error.details or {})
    if "candidates" in details:
        return CliError(error.code, error.message, details)
    candidates: list[str] = []
    found = _inventory(conn, error.code, context)
    if found is not None:
        refs, query = found
        if query:
            candidates = find_candidates(query, refs)
    details["candidates"] = candidates
    return CliError(error.code, error.message, details)
