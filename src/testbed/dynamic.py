"""ISSUE-06: 动态值校验端点."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/dynamic")

WINDOW_SECONDS = 60


class NowResponse(BaseModel):
    valid: bool
    server_now: str


class NowErrorResponse(BaseModel):
    valid: bool
    reason: str
    server_now: str


class UuidResponse(BaseModel):
    valid: bool


class UuidErrorResponse(BaseModel):
    valid: bool
    reason: str


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _error_422(reason: str, server_now: str | None = None) -> JSONResponse:
    content: dict[str, object] = {"valid": False, "reason": reason}
    if server_now is not None:
        content["server_now"] = server_now
    return JSONResponse(status_code=422, content=content)


def _parse_iso8601(value: str) -> datetime:
    """解析 ISO 8601 时间戳, 要求 'T' 分隔符且带时区, 容忍 Z 后缀."""
    text = value.strip()
    if "T" not in text:
        raise ValueError("ISO 8601 timestamp must use 'T' separator between date and time")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("missing timezone")
    return parsed


@router.get(
    "/now",
    response_model=NowResponse,
    responses={422: {"model": NowErrorResponse}},
)
async def validate_now(ts: Optional[str] = Query(None)):
    server_now = _now_utc()
    server_now_str = server_now.isoformat().replace("+00:00", "Z")
    if ts is None:
        return _error_422("Missing ts query parameter", server_now_str)

    try:
        parsed = _parse_iso8601(ts)
    except ValueError as exc:
        return _error_422(f"Invalid ISO 8601 timestamp: {exc}", server_now_str)

    delta = abs((parsed - server_now).total_seconds())
    if delta > WINDOW_SECONDS:
        return _error_422(
            f"Timestamp {delta:.1f}s outside ±{WINDOW_SECONDS}s window",
            server_now_str,
        )

    return NowResponse(
        valid=True,
        server_now=server_now_str,
    )


@router.get(
    "/uuid",
    response_model=UuidResponse,
    responses={422: {"model": UuidErrorResponse}},
)
async def validate_uuid(uuid_value: Optional[str] = Query(None, alias="uuid")):
    if uuid_value is None:
        return _error_422("Missing uuid query parameter")

    try:
        parsed = uuid.UUID(uuid_value)
    except ValueError as exc:
        return _error_422(f"Invalid UUID: {exc}")

    if parsed.version != 4:
        return _error_422(f"Expected UUIDv4, got version {parsed.version}")

    return UuidResponse(valid=True)
