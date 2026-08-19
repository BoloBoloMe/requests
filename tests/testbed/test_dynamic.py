"""ISSUE-06: 动态值校验端点 /dynamic/now 与 /dynamic/uuid."""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from testbed.app import app

client = TestClient(app)

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def test_now_with_current_timestamp_is_valid():
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace("+00:00", "Z")
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert "server_now" in body
    assert ISO_RE.match(body["server_now"])


def test_now_with_z_offset_current_timestamp_is_valid():
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_now_with_future_timestamp_outside_window_returns_422():
    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    ts = future.isoformat()
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body


def test_now_with_past_timestamp_outside_window_returns_422():
    past = datetime.now(timezone.utc) - timedelta(seconds=120)
    ts = past.isoformat()
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body


def test_now_with_invalid_format_returns_422():
    response = client.get("/dynamic/now", params={"ts": "not-a-timestamp"})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body


def test_now_with_naive_timestamp_returns_422():
    """naive 时间戳缺时区, 必须 422 且 reason 指出缺时区."""
    ts = (datetime.now(timezone.utc) + timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%S")
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body
    assert "missing timezone" in body["reason"].lower()


def test_now_with_space_separator_returns_422():
    """空格分隔的非严格 ISO 形式必须 422."""
    ts = "2026-01-30 12:00:00+00:00"
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body
    assert "'T'" in body["reason"]


def test_now_missing_ts_returns_422_with_reason():
    response = client.get("/dynamic/now")
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body
    assert "server_now" in body


def test_now_exactly_60_seconds_within_window_returns_200():
    ts = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_now_61_seconds_outside_window_returns_422():
    ts = (datetime.now(timezone.utc) + timedelta(seconds=61)).isoformat()
    response = client.get("/dynamic/now", params={"ts": ts})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body


def test_uuid_with_valid_uuidv4_is_valid():
    value = str(uuid.uuid4())
    response = client.get("/dynamic/uuid", params={"uuid": value})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True


def test_uuid_with_invalid_string_returns_422():
    response = client.get("/dynamic/uuid", params={"uuid": "not-a-uuid"})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body


def test_uuid_with_non_v4_uuid_returns_422():
    value = str(uuid.uuid1())
    response = client.get("/dynamic/uuid", params={"uuid": value})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body


def test_uuid_missing_uuid_returns_422_with_reason():
    response = client.get("/dynamic/uuid")
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
    assert "reason" in body
