"""错误类型与退出码映射 (M4 D004): 错误统一走 stderr {"error":{code,message,details}}."""

import json
import sys

from . import contract


class CliError(Exception):
    """CLI 可预期错误: 机器码 + 消息 + 可选 details; 退出码由 code 映射."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def exit_for(code: str) -> int:
    return contract.EXIT_BY_CODE.get(code, contract.EXIT_SERVICE_ERROR)


def emit_error(code: str, message: str, details: dict | None = None) -> None:
    payload: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    sys.stderr.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def classify_not_found(message: str) -> str:
    """服务端 404 文案 -> 细分码 (服务端错误契约未细分时的客户端兜底映射)."""
    if "条目" in message or "请求" in message:
        return "ITEM_NOT_FOUND"
    if "环境" in message:
        return "ENV_NOT_FOUND"
    if "集合" in message or "文件夹" in message:
        return "COLLECTION_NOT_FOUND"
    return "NOT_FOUND"


def server_error(status: int, body: str) -> CliError:
    """服务端错误响应 -> CliError.

    优先按裁决形状 {"error":{code,message,details}} 透传; 兜底解析 FastAPI
    {"detail": ...} (08 当前形状): 404 文案细分 NOT_FOUND, 422 detail.code 透传
    (UNRESOLVED_VARIABLES), 其余归 SERVICE_ERROR.
    """
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return CliError(error["code"], str(error.get("message", "")), error.get("details"))
        detail = payload.get("detail")
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            code = detail["code"]
            details = {k: v for k, v in detail.items() if k != "code"} or None
            return CliError(code, str(detail.get("message") or code), details)
        if status == 404:
            message = detail if isinstance(detail, str) else "资源不存在"
            return CliError(classify_not_found(message), message)
        if isinstance(detail, str):
            return CliError("SERVICE_ERROR", detail)
    if status == 404:
        return CliError("NOT_FOUND", "资源不存在")
    return CliError("SERVICE_ERROR", f"服务返回 HTTP {status}: {body[:200]}")
