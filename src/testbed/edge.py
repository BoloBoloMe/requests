"""ISSUE-07: 边界端点 /status/{code}, /delay/{seconds}, /large."""

import asyncio

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

router = APIRouter(tags=["edge"])

_MAX_DELAY_SECONDS = 5.0
_MAX_LARGE_BYTES = 10 * 1024 * 1024


@router.get("/status/{code}")
async def status_code(code: int) -> Response:
    """返回指定 HTTP 状态码; 204/304 响应体必须为空."""
    if code < 200 or code > 599:
        return JSONResponse(
            status_code=422,
            content={
                "status": code,
                "valid": False,
                "reason": "Status code must be between 200 and 599",
            },
        )
    if code in (204, 304):
        return Response(status_code=code, content=b"")
    return JSONResponse(status_code=code, content={"status": code})


@router.get("/delay/{seconds}", response_model=None)
async def delay(seconds: float) -> dict[str, float] | JSONResponse:
    """asyncio.sleep 后返回实际延迟秒数; 上限 clamp 到 5s, 负值 422."""
    if seconds < 0:
        return JSONResponse(
            status_code=422,
            content={"valid": False, "reason": "seconds must be non-negative"},
        )
    actual = max(0.0, min(seconds, _MAX_DELAY_SECONDS))
    await asyncio.sleep(actual)
    return {"delayed": actual}


@router.get("/large")
async def large_bytes(size: int | None = Query(None, alias="bytes")) -> Response:
    """返回恰好 N 字节的 application/octet-stream 响应体; 上限 10MB."""
    if size is None:
        return JSONResponse(
            status_code=422,
            content={"valid": False, "reason": "Missing bytes query parameter"},
        )
    if size < 0:
        return JSONResponse(
            status_code=422,
            content={"valid": False, "reason": "bytes must be non-negative"},
        )
    if size > _MAX_LARGE_BYTES:
        return JSONResponse(
            status_code=422,
            content={
                "valid": False,
                "reason": f"bytes must not exceed {_MAX_LARGE_BYTES}",
            },
        )
    return Response(
        content=b"\x00" * size,
        media_type="application/octet-stream",
    )
