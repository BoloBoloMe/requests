"""ISSUE-01 TS-001: CLI 骨架 + 用法错误 (M4-D001/D004, M3-D001).

接缝: `apic` 子进程; argparse 命令树.
"""

from support import run_cli, stderr_error


def test_no_command_exits_usage_error():
    """无命令 -> stderr {"error":{"code":"USAGE_ERROR",...}}, exit 2, stdout 空 (TC-001)."""
    proc = run_cli([])
    assert proc.returncode == 2
    assert proc.stdout == ""
    error = stderr_error(proc)
    assert error["code"] == "USAGE_ERROR"
    assert error["message"]


def test_unknown_command_exits_usage_error():
    """未知命令 -> USAGE_ERROR exit 2, stdout 空 (TC-001)."""
    proc = run_cli(["frobnicate"])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "USAGE_ERROR"


def test_missing_required_argument_exits_usage_error():
    """缺必填参数 (send 无 item-ref) -> USAGE_ERROR exit 2 (TC-001)."""
    proc = run_cli(["send"])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "USAGE_ERROR"


def test_resource_group_without_verb_exits_usage_error():
    """资源组缺动词 (apic collection) -> USAGE_ERROR exit 2 (TC-001)."""
    proc = run_cli(["collection"])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert stderr_error(proc)["code"] == "USAGE_ERROR"


def test_top_help_has_three_machine_contract_sections():
    """顶层 --help 存在且 epilog 含 exit/error/event 三节机器契约 (TC-002)."""
    proc = run_cli(["--help"])
    assert proc.returncode == 0
    assert "Exit codes" in proc.stdout
    assert "Error codes" in proc.stdout
    assert "Event stream" in proc.stdout
    # 命令面骨架 (M4-D001): 动作动词 + 资源名词组 + 元命令
    for name in ("send", "run", "collection", "item", "env", "history", "service", "schema", "guide"):
        assert name in proc.stdout


def test_subcommand_help_available():
    """各子命令 --help 存在 (TC-002)."""
    for argv in (["send", "--help"], ["run", "--help"], ["service", "--help"], ["collection", "--help"]):
        proc = run_cli(argv)
        assert proc.returncode == 0, argv
        assert "usage" in proc.stdout.lower()
