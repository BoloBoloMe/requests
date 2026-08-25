"""输出渲染原语 (M4 D002): 流式 NDJSON / 非流式单 JSON / pretty 供人.

值一律 json.dumps(..., ensure_ascii=False) 渲染 (禁 repr, dogfood 第三轮修正).
"""

import json
import sys


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def emit_object(data, mode: str = "json") -> None:
    """非流式命令单 JSON 对象; ndjson 等同单行; pretty 回退 JSON (M4 明示残留)."""
    if mode == "ndjson":
        sys.stdout.write(_dump(data) + "\n")
    else:
        sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


class EventRenderer:
    """流式事件渲染: ndjson 逐行 / pretty 每行 type 开头 / json 收集为数组."""

    def __init__(self, mode: str = "ndjson") -> None:
        self.mode = mode
        self._events: list = []

    def handle(self, event: dict) -> None:
        if self.mode == "ndjson":
            sys.stdout.write(_dump(event) + "\n")
            sys.stdout.flush()
        elif self.mode == "pretty":
            sys.stdout.write(f"{event.get('type', 'event')} {_dump(event)}\n")
            sys.stdout.flush()
        else:
            self._events.append(event)

    def finish(self) -> None:
        if self.mode == "json":
            sys.stdout.write(json.dumps(self._events, indent=2, ensure_ascii=False) + "\n")
