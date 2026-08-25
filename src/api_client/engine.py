"""Engine: 可执行请求 -> 执行事件流 (meta/chunk/done) (M3 D006/D008).

内嵌服务进程, async httpx (同步 httpx 会卡死事件循环上全部 API), 事件经
asyncio.Queue 出流; SSE 断连不取消底层执行 (M3 D006). 藏 httpx/五种认证
(M1 D003)/multipart (M2 D009)/超时与响应大小内置常量 (M3 D013).
副作用只有经 Store 写历史 (M2 D011, 发送即记录).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .assertions import Response as AssertionResponse
from .assertions import evaluate
from .resolve import ResolvedRequest
from .store import Store

# 内置常量 (M3 D013, 不进配置面).
# READ_TIMEOUT < 5s: testbed /delay/{s} 上限 5s, 超时用例由此可观察 (TC-009);
# read 语义 = 等待下一字节的间隔上限, SSE 事件流不因总长被掐断.
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 4.0
WRITE_TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # testbed /large 上限 10MB, 超限用例可构造 (TC-010)

_TEXT_CONTENT_TYPES = ("text/", "application/json", "application/x-ndjson", "application/xml")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_text_content_type(content_type: str) -> bool:
    ct = content_type.split(";", 1)[0].strip().lower()
    return ct.startswith(_TEXT_CONTENT_TYPES) or ct.endswith("+json") or ct.endswith("+xml")


@dataclass
class Execution:
    """一次执行的句柄: queue 出事件 (None 为哨兵), task 跑到底 (断连不取消)."""

    queue: asyncio.Queue
    task: asyncio.Task


class Engine:
    """执行引擎; store 提供数据仓库根 (multipart 相对路径基准) 与历史写入口."""

    def __init__(self, store: Store | None = None) -> None:
        self._store = store
        self._live: set[asyncio.Task] = set()  # 强引用防任务被 GC (断连后仍跑到底)

    def start(
        self,
        request: ResolvedRequest,
        *,
        item_ref: str,
        env: str | None = None,
        collection: str | None = None,
        slug: str | None = None,
        folder: str = "",
        assertions: list[dict] | None = None,
    ) -> Execution:
        """启动执行: 立即返回, 事件经 queue 出流; 调用方放弃消费不影响执行完成.
        assertions 为条目断言定义 (M6 决策 1), 求值结果进 done.assertions (M4 D003)."""
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(
            self._run(
                request,
                queue,
                item_ref=item_ref,
                env=env,
                collection=collection,
                slug=slug,
                folder=folder,
                assertions=assertions or [],
            )
        )
        self._live.add(task)
        task.add_done_callback(self._live.discard)
        return Execution(queue=queue, task=task)

    async def execute(self, request: ResolvedRequest, **kwargs: Any) -> AsyncIterator[dict]:
        """便捷封装: start + 排干队列; 事件为 dict (meta/chunk/done, M4 D003)."""
        execution = self.start(request, **kwargs)
        while True:
            event = await execution.queue.get()
            if event is None:
                break
            yield event
        await execution.task  # 传播意外异常 (传输错误已在 _run 内转 done.error)

    # --- 内部 ---

    def _files_base_dir(self) -> Path:
        return self._store.data_dir if self._store is not None else Path.cwd()

    def _request_snapshot(
        self,
        request: ResolvedRequest,
        headers: list[tuple[str, str]],
        params: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """历史请求侧快照 (M2 D011): 记实际发送内容 (disabled 已滤除, 认证已应用);
        multipart 落文件引用路径+大小, 不内联文件内容."""
        snapshot: dict[str, Any] = {
            "method": request.method,
            "url": request.url,
            "params": [{"key": k, "value": v} for k, v in params],
            "headers": [{"key": k, "value": v} for k, v in headers],
        }
        body = request.body
        if body.type == "none":
            snapshot["body"] = None
        elif body.type in ("json", "text"):
            snapshot["body"] = {"type": body.type, "text": body.text}
        elif body.type == "form-urlencoded":
            snapshot["body"] = {
                "type": body.type,
                "params": [
                    {"key": kv.key, "value": kv.value}
                    for kv in body.params
                    if not kv.disabled
                ],
            }
        elif body.type == "multipart":
            parts: list[dict[str, Any]] = []
            for part in body.parts:
                if part.file is None:
                    parts.append({"name": part.name, "value": part.value or ""})
                    continue
                path = Path(part.file)
                if not path.is_absolute():
                    path = self._files_base_dir() / path
                try:
                    size: int | None = path.stat().st_size
                except OSError:
                    size = None
                entry: dict[str, Any] = {"name": part.name, "file": part.file, "size": size}
                if part.content_type is not None:
                    entry["contentType"] = part.content_type
                parts.append(entry)
            snapshot["body"] = {"type": "multipart", "parts": parts}
        return snapshot

    def _request_kwargs(
        self, request: ResolvedRequest
    ) -> tuple[dict[str, Any], list[tuple[str, str]], list[tuple[str, str]]]:
        """ResolvedRequest -> client.stream(...) 参数; 同时返回生效 headers/params
        (认证已应用), 供历史快照记实际发送内容 (bearer 明文进历史, M5 决策 5)."""
        headers = [(kv.key, kv.value) for kv in request.headers if not kv.disabled]
        params = [(kv.key, kv.value) for kv in request.params if not kv.disabled]
        kwargs: dict[str, Any] = {"headers": headers}
        header_names = {k.lower() for k, _ in headers}

        body = request.body
        if body.type in ("json", "text"):
            kwargs["content"] = body.text.encode("utf-8")
            if "content-type" not in header_names:
                default_ct = (
                    "application/json" if body.type == "json" else "text/plain; charset=utf-8"
                )
                headers.append(("Content-Type", default_ct))
        elif body.type == "form-urlencoded":
            kwargs["data"] = [(kv.key, kv.value) for kv in body.params if not kv.disabled]
        elif body.type == "multipart":
            data_parts: list[tuple[str, str]] = []
            file_parts: list[tuple[str, tuple[str, bytes, str]]] = []
            for part in body.parts:
                if part.file is None:
                    data_parts.append((part.name, part.value or ""))
                    continue
                path = Path(part.file)
                if not path.is_absolute():
                    path = self._files_base_dir() / path  # 仓库相对路径 (M2 D009)
                content = path.read_bytes()
                file_parts.append(
                    (part.name, (path.name, content, part.content_type or "application/octet-stream"))
                )
            # data 必须传 Mapping: httpx 0.28 下 list-of-tuples 会走弃用的 urlencoded
            # 同步流分支并忽略 files, AsyncClient 抛 RuntimeError (同名 part 折叠, 可接受)
            kwargs["data"] = dict(data_parts)
            kwargs["files"] = file_parts

        # 五种认证 (M1 D003)
        auth = request.auth
        if auth and auth.get("type") not in (None, "none"):
            auth_type = auth["type"]
            if auth_type == "basic":
                kwargs["auth"] = (str(auth.get("username", "")), str(auth.get("password", "")))
            elif auth_type == "bearer":
                headers.append(("Authorization", f"Bearer {auth.get('token', '')}"))
            elif auth_type == "apikey":
                if auth.get("in", "header") == "query":
                    params.append((str(auth.get("key", "")), str(auth.get("value", ""))))
                else:
                    headers.append((str(auth.get("key", "")), str(auth.get("value", ""))))
            elif auth_type == "digest":
                kwargs["auth"] = httpx.DigestAuth(
                    str(auth.get("username", "")), str(auth.get("password", ""))
                )
            else:
                raise ValueError(f"未知认证类型: {auth_type!r}")
        if params:
            # 空 params 也要避开: httpx 收到 params=[] 会重建 query string,
            # 把 url 里已有的 ?a=1 整个抹掉 (TC-010 抓到的真 bug);
            # 赋值放在认证处理后: apikey in=query 可能追加 params
            kwargs["params"] = params
        return kwargs, headers, params

    async def _run(
        self,
        request: ResolvedRequest,
        queue: asyncio.Queue,
        *,
        item_ref: str,
        env: str | None,
        collection: str | None,
        slug: str | None,
        folder: str,
        assertions: list[dict],
    ) -> None:
        start = time.monotonic()

        def done_event(
            status: int | None,
            error: dict | None = None,
            assertion_results: list[dict] | None = None,
        ) -> dict:
            event = {
                "type": "done",
                "timestamp": _now_iso(),
                "item": item_ref,
                "status": status,
                "duration_ms": int((time.monotonic() - start) * 1000),
                "assertions": assertion_results or [],  # M4 D003: 每条 定义/ok/actual/message
            }
            # 断言失败反映在 done.status (不中断执行; 供 ISSUE-05 runner 统计对齐)
            if assertion_results and not all(r["ok"] for r in assertion_results):
                event["status"] = "assert_failed"
            if error is not None:
                # 三态钉死: 传输失败 done.status 强制 None (不留已到的 HTTP 码),
                # 避免下游见 status 有值误判传输成功 (error 是唯一失败信号)
                event["status"] = None
                event["error"] = error  # 传输失败可观察 (超时/大小超限), 仅失败时出现
            return event

        await queue.put(
            {
                "type": "meta",
                "timestamp": _now_iso(),
                "item_ref": item_ref,
                "item": item_ref,
                "method": request.method,
                "resolved_url": request.url,
                "env": env,
            }
        )

        timeout = httpx.Timeout(
            connect=CONNECT_TIMEOUT_SECONDS,
            read=READ_TIMEOUT_SECONDS,
            write=WRITE_TIMEOUT_SECONDS,
            pool=5.0,
        )
        status: int | None = None
        error: dict | None = None
        chunk_index = 0
        # 历史捕获 (M2 D011): sent=False 表示请求未发出 (构造失败), 不落历史
        sent = False
        is_sse = False
        response_headers: list[dict[str, str]] = []
        eff_headers: list[tuple[str, str]] = []
        eff_params: list[tuple[str, str]] = []
        content_type = ""
        body_text: str | None = None
        body_size = 0
        sse_payloads: list[str] = []
        try:
            kwargs, eff_headers, eff_params = self._request_kwargs(request)
            sent = True
            # trust_env=False: 绕开环境代理变量 (SOCKS 代理会把本机回环也劫走)
            async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
                async with client.stream(request.method, request.url, **kwargs) as resp:
                    status = resp.status_code
                    response_headers = [
                        {"key": k, "value": v} for k, v in resp.headers.multi_items()
                    ]
                    content_type = resp.headers.get("content-type", "")
                    if content_type.startswith("text/event-stream"):
                        is_sse = True
                        async for payload in _iter_sse_data(resp):
                            sse_payloads.append(payload)
                            await queue.put(
                                {
                                    "type": "chunk",
                                    "timestamp": _now_iso(),
                                    "item": item_ref,
                                    "index": chunk_index,
                                    "data": payload,
                                }
                            )
                            chunk_index += 1
                    else:
                        parts: list[bytes] = []
                        async for data in resp.aiter_bytes():
                            body_size += len(data)
                            if body_size > MAX_RESPONSE_BYTES:
                                error = {
                                    "code": "RESPONSE_TOO_LARGE",
                                    "message": f"响应超过大小上限 {MAX_RESPONSE_BYTES} 字节",
                                }
                                break
                            parts.append(data)
                        if error is None and _is_text_content_type(content_type):
                            body_text = b"".join(parts).decode("utf-8", errors="replace")
                            await queue.put(
                                {
                                    "type": "chunk",
                                    "timestamp": _now_iso(),
                                    "item": item_ref,
                                    "index": chunk_index,
                                    "data": body_text,
                                }
                            )
        except httpx.TimeoutException:
            error = {"code": "TIMEOUT", "message": "请求超时 (内置超时常量)"}
        except (httpx.TransportError, OSError) as exc:
            error = {"code": "REQUEST_FAILED", "message": str(exc)}
        except Exception as exc:
            # 未预期异常 (如未知认证类型 ValueError, HTTP 段之外): done 带 error 后重抛,
            # 由 execute() 排干队列后 await task 传播给调用方
            error = {"code": "UNEXPECTED_ERROR", "message": f"{type(exc).__name__}: {exc}"}
            raise
        finally:
            # 断言求值 (M6 决策 1): 拿到响应且传输未失败才求值; 失败不中断.
            # 先于落历史: 历史记录捎带断言计数 (M10 协调: GET /history 条目形状)
            assertion_results: list[dict] | None = None
            if assertions and status is not None and error is None:
                snapshot = AssertionResponse(
                    status=status,
                    headers={h["key"]: h["value"] for h in response_headers},
                    body_text=body_text or "",  # 二进制体无文本: 按非 JSON 降级 (决策 3)
                    elapsed_ms=(time.monotonic() - start) * 1000,
                )
                assertion_results = [
                    {
                        "assertion": r.assertion,
                        "ok": r.ok,
                        "actual": r.actual,
                        "message": r.message,
                    }
                    for r in evaluate(snapshot, assertions)
                ]
            # SSE 未关闭不落 (M2 D011): 流中途出错 (超时/断线) 不聚合落盘
            if sent and not (is_sse and error is not None):
                self._write_history(
                    request,
                    eff_headers,
                    eff_params,
                    item_ref=item_ref,
                    env=env,
                    collection=collection,
                    slug=slug,
                    folder=folder,
                    status=status,
                    response_headers=response_headers,
                    content_type=content_type,
                    is_sse=is_sse,
                    sse_payloads=sse_payloads,
                    body_text=body_text,
                    body_size=body_size,
                    error=error,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    assertion_results=assertion_results,
                )
            # 收尾必达 (防挂): 任何路径都发 done + 哨兵, 消费者 queue.get() 不会永久阻塞
            await queue.put(done_event(status, error, assertion_results))
            await queue.put(None)  # 哨兵
    # --- 历史写入口 (M2 D011: 发送即记录, 副作用经 Store; 不脱敏 M5 决策 5) ---

    def _write_history(
        self,
        request: ResolvedRequest,
        headers: list[tuple[str, str]],
        params: list[tuple[str, str]],
        *,
        item_ref: str,
        env: str | None = None,
        collection: str | None,
        slug: str | None,
        folder: str,
        status: int | None,
        response_headers: list[dict[str, str]],
        content_type: str,
        is_sse: bool,
        sse_payloads: list[str],
        body_text: str | None,
        body_size: int,
        error: dict | None,
        duration_ms: int,
        assertion_results: list[dict] | None = None,
    ) -> None:
        if self._store is None or not collection or not slug:
            return  # 无仓库或无定位信息: 纯执行 (如引擎单测), 不落历史
        record: dict[str, Any] = {
            "timestamp": _now_iso(),
            "item": item_ref,
            "env": env,
            "duration_ms": duration_ms,
            "request": self._request_snapshot(request, headers, params),
        }
        if assertion_results is not None:
            # 断言计数 (M10 协调: GET /history 条目形状, 全文不落明细)
            record["assertions"] = {
                "passed": sum(1 for r in assertion_results if r["ok"]),
                "failed": sum(1 for r in assertion_results if not r["ok"]),
            }
        if status is None:
            record["response"] = None  # 响应头都没等到 (如超时)
        else:
            if is_sse:
                # 连接已关闭: 已收事件聚合为一个文本体 (M2 D011)
                response_body: dict[str, Any] = {
                    "kind": "text",
                    "content_type": content_type,
                    "text": "\n\n".join(sse_payloads),
                }
            elif body_text is not None:
                response_body = {
                    "kind": "text",
                    "content_type": content_type,
                    "text": body_text,
                }
            else:
                # 非文本或超大 body 只落元信息 (content-type/大小)
                response_body = {
                    "kind": "binary",
                    "content_type": content_type,
                    "size": body_size,
                }
            record["response"] = {
                "status": status,
                "headers": response_headers,
                "body": response_body,
            }
        if error is not None:
            record["error"] = error
        self._store.append_history(collection, slug, record, folder)


async def _iter_sse_data(resp: httpx.Response) -> AsyncIterator[str]:
    """逐帧解析 text/event-stream, 产出各帧 data 载荷 (多行 data 以 \\n 连接)."""
    data_lines: list[str] = []
    async for line in resp.aiter_lines():
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith(":"):
            continue  # 注释/心跳行
        if line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip(" "))
    if data_lines:
        yield "\n".join(data_lines)
