"""history 资源组: list/show 非流式只读查询 (M4 D002 单 JSON, M3 D010).

历史落盘/聚合是服务端 Store 职责, CLI 纯查询渲染 (M3 D008).
"""

from urllib.parse import quote

from . import candidates, client
from .errors import CliError, server_error
from .output import emit_object


def _get(conn: client.Connection, path: str, context: dict):
    response = conn.request("GET", path)
    if response.status_code != 200:
        error = server_error(response.status_code, response.text)
        raise candidates.with_candidates(error, conn, context)
    return response.json()


def cmd_history_list(args) -> int:
    conn = client.connect(args.data_dir)
    payload = _get(conn, "/history", {})
    # 服务端包 {"entries": [...]}; CLI 输出裸数组 (M4 D002 单 JSON)
    emit_object(payload.get("entries", payload), args.output or "json")
    return 0


def cmd_history_show(args) -> int:
    conn = client.connect(args.data_dir)
    # id = 历史相对路径 (集合/[文件夹/]条目/时间戳), 逐段引用防特殊字符
    quoted = "/".join(quote(part, safe="") for part in args.id.split("/"))
    emit_object(_get(conn, f"/history/entry/{quoted}", {}), args.output or "json")
    return 0
