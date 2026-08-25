"""service 资源组: status/stop/token (M3 D005/D011-7, M4 D002 非流式单 JSON)."""

from . import client
from .errors import CliError
from .output import emit_object


def _fetch_version(conn: client.Connection) -> str | None:
    """GET /health 取 version; 不可达/无该字段为 null (请求级重试一次在 client 内)."""
    try:
        response = conn.request("GET", "/health")
    except CliError:
        return None
    if response.status_code != 200:
        return None
    try:
        version = response.json().get("version")
    except ValueError:
        return None
    return version if isinstance(version, str) else None


def cmd_status(args) -> int:
    """读 service.json + kill(pid,0) 存活判定, 输出 {status,pid,port,version}."""
    conn = client.read_connection(args.data_dir)
    if conn is None or not conn.alive:
        payload = {"status": "stopped", "pid": conn.pid if conn else None, "port": conn.port if conn else None, "version": None}
    else:
        payload = {"status": "running", "pid": conn.pid, "port": conn.port, "version": _fetch_version(conn)}
    emit_object(payload, args.output or "json")
    return 0


def cmd_stop(args) -> int:
    """委托 launch 停止语义 (SIGTERM + 等待), 按 --data-dir 定位 (D011-7)."""
    pid = client.stop_service(args.data_dir)
    emit_object({"status": "stopped", "pid": pid}, args.output or "json")
    return 0


def cmd_token(args) -> int:
    """读 launch token (service.json 单一权威源, M3 D005), 输出 {token}."""
    conn = client.read_connection(args.data_dir)
    if conn is None:
        raise CliError("SERVICE_ERROR", f"服务未运行 ({args.data_dir} 无有效 service.json)")
    emit_object({"token": conn.token}, args.output or "json")
    return 0
