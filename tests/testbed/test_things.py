"""ISSUE-02: CRUD /things 切片测试."""

from fastapi.testclient import TestClient

from testbed.app import app

client = TestClient(app)


def test_post_then_get_returns_same_content():
    payload = {"content": "hello things"}
    create_response = client.post("/things", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    thing_id = created["id"]
    assert created["content"] == payload["content"]

    get_response = client.get(f"/things/{thing_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == thing_id
    assert fetched["content"] == payload["content"]


def test_put_then_get_returns_updated_content():
    payload = {"content": "initial"}
    create_response = client.post("/things", json=payload)
    assert create_response.status_code == 201
    thing_id = create_response.json()["id"]

    update = {"content": "updated"}
    put_response = client.put(f"/things/{thing_id}", json=update)
    assert put_response.status_code == 200
    assert put_response.json()["id"] == thing_id
    assert put_response.json()["content"] == update["content"]

    get_response = client.get(f"/things/{thing_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == thing_id
    assert fetched["content"] == update["content"]


def test_delete_then_get_returns_404():
    payload = {"content": "to delete"}
    create_response = client.post("/things", json=payload)
    assert create_response.status_code == 201
    thing_id = create_response.json()["id"]

    delete_response = client.delete(f"/things/{thing_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/things/{thing_id}")
    assert get_response.status_code == 404


def test_get_nonexistent_id_returns_404():
    response = client.get("/things/-1")
    assert response.status_code == 404


def test_put_nonexistent_id_returns_404():
    response = client.put("/things/-1", json={"content": "ignored"})
    assert response.status_code == 404


def test_delete_nonexistent_id_returns_404():
    response = client.delete("/things/-1")
    assert response.status_code == 404
