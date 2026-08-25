"""schema 机读契约组装 (M4 D005): 全部由 contract.py 常量源产出, 禁止手写副本."""

from . import contract


def build_schema() -> dict:
    """完整机读契约: 命令树/参数/输出模式/事件定义/退出码表/错误码表/错误格式."""
    commands = []
    for command in contract.COMMANDS:
        entry = dict(command)
        if "event_stream" in entry:
            entry["event_stream"] = [
                {"event": name, "fields": contract.EVENTS[name]} for name in entry["event_stream"]
            ]
            if entry["path"][0] == "run":
                entry["note"] = contract.RUN_REPORT_NOTE
        commands.append(entry)
    return {
        "program": "apic",
        "description": "AI 友好的 API client 命令行外壳 (瘦客户端, 连本地服务执行).",
        "global_flags": contract.GLOBAL_FLAGS,
        "output_modes": contract.OUTPUT_MODES,
        "commands": commands,
        "events": {
            name: {"fields": fields, "field_descriptions": contract.EVENT_FIELD_DESCRIPTIONS[name]}
            for name, fields in contract.EVENTS.items()
        },
        "exit_codes": contract.EXIT_CODES,
        "error_codes": contract.ERROR_CODES,
        "error_format": contract.ERROR_FORMAT,
    }
