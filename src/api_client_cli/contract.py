"""契约常量源 (M4 D005 单一事实源): 退出码/错误码/事件字段/错误格式.

schema/guide/help 三节机器契约与本实现共用此源, 禁止手写副本 (dogfood 扣分项).
事件字段对齐 M4 D003 与服务端 Engine/Runner 实际出流.
"""

EXIT_OK = 0
EXIT_ASSERTION_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_SERVICE_ERROR = 3
EXIT_NOT_FOUND = 4

EXIT_CODES = [
    {"code": EXIT_OK, "label": "OK", "meaning": "成功; 全部断言通过."},
    {"code": EXIT_ASSERTION_FAILED, "label": "ASSERTION_FAILED", "meaning": "领域失败; 数据正常产出但至少一条断言未通过."},
    {"code": EXIT_USAGE_ERROR, "label": "USAGE_ERROR", "meaning": "CLI 调用非法, 未解析变量或参数错误."},
    {"code": EXIT_SERVICE_ERROR, "label": "SERVICE_ERROR", "meaning": "服务/操作失败."},
    {"code": EXIT_NOT_FOUND, "label": "NOT_FOUND", "meaning": "集合, 请求条目或环境不存在."},
]

ERROR_CODES = [
    {"code": "USAGE_ERROR", "exit": EXIT_USAGE_ERROR, "meaning": "CLI 调用非法或参数错误."},
    {
        "code": "UNRESOLVED_VARIABLES",
        "exit": EXIT_USAGE_ERROR,
        "meaning": "变量替换后 URL/headers/body 仍残留 {{NAME}} 占位符; 动态变量 {{$now}}/{{$uuid}} 由引擎求值, 不在此列.",
        "details": {"missing": "未解析变量名列表"},
    },
    {"code": "COLLECTION_NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "集合引用不存在.", "details": {"candidates": "相近集合 ref 列表"}},
    {"code": "ITEM_NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "请求条目引用不存在.", "details": {"candidates": "相近条目 slug 列表"}},
    {"code": "ENV_NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "环境名不存在.", "details": {"candidates": "相近环境名列表"}},
    {"code": "NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "资源不存在 (历史条目等无细分码的资源)."},
    {"code": "SERVICE_ERROR", "exit": EXIT_SERVICE_ERROR, "meaning": "服务/操作失败."},
]

# 错误码 -> 退出码 (M4 D004 小表)
EXIT_BY_CODE = {entry["code"]: entry["exit"] for entry in ERROR_CODES}

# 事件字段 (M4 D003): meta/chunk/done/summary, 逐字精确, 禁止省略
EVENTS = {
    "meta": ["type", "timestamp", "item_ref", "item", "method", "resolved_url", "env"],
    "chunk": ["type", "timestamp", "item", "index", "data"],
    "done": ["type", "timestamp", "item", "status", "duration_ms", "assertions"],
    "summary": ["type", "timestamp", "total", "passed", "failed", "items"],
}

EVENT_STREAM_LINE = " / ".join(f"{name}({','.join(fields)})" for name, fields in EVENTS.items())

ERROR_FORMAT = {"error": {"code": "<MACHINE_CODE>", "message": "人类可读消息", "details": "可选对象"}}

OUTPUT_MODES = {
    "json": "流式命令 (send/run): 事件 JSON 数组; 非流式命令: 单 JSON 对象.",
    "ndjson": "流式命令 (send/run): 逐行 NDJSON 事件流; 非流式命令: 等同 json, 单行输出.",
    "pretty": "流式命令 (send/run): 每行以事件 type 开头 + 完整 JSON; 非流式命令: 表格/缩略 (可回退 JSON).",
}

DEFAULT_DATA_DIR = "~/.local/share/api-client"
