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

# 事件字段说明 (schema events 节用; 字段名列表在 EVENTS, 单一事实源)
EVENT_FIELD_DESCRIPTIONS = {
    "meta": {
        "type": "事件类型, 恒为 meta",
        "timestamp": "ISO-8601 UTC 字符串",
        "item_ref": "<collection>/<slug>",
        "item": "<collection>/<slug> (同 item_ref)",
        "method": "HTTP 方法",
        "resolved_url": "变量替换后的 URL",
        "env": "环境名或 null",
    },
    "chunk": {
        "type": "事件类型, 恒为 chunk",
        "timestamp": "ISO-8601 UTC 字符串",
        "item": "<collection>/<slug>",
        "index": "从 0 起的 chunk 序号",
        "data": "响应负载 (字符串/对象等)",
    },
    "done": {
        "type": "事件类型, 恒为 done",
        "timestamp": "ISO-8601 UTC 字符串",
        "item": "<collection>/<slug>",
        "status": "HTTP 状态码; 传输失败为 null, 断言失败为 assert_failed",
        "duration_ms": "整数毫秒",
        "assertions": "断言结果列表 {name/assertion, expected, actual, ok/passed, message}",
    },
    "summary": {
        "type": "事件类型, 恒为 summary",
        "timestamp": "ISO-8601 UTC 字符串",
        "total": "条目总数",
        "passed": "通过数",
        "failed": "失败数",
        "items": "每条 {item, status, passed}",
    },
}

# run 末尾附 report 事件 (08 沿用, JUnit XML 输出物): 注记, 不入 M4 D003 四事件契约
RUN_REPORT_NOTE = "run 事件流末尾附 report 事件 {type, format, content} (format=junit, content=JUnit XML 字符串)."

# 命令面 (M4 D001): schema 命令树与 help 共用
COMMANDS = [
    {"path": ["send", "<item-ref>"], "options": ["--env NAME", "--var KEY=VALUE (可重复)"], "default_output": "ndjson", "event_stream": ["meta", "chunk", "done"], "description": "执行单个请求条目并流式输出事件."},
    {"path": ["run", "<collection-ref>"], "options": ["--env NAME", "--var KEY=VALUE (可重复)"], "default_output": "ndjson", "event_stream": ["meta", "chunk", "done", "summary"], "description": "顺序批量执行集合内全部条目; 每条目完整 meta/chunk/done (不吞 chunk), 末尾 summary."},
    {"path": ["collection", "list"], "options": [], "default_output": "json", "description": "列出集合."},
    {"path": ["collection", "show", "<ref>"], "options": [], "default_output": "json", "description": "查看集合配置."},
    {"path": ["item", "list", "<collection-ref>"], "options": [], "default_output": "json", "description": "列出集合内请求条目."},
    {"path": ["item", "show", "<item-ref>"], "options": [], "default_output": "json", "description": "查看请求条目定义."},
    {"path": ["env", "list"], "options": [], "default_output": "json", "description": "列出环境."},
    {"path": ["env", "show", "<name>"], "options": [], "default_output": "json", "description": "查看环境变量."},
    {"path": ["history", "list"], "options": [], "default_output": "json", "description": "列出最近执行历史."},
    {"path": ["history", "show", "<id>"], "options": [], "default_output": "json", "description": "查看单条历史."},
    {"path": ["service", "status"], "options": [], "default_output": "json", "description": "服务运行状态 {status,pid,port,version}."},
    {"path": ["service", "stop"], "options": [], "default_output": "json", "description": "停止服务 (按 --data-dir 定位)."},
    {"path": ["service", "token"], "options": [], "default_output": "json", "description": "显示当前服务 token."},
    {"path": ["schema"], "options": [], "default_output": "json", "description": "输出本机读契约."},
    {"path": ["guide"], "options": [], "default_output": "text", "description": "输出文读手册 (llms.txt 风格)."},
]

GLOBAL_FLAGS = [
    {"name": "--output", "type": "choice", "choices": ["json", "ndjson", "pretty"], "default": "按命令默认 (send/run 为 ndjson, 其余 json)", "description": "输出形态."},
    {"name": "--data-dir", "type": "path", "default": "~/.local/share/api-client/", "description": "数据仓库目录."},
]

DEFAULT_DATA_DIR = "~/.local/share/api-client"
