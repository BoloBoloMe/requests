"""ISSUE-01: echo 端点切片测试."""

from fastapi.testclient import TestClient

from testbed.app import app

client = TestClient(app)


def test_get_echo_with_query_and_custom_header():
    response = client.get(
        "/echo?foo=bar&baz=qux",
        headers={"X-Custom": "hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "GET"
    assert data["url"] == "/echo?foo=bar&baz=qux"
    assert data["query"] == {"foo": "bar", "baz": "qux"}
    assert data["headers"]["x-custom"] == "hello"


def test_post_echo_with_json_body():
    payload = {"name": "test", "value": 42}
    response = client.post("/echo?foo=bar", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "POST"
    assert data["url"] == "/echo?foo=bar"
    assert data["query"] == {"foo": "bar"}
    assert data["body"] == payload


def test_post_echo_with_text_body():
    text = "hello world"
    response = client.post(
        "/echo?baz=qux",
        content=text,
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "POST"
    assert data["url"] == "/echo?baz=qux"
    assert data["query"] == {"baz": "qux"}
    assert data["body"]["text"] == text
    assert data["body"]["content_type"].startswith("text/plain")
