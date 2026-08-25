"""ISSUE-04 TS-002/TS-003: schema/guide/help 契约一致性 (M4 D005 硬要求).

一致性锚点两类:
- 独立字面量 (来自 M4 D003/D004 账本): 防实现与账本漂移;
- api_client_cli.contract 常量源自动比对: 防 schema/help 手写副本漂移.
"""

import json

from api_client_cli import contract

from support import run_cli, stdout_json

# M4 D003 事件字段 (账本独立真相源)
EVENT_FIELDS_LITERAL = {
    "meta": ["type", "timestamp", "item_ref", "item", "method", "resolved_url", "env"],
    "chunk": ["type", "timestamp", "item", "index", "data"],
    "done": ["type", "timestamp", "item", "status", "duration_ms", "assertions"],
    "summary": ["type", "timestamp", "total", "passed", "failed", "items"],
}
EXIT_LINE_LITERAL = "0 OK / 1 ASSERTION_FAILED / 2 USAGE_ERROR / 3 SERVICE_ERROR / 4 NOT_FOUND"
ERROR_CODES_LITERAL = {"USAGE_ERROR", "UNRESOLVED_VARIABLES", "COLLECTION_NOT_FOUND", "ITEM_NOT_FOUND", "ENV_NOT_FOUND", "SERVICE_ERROR"}


def test_schema_event_fields_match_contract_source():
    """schema 事件字段与 contract.py 常量源逐字一致, 且锚定账本字面量, 无省略 (TC-005/TC-006)."""
    proc = run_cli(["schema"])
    assert proc.returncode == 0, proc.stderr
    schema = stdout_json(proc)
    assert "..." not in proc.stdout, "schema 禁止省略号 (dogfood 首轮扣分项)"
    for name, fields in EVENT_FIELDS_LITERAL.items():
        assert schema["events"][name]["fields"] == fields, f"schema 事件 {name} 字段与账本不符"
        assert schema["events"][name]["fields"] == contract.EVENTS[name], f"schema 事件 {name} 字段与常量源漂移"


def test_schema_contains_full_machine_contract():
    """schema 含命令树/参数/输出模式/退出码表/错误码表/错误格式 (TC-005)."""
    schema = stdout_json(run_cli(["schema"]))
    assert schema["exit_codes"] == contract.EXIT_CODES
    assert schema["error_codes"] == contract.ERROR_CODES
    assert schema["error_format"] == contract.ERROR_FORMAT
    assert schema["output_modes"] == contract.OUTPUT_MODES
    paths = [" ".join(c["path"]) for c in schema["commands"]]
    for expected in (
        "send <item-ref>",
        "run <collection-ref>",
        "collection list",
        "collection show <ref>",
        "item list <collection-ref>",
        "item show <item-ref>",
        "env list",
        "env show <name>",
        "history list",
        "history show <id>",
        "service status",
        "service stop",
        "service token",
        "schema",
        "guide",
    ):
        assert expected in paths, f"schema 命令树缺 {expected}"
    send = schema["commands"][paths.index("send <item-ref>")]
    assert "--env NAME" in send["options"] and any("--var" in o for o in send["options"])


def test_schema_error_codes_cover_ledger():
    """schema 错误码覆盖账本集合, 退出码表 0-4 (TC-006)."""
    schema = stdout_json(run_cli(["schema"]))
    codes = {entry["code"] for entry in schema["error_codes"]}
    assert ERROR_CODES_LITERAL <= codes
    assert [entry["code"] for entry in schema["exit_codes"]] == [0, 1, 2, 3, 4]


def test_guide_covers_agent_curriculum():
    """guide 含快速示例/命令面/输出模式/退出码/错误码/item-ref/变量与未解析变量语义 (TC-007)."""
    proc = run_cli(["guide"])
    assert proc.returncode == 0, proc.stderr
    guide = proc.stdout
    assert "apic send" in guide and "apic run" in guide
    assert "item-ref" in guide and "<collection>/<slug>" in guide
    for needle in ("UNRESOLVED_VARIABLES", "{{$now}}", "{{$uuid}}", "--var", "Exit codes", "Error codes"):
        assert needle in guide, f"guide 缺 {needle}"
    # 事件字段与退出码行与常量源逐字一致
    assert contract.EVENT_STREAM_LINE in guide
    assert EXIT_LINE_LITERAL in guide


def test_help_epilog_matches_contract():
    """顶层 help epilog 三节与 schema/contract 逐字一致 (TC-008, dogfood 二轮扣分项)."""
    help_text = run_cli(["--help"]).stdout
    assert EXIT_LINE_LITERAL in help_text
    assert contract.EVENT_STREAM_LINE in help_text  # 含 resolved_url/index 等真实字段名
    error_line = ", ".join(c["code"] for c in contract.ERROR_CODES)
    assert error_line in help_text
    # 与 schema 同源: help 中的事件行 == schema 所引常量源 (防 url vs resolved_url 类错配)
    schema = stdout_json(run_cli(["schema"]))
    schema_line = " / ".join(f"{name}({','.join(e['fields'])})" for name, e in schema["events"].items())
    assert schema_line in help_text


def test_subcommand_help_has_examples():
    """每个子命令 --help 带示例 (dogfood 二/三轮修正) (TC-008 同类)."""
    for argv in (
        ["send", "--help"],
        ["run", "--help"],
        ["collection", "--help"],
        ["item", "--help"],
        ["env", "--help"],
        ["history", "--help"],
        ["service", "--help"],
        ["schema", "--help"],
        ["guide", "--help"],
    ):
        proc = run_cli(argv)
        assert proc.returncode == 0, argv
        assert "示例" in proc.stdout or "Example" in proc.stdout, f"{argv} 缺示例"
