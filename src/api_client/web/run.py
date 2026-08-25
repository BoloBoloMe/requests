"""POST /collections/{c}/run 路由: Runner 批量事件流 + SSE/NDJSON 协商 (M3 D010/D007).

薄壳: 存在性/解析错误归 404/422, 业务在 Runner; 事件流末尾附 report 事件
(format=junit, content=XML 字符串, M2 D011 报告是输出物不入数据仓库).
协商与编码同 /execute (M3 D007 单一事件模型两种编码).
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..engine import Engine
from ..resolve import UnresolvedVariablesError
from ..runner import junit_xml, run_collection
from ..store import NotFoundError, Store
from .execute import _encode_ndjson, _encode_sse


def create_run_router(store: Store, require_token) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_token)])
    engine = Engine(store)

    @router.post("/collections/{collection}/run")
    async def run(collection: str, request: Request, env: str | None = None) -> StreamingResponse:
        # 急切读: 集合/环境不存在 404, 未解析变量 422 (事件流尚未开始, M4 D006)
        try:
            batch = run_collection(store, engine, collection, env_name=env)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except UnresolvedVariablesError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNRESOLVED_VARIABLES", "missing": exc.missing},
            ) from None

        # Accept 协商 (M3 D007): 同 /execute 简化语义
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            encode, media_type = _encode_sse, "text/event-stream"
        else:
            encode, media_type = _encode_ndjson, "application/x-ndjson"

        async def stream() -> AsyncIterator[str]:
            async for event in batch:
                yield encode(event)
            # report 事件附末尾 (summary 之后): JUnit XML 内容, 输出物不落盘
            yield encode(
                {
                    "type": "report",
                    "format": "junit",
                    "content": junit_xml(batch.results, suite_name=collection),
                }
            )

        return StreamingResponse(stream(), media_type=media_type)

    return router
