"""POST /execute 路由 + SSE/NDJSON 协商 + 历史只读端点 (M3 D007/D010, M2 D011).

薄壳: 参数校验 + Resolve/Engine/Store 串联, 无业务逻辑. 事件模型与 Engine 相同
(meta/chunk/done, M4 D003), 仅编码不同 (M3 D007 单一事件模型按 Accept 协商).
断连不取消执行 (M3 D006): 客户端断开只停消费, Engine 任务跑到底并落历史.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..engine import Engine
from ..resolve import UnresolvedVariablesError, build_request
from ..store import NotFoundError, Store


def _encode_sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def _encode_ndjson(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def create_execute_router(store: Store, require_token) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_token)])
    engine = Engine(store)

    @router.post("/execute")
    async def execute(request: Request) -> StreamingResponse:
        try:
            payload: dict[str, Any] = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="请求体应为 JSON") from None
        collection = payload.get("collection")
        slug = payload.get("item")
        folder = str(payload.get("folder") or "")
        if not isinstance(collection, str) or not isinstance(slug, str):
            raise HTTPException(status_code=422, detail="请求体需含 collection 与 item")

        # env 缺省读激活环境 (M2 D007)
        env_name = payload.get("env")
        if env_name is None:
            env_name = store.get_active_environment()
        env_name = None if env_name is None else str(env_name)

        try:
            item = store.read_item(collection, slug, folder)
            config = store.read_collection(collection)
            env = store.read_environment(env_name) if env_name is not None else None
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        try:
            resolved = build_request(item, env, config)
        except UnresolvedVariablesError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNRESOLVED_VARIABLES", "missing": exc.missing},
            ) from None

        item_ref = f"{collection}/{slug}"
        execution = engine.start(
            resolved,
            item_ref=item_ref,
            env=env_name,
            collection=collection,
            slug=slug,
            folder=folder,
        )

        # Accept 协商 (M3 D007): 明确要求 SSE 才走 SSE, 其余一律 NDJSON
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            encode, media_type = _encode_sse, "text/event-stream"
        else:
            encode, media_type = _encode_ndjson, "application/x-ndjson"

        async def stream() -> AsyncIterator[str]:
            while True:
                event = await execution.queue.get()
                if event is None:  # 哨兵: 执行收尾
                    break
                yield encode(event)
            # 客户端中途断开时本生成器被取消, 只停消费; execution.task 由
            # Engine._live 强引用持有, 跑到底并落历史 (M3 D006 断连不取消)

        return StreamingResponse(stream(), media_type=media_type)

    # --- 历史只读端点 (M2 D011) ---

    @router.get("/history/{collection}/{slug}")
    async def list_history(collection: str, slug: str, folder: str = "") -> dict:
        try:
            entries = store.list_history(collection, slug, folder)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return {"entries": entries}

    return router
