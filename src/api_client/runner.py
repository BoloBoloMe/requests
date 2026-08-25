"""Runner: 集合 -> 批量事件流 + JUnit 报告 (M3 D008).

顺序执行 (M3 D013, v1 不并发): 逐条复用 Engine 完整事件流 (meta/chunk/done,
不吞 chunk, M4 D003), 断言失败不中断后续条目; 单条目意外异常 (如未知认证类型)
隔离为该条失败 (status=null + error.code=UNEXPECTED_ERROR), 不中断整批 (D-AFK-009);
末尾发 summary.
统计口径: passed/failed 按断言 ok 计数 (done.status 为 int 且非 assert_failed
即 passed; 断言失败或传输失败计 failed, ISSUE-10 CLI 消费 summary 同口径).
JUnit 报告为输出物, 手写最小 XML (xml.etree), 不入数据仓库 (M2 D011).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .engine import Engine
from .resolve import build_request
from .store import Item, Store


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunResult:
    """单条目运行结果: summary.items 与 junit_xml 的共同输入."""

    item: str  # item_ref, 形如 "collection/slug"
    name: str  # 条目显示名 (testcase name)
    classname: str  # 集合名 (testcase classname, pytest --junitxml 惯例)
    status: int | str | None  # done.status 三态: int / "assert_failed" / None(传输失败)
    duration_ms: int
    assertions: list[dict]
    error: dict | None

    @property
    def passed(self) -> bool:
        return self.status is not None and self.status != "assert_failed"


class Run:
    """一次批量运行的句柄: 异步迭代出事件流; results 在流排干后完整 (供报告组装)."""

    def __init__(
        self,
        engine: Engine,
        collection: str,
        env_name: str | None,
        prepared: list[tuple[str, Item, Any]],
    ) -> None:
        self._engine = engine
        self._collection = collection
        self._env_name = env_name
        self._prepared = prepared
        self.results: list[RunResult] = []

    def __aiter__(self) -> AsyncIterator[dict]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[dict]:
        # 顺序遍历 (D013): 逐条排干 Engine 完整事件流 (不吞 chunk, M4 D003)
        for slug, item, resolved in self._prepared:
            item_ref = f"{self._collection}/{slug}"
            done: dict | None = None
            try:
                async for event in self._engine.execute(
                    resolved,
                    item_ref=item_ref,
                    env=self._env_name,
                    collection=self._collection,
                    slug=slug,
                    assertions=item.assertions,  # 结果进 done.assertions (M4 D003)
                ):
                    if event["type"] == "done":
                        done = event
                    yield event
            except Exception as exc:
                # 单条目意外异常不中断整批 (D-AFK-009): Engine 收尾已把失败 done
                # (status=null + error.code=UNEXPECTED_ERROR) 入队出流, 此处吞掉异常
                # 继续后续条目; 仅捕获 Exception, 不吞取消/GeneratorExit
                if done is None:
                    # 极端路径防御 (异常发生在 done 出流前): 补一个同词汇的失败 done,
                    # 保住 每条目必有 done 的事件流不变式
                    done = {
                        "type": "done",
                        "timestamp": _now_iso(),
                        "item": item_ref,
                        "status": None,
                        "duration_ms": 0,
                        "assertions": [],
                        "error": {
                            "code": "UNEXPECTED_ERROR",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    }
                    yield done
            # 断言失败/意外异常不中断: 只记录结果, 继续下一条目
            self.results.append(
                RunResult(
                    item=item_ref,
                    name=item.name,
                    classname=self._collection,
                    status=done["status"],
                    duration_ms=done["duration_ms"],
                    assertions=done["assertions"],
                    error=done.get("error"),
                )
            )
        passed = sum(1 for r in self.results if r.passed)
        yield {
            "type": "summary",
            "timestamp": _now_iso(),
            "total": len(self.results),
            "passed": passed,
            "failed": len(self.results) - passed,
            "items": [
                {"item": r.item, "status": r.status, "passed": r.passed}
                for r in self.results
            ],
        }


def run_collection(
    store: Store,
    engine: Engine,
    collection: str,
    env_name: str | None = None,
    *,
    vars: dict[str, str] | None = None,
) -> Run:
    """急切完成 集合/环境/条目读取与变量解析后返回 Run 句柄.

    NotFoundError (集合/环境不存在) 与 UnresolvedVariablesError 在调用点同步抛出,
    事件流尚未开始 (M4 D006: 未解析变量硬失败, 不产生事件流); 壳层归 404/422.
    env_name 缺省读激活环境 (M2 D007).
    vars 为调用方一次性覆盖层 (D-AFK-011), 透传 build_request, 优先级最高.
    """
    config = store.read_collection(collection)
    if env_name is None:
        env_name = store.get_active_environment()
    env = store.read_environment(env_name) if env_name is not None else None
    prepared = [
        (entry.slug, entry.item, build_request(entry.item, env, config, vars=vars))
        for entry in store.list_items(collection)
    ]
    return Run(engine, collection, env_name, prepared)


def junit_xml(results: list[RunResult], suite_name: str = "api-client") -> str:
    """RunResult 列表 -> JUnit XML 字符串 (最小结构, 类 pytest --junitxml).

    failures = 断言失败条目数, errors = 传输失败条目数 (口径与 summary 一致);
    失败条目 failure 元素 message = 首条失败断言消息, 传输失败用 error 元素.
    """
    failures = sum(1 for r in results if r.status == "assert_failed")
    errors = sum(1 for r in results if r.status is None)
    total_ms = sum(r.duration_ms for r in results)
    testsuite = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": str(len(results)),
            "failures": str(failures),
            "errors": str(errors),
            "time": f"{total_ms / 1000:.3f}",
        },
    )
    for r in results:
        case = ET.SubElement(
            testsuite,
            "testcase",
            {
                "name": r.name,
                "classname": r.classname,
                "time": f"{r.duration_ms / 1000:.3f}",
            },
        )
        if r.error is not None:
            element = ET.SubElement(case, "error", {"message": r.error["message"]})
            element.text = r.error["message"]
        elif r.status == "assert_failed":
            message = next(
                (a["message"] for a in r.assertions if not a["ok"]),
                "断言失败",
            )
            element = ET.SubElement(case, "failure", {"message": message})
            element.text = message
    return ET.tostring(testsuite, encoding="unicode", xml_declaration=True)
