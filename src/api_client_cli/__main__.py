"""apic CLI 入口: argparse 命令树 + dispatch + 顶层异常 -> 退出码 (M4 D001/D004).

`apic serve` / `apic stop` 转发到 `python -m api_client` (08 服务壳路径不失效);
业务命令 (send/run/资源组) 经 client.connect 幂等拉起服务后执行.
"""

import argparse
import subprocess
import sys

from . import client, contract
from .commands_history import cmd_history_list, cmd_history_show
from .commands_run import cmd_run
from .commands_send import cmd_send
from .commands_service import cmd_status, cmd_stop, cmd_token
from .errors import CliError, emit_error, exit_for


class JSONErrorParser(argparse.ArgumentParser):
    """用法错误输出机器可读 JSON (M4 D004): stderr {"error":{"code":"USAGE_ERROR",...}}, exit 2."""

    def error(self, message: str) -> None:
        emit_error("USAGE_ERROR", message)
        self.exit(contract.EXIT_USAGE_ERROR)


def _epilog() -> str:
    """顶层 help 三节机器契约 (exit/error/event), 由 contract 常量源生成 (M4 D005)."""
    exit_line = " / ".join(f"{c['code']} {c['label']}" for c in contract.EXIT_CODES)
    error_line = ", ".join(c["code"] for c in contract.ERROR_CODES)
    return (
        "Exit codes:\n  " + exit_line + "\n\n"
        "Error codes:\n  " + error_line + "\n\n"
        "Event stream:\n  " + contract.EVENT_STREAM_LINE + "\n\n"
        "Agent examples: apic schema | apic guide | apic send <collection>/<slug> | apic run <collection>"
    )


def _placeholder(name: str):
    """业务命令占位 (后续 issue 实现): 先 connect 幂等拉起 (服务在则不动作), 再报未实现."""

    def handler(args) -> int:
        client.connect(args.data_dir)
        raise CliError("SERVICE_ERROR", f"命令尚未实现 (占位): {name}")

    return handler


def _meta_placeholder(name: str):
    """元命令占位: 离线可答, 不拉起服务."""

    def handler(args) -> int:
        raise CliError("SERVICE_ERROR", f"命令尚未实现 (占位): {name}")

    return handler


def _add_global(parser: argparse.ArgumentParser, suppress: bool = False) -> None:
    # 子命令位副本用 SUPPRESS 默认值: 避免 argparse 子解析器默认值覆盖顶层已解析值
    default = argparse.SUPPRESS if suppress else None
    parser.add_argument(
        "--output",
        choices=["json", "ndjson", "pretty"],
        default=default,
        help="输出形态: json / ndjson (send/run 默认) / pretty (供人, 非流式默认 json).",
    )
    parser.add_argument(
        "--data-dir",
        default=argparse.SUPPRESS if suppress else contract.DEFAULT_DATA_DIR,
        help="数据仓库目录 (默认: ~/.local/share/api-client/).",
    )


def build_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    _add_global(parent, suppress=True)  # 子命令位全局选项 (--data-dir 可置于子命令后)

    parser = JSONErrorParser(
        prog="apic",
        description="AI 友好的 API client 命令行外壳 (瘦客户端, 连本地服务执行).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_epilog(),
    )
    _add_global(parser)  # 顶站位全局选项

    subparsers = parser.add_subparsers(dest="command", parser_class=JSONErrorParser)

    send = subparsers.add_parser("send", parents=[parent], help="执行单个请求条目并流式输出事件.")
    send.add_argument("item_ref", metavar="<item-ref>", help="条目引用, 格式 <collection>/<slug>.")
    send.add_argument("--env", default=None, help="环境名.")
    send.add_argument("--var", action="append", metavar="KEY=VALUE", help="覆盖变量 (可重复); 优先于环境变量.")
    send.set_defaults(func=cmd_send)

    run = subparsers.add_parser("run", parents=[parent], help="批量执行集合内全部条目.")
    run.add_argument("collection_ref", metavar="<collection-ref>")
    run.add_argument("--env", default=None, help="环境名.")
    run.add_argument("--var", action="append", metavar="KEY=VALUE", help="覆盖变量 (可重复); 优先于环境变量.")
    run.set_defaults(func=cmd_run)

    for group, verbs in (
        ("collection", ("list", "show")),
        ("item", ("list", "show")),
        ("env", ("list", "show")),
    ):
        group_parser = subparsers.add_parser(group, help=f"{group} 资源查询.")
        group_sub = group_parser.add_subparsers(dest=f"{group}_cmd", parser_class=JSONErrorParser)
        for verb in verbs:
            verb_parser = group_sub.add_parser(verb, parents=[parent])
            verb_parser.add_argument("ref", nargs="?", default=None)
            verb_parser.set_defaults(func=_placeholder(f"{group} {verb}"))

    history = subparsers.add_parser("history", help="执行历史查询.", epilog="示例: apic history list | apic history show <id>")
    history_sub = history.add_subparsers(dest="history_cmd", parser_class=JSONErrorParser)
    history_sub.add_parser("list", parents=[parent], help="列出最近历史条目.").set_defaults(func=cmd_history_list)
    history_show = history_sub.add_parser("show", parents=[parent], help="查看单条历史.")
    history_show.add_argument("id", metavar="<id>")
    history_show.set_defaults(func=cmd_history_show)

    service = subparsers.add_parser("service", help="服务生命周期.", epilog="示例: apic service status | apic service token")
    service_sub = service.add_subparsers(dest="service_cmd", parser_class=JSONErrorParser)
    service_sub.add_parser("status", parents=[parent], help="服务运行状态.").set_defaults(func=cmd_status)
    service_sub.add_parser("stop", parents=[parent], help="停止服务 (按 --data-dir 定位).").set_defaults(func=cmd_stop)
    service_sub.add_parser("token", parents=[parent], help="显示当前服务 token.").set_defaults(func=cmd_token)

    subparsers.add_parser("schema", parents=[parent], help="输出完整机读契约 (JSON).").set_defaults(func=_meta_placeholder("schema"))
    subparsers.add_parser("guide", parents=[parent], help="输出文读手册 (llms.txt 风格).").set_defaults(func=_meta_placeholder("guide"))
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # serve/stop 转发到 08 服务壳 (apic script 归属 CLI 后 `uv run apic serve` 不失效)
    if argv and argv[0] in ("serve", "stop"):
        return subprocess.call([sys.executable, "-m", "api_client", *argv])

    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.error("缺少命令 (见 apic --help)")

    try:
        return func(args)
    except CliError as exc:
        emit_error(exc.code, exc.message, exc.details)
        return exit_for(exc.code)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        return contract.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
