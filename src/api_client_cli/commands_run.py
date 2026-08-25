"""run 命令: 批量执行集合, 与 send 同构事件流 + summary (M4 D003 不吞 chunk).

执行语义 (顺序/统计/报告) 全在服务端 Runner (M3 D013), CLI 只消费渲染.
"""

from . import candidates, client
from .commands_send import parse_vars
from .errors import CliError
from .output import EventRenderer, event_failed


def cmd_run(args) -> int:
    variables = parse_vars(args.var)
    conn = client.connect(args.data_dir)
    body: dict = {"collection": args.collection_ref}
    if args.env is not None:
        body["env"] = args.env
    if variables:
        body["vars"] = variables

    renderer = EventRenderer(args.output or "ndjson")
    failed = False
    context = {"collection": args.collection_ref, "env": args.env}
    try:
        for event in conn.stream_events(f"/collections/{args.collection_ref}/run", body):
            renderer.handle(event)
            if event_failed(event):
                failed = True
    except CliError as exc:
        raise candidates.with_candidates(exc, conn, context) from exc
    renderer.finish()
    return 1 if failed else 0
