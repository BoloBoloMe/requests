"""REST GET 助手: 非流式资源/历史查询共用 (响应透传 + 错误映射 + candidates 兜底)."""

from . import candidates, client
from .errors import server_error


def rest_get(conn: client.Connection, path: str, context: dict):
    """GET path 并返回响应 JSON; 非 200 映射为 CliError 并补 candidates (NOT_FOUND 类)."""
    response = conn.request("GET", path)
    if response.status_code != 200:
        error = server_error(response.status_code, response.text)
        raise candidates.with_candidates(error, conn, context)
    return response.json()
