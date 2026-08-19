"""SSE /sse 路由."""

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/sse", tags=["sse"])


@router.get("")
async def sse(
    count: int = Query(default=5, ge=1, le=1000),
    interval: float = Query(default=0.01, ge=0.0, le=5.0),
    event: str = Query(default="message", min_length=1),
):
    async def event_generator():
        for i in range(count):
            payload = json.dumps({"seq": i, "total": count})
            yield f"event: {event}\ndata: {payload}\n\n"
            if i < count - 1:
                await asyncio.sleep(interval)

    return StreamingResponse(
        event_generator(),
        headers={
            "content-type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
