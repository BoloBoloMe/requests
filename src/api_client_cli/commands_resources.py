"""资源名词组: collection/item/env list/show (M4 D001/D002 非流式单 JSON).

CLI 透传服务端响应体渲染 (薄壳, 不做形状变换); 404 细分 + candidates 沿用 ISSUE-02.
"""

from . import client
from .commands_send import parse_item_ref
from .errors import CliError
from .output import emit_object
from .rest import rest_get


def cmd_collection_list(args) -> int:
    conn = client.connect(args.data_dir)
    emit_object(rest_get(conn, "/collections", {}), args.output or "json")
    return 0


def cmd_collection_show(args) -> int:
    conn = client.connect(args.data_dir)
    context = {"collection": args.ref}
    emit_object(rest_get(conn, f"/collections/{args.ref}/collection", context), args.output or "json")
    return 0


def cmd_item_list(args) -> int:
    conn = client.connect(args.data_dir)
    context = {"collection": args.collection_ref}
    emit_object(rest_get(conn, f"/collections/{args.collection_ref}/items", context), args.output or "json")
    return 0


def cmd_item_show(args) -> int:
    collection, slug = parse_item_ref(args.item_ref)
    conn = client.connect(args.data_dir)
    context = {"collection": collection, "item": slug}
    emit_object(rest_get(conn, f"/collections/{collection}/items/{slug}", context), args.output or "json")
    return 0


def cmd_env_list(args) -> int:
    conn = client.connect(args.data_dir)
    emit_object(rest_get(conn, "/environments", {}), args.output or "json")
    return 0


def cmd_env_show(args) -> int:
    conn = client.connect(args.data_dir)
    emit_object(rest_get(conn, f"/environments/{args.name}", {"env": args.name}), args.output or "json")
    return 0
