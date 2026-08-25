"""send 命令: 执行单个请求条目并渲染事件流 (M4 D002/D003/D004/D006).

CLI 只做参数解析/输出渲染/错误映射; 变量解析/断言求值/执行全在服务端 (M3 D001).
"""

from . import candidates, client
from .errors import CliError
from .output import EventRenderer, event_failed


def parse_item_ref(ref: str) -> tuple[str, str]:
    """item-ref 格式校验 <collection>/<slug>; 存在性交服务端判定 (M4 D004)."""
    parts = ref.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise CliError("USAGE_ERROR", f"item-ref 应为 <collection>/<slug>, 得到: {ref!r}")
    return parts[0], parts[1]


def parse_vars(pairs: list[str] | None) -> dict[str, str]:
    """--var KEY=VALUE 解析; 缺 '=' 为用法错误."""
    variables: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise CliError("USAGE_ERROR", f"--var 应为 KEY=VALUE, 得到: {pair!r}")
        key, value = pair.split("=", 1)
        if not key:
            raise CliError("USAGE_ERROR", f"--var 应为 KEY=VALUE, 得到: {pair!r}")
        variables[key] = value
    return variables


def cmd_send(args) -> int:
    collection, slug = parse_item_ref(args.item_ref)
    variables = parse_vars(args.var)
    conn = client.connect(args.data_dir)
    body: dict = {"collection": collection, "item": slug}
    if args.env is not None:
        body["env"] = args.env
    if variables:
        body["vars"] = variables

    renderer = EventRenderer(args.output or "ndjson")
    failed = False
    context = {"collection": collection, "item": slug, "env": args.env}
    try:
        for event in conn.stream_events("/execute", body):
            renderer.handle(event)
            if event_failed(event):
                failed = True
    except CliError as exc:
        raise candidates.with_candidates(exc, conn, context) from exc
    renderer.finish()
    return 1 if failed else 0
