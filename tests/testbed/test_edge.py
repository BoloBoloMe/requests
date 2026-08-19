"""ISSUE-07: 边界端点 /status/{code}, /delay/{seconds}, /large."""

import time

import pytest
from fastapi.testclient import TestClient

from testbed.app import app

client = TestClient(app)


@pytest.fixture
def stub_sleep(monkeypatch):
    """把 edge.asyncio.sleep 替换成记录实参的 async no-op 桩."""
    captured = []

    async def fake_sleep(seconds):
        captured.append(seconds)

    monkeypatch.setattr("testbed.edge.asyncio.sleep", fake_sleep)
    return captured


def test_status_503_returns_503_and_body():
    response = client.get("/status/503")
    assert response.status_code == 503
    assert response.json() == {"status": 503}


def test_status_200_returns_200_and_body():
    response = client.get("/status/200")
    assert response.status_code == 200
    assert response.json() == {"status": 200}


def test_status_599_returns_599_and_body():
    response = client.get("/status/599")
    assert response.status_code == 599
    assert response.json() == {"status": 599}


def test_status_204_returns_empty_body():
    response = client.get("/status/204")
    assert response.status_code == 204
    assert response.content == b""


def test_status_304_returns_empty_body():
    response = client.get("/status/304")
    assert response.status_code == 304
    assert response.content == b""


def test_status_below_200_returns_422():
    response = client.get("/status/199")
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 199
    assert body["valid"] is False


def test_status_above_599_returns_422():
    response = client.get("/status/600")
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 600
    assert body["valid"] is False


def test_delay_0_2_takes_at_least_0_2_seconds():
    start = time.monotonic()
    response = client.get("/delay/0.2")
    elapsed = time.monotonic() - start
    assert response.status_code == 200
    assert response.json() == {"delayed": 0.2}
    assert elapsed >= 0.2
    assert elapsed < 2.0


def test_delay_above_5_seconds_is_clamped_to_5(stub_sleep):
    response = client.get("/delay/5.5")
    assert response.status_code == 200
    assert response.json() == {"delayed": 5.0}
    assert stub_sleep == [5.0]


def test_delay_negative_returns_422():
    response = client.get("/delay/-1")
    assert response.status_code == 422


def test_large_1mb_returns_exactly_1048576_bytes():
    response = client.get("/large", params={"bytes": 1048576})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert len(response.content) == 1048576
    assert response.content == b"\x00" * 1048576


def test_large_over_10mb_returns_422():
    response = client.get("/large", params={"bytes": 10 * 1024 * 1024 + 1})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False


def test_large_negative_bytes_returns_422():
    response = client.get("/large", params={"bytes": -1})
    assert response.status_code == 422
    body = response.json()
    assert body["valid"] is False
