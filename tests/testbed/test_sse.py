"""ISSUE-05: SSE /sse 切片测试."""

import json
from fastapi.testclient import TestClient

from testbed.app import app

client = TestClient(app)


def _parse_sse_events(response) -> list[dict]:
    """把 text/event-stream 响应体解析为事件列表."""
    events: list[dict] = []
    current: dict = {}
    for line in response.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if not line:
            if current:
                events.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        field, value = line.split(":", 1)
        value = value.lstrip(" ")
        if field == "event":
            current["event"] = value
        elif field == "data":
            current.setdefault("data", [])
            current["data"].append(value)
    if current:
        events.append(current)
    for ev in events:
        if "data" in ev:
            ev["data"] = "\n".join(ev["data"])
    return events


def test_default_sse_returns_five_numbered_events():
    with client.stream("GET", "/sse") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["X-Accel-Buffering"] == "no"
        events = _parse_sse_events(response)

    assert len(events) == 5
    for i, ev in enumerate(events):
        assert ev["event"] == "message"
        payload = json.loads(ev["data"])
        assert payload["seq"] == i
        assert payload["total"] == 5


def test_sse_count_parameter_changes_event_count_and_total():
    with client.stream("GET", "/sse?count=3") as response:
        assert response.status_code == 200
        events = _parse_sse_events(response)

    assert len(events) == 3
    for i, ev in enumerate(events):
        payload = json.loads(ev["data"])
        assert payload["seq"] == i
        assert payload["total"] == 3


def test_sse_interval_parameter_does_not_slow_test():
    with client.stream("GET", "/sse?count=2&interval=0.001") as response:
        events = _parse_sse_events(response)
    assert len(events) == 2


def test_sse_event_query_parameter():
    with client.stream("GET", "/sse?event=chunk") as response:
        assert response.status_code == 200
        events = _parse_sse_events(response)

    assert len(events) == 5
    for ev in events:
        assert ev["event"] == "chunk"
        payload = json.loads(ev["data"])
        assert "seq" in payload
        assert payload["total"] == 5
