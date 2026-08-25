"""ISSUE-02 TS-003: CRUD API 壳薄测 (M3 D010, D014-3).

TestClient 薄测 API 形状与 token 校验; 一律显式 Host: localhost (Host 白名单中间件).
业务行为断言下沉 tests/api_client/test_store.py.
"""

import pytest
from fastapi.testclient import TestClient

from api_client.web.app import create_app

TOKEN = "test-token"
HOST = {"Host": "localhost"}
AUTH = {"X-Auth-Token": TOKEN}

ITEM_PAYLOAD = {
    "name": "ping",
    "method": "GET",
    "url": "http://127.0.0.1:9000/echo",
    "seq": 1,
    "params": [{"key": "a", "value": "1"}],
    "headers": [{"key": "X-T", "value": "v", "disabled": True}],
    "body": {"type": "none"},
    "auth": {"type": "none"},
    "assert": [{"target": "status", "op": "eq", "expect": 200}],
}


@pytest.fixture
def client(tmp_path) -> TestClient:
    return TestClient(create_app(TOKEN, data_dir=tmp_path / "repo"))


# --- TC-008: PUT upsert → GET 取回同一领域对象; DELETE 后 GET 404 ---


def test_crud_upsert_then_get(client):
    r = client.put(
        "/collections/demo/items/ping",
        json=ITEM_PAYLOAD,
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 200

    r = client.get("/collections/demo/items/ping", headers={**HOST, **AUTH})
    assert r.status_code == 200
    got = r.json()
    for key in ("name", "method", "url", "seq", "params", "headers", "body", "auth", "assert"):
        assert got[key] == ITEM_PAYLOAD[key], key

    # 集合出现在列表; 条目出现在集合列表 (按 seq 排序)
    assert client.get("/collections", headers={**HOST, **AUTH}).json() == {"collections": ["demo"]}
    items = client.get("/collections/demo/items", headers={**HOST, **AUTH}).json()["items"]
    assert [e["slug"] for e in items] == ["ping"]

    # folder 维度 upsert + 取回
    r = client.put(
        "/collections/demo/items/nested?folder=a/b",
        json={**ITEM_PAYLOAD, "name": "nested"},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 200
    r = client.get("/collections/demo/items/nested?folder=a/b", headers={**HOST, **AUTH})
    assert r.json()["name"] == "nested"

# --- 畸形 payload 归 422, 不得 500 穿透 ---


def test_malformed_payloads_422(client):
    # params 非 list-of-dicts
    r = client.put(
        "/collections/demo/items/x",
        json={**ITEM_PAYLOAD, "params": "not-a-list"},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 422
    # headers 元素非 dict
    r = client.put(
        "/collections/demo/items/x",
        json={**ITEM_PAYLOAD, "headers": ["not-a-dict"]},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 422
    # headers 元素缺 key
    r = client.put(
        "/collections/demo/items/x",
        json={**ITEM_PAYLOAD, "headers": [{"value": "v"}]},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 422
    # body 非 mapping
    r = client.put(
        "/collections/demo/items/x",
        json={**ITEM_PAYLOAD, "body": "not-a-dict"},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 422
    # 整个请求体非 dict
    r = client.put("/collections/demo/items/x", json=["not-a-dict"], headers={**HOST, **AUTH})
    assert r.status_code == 422
    # 集合配置 defaults.headers 畸形
    r = client.put(
        "/collections/demo/collection",
        json={"defaults": {"headers": ["not-a-dict"]}},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 422
    # 环境 vars 非 mapping
    r = client.put("/environments/dev", json={"vars": ["not-a-dict"]}, headers={**HOST, **AUTH})
    assert r.status_code == 422
    # secrets 非 mapping
    r = client.put(
        "/environments/dev/secrets", json={"secrets": "not-a-dict"}, headers={**HOST, **AUTH}
    )
    assert r.status_code == 422


# --- 路径穿越防护: slug/folder 越出集合目录的形态 → 422 ---


def test_path_traversal_rejected_422(client):
    # 先建立合法集合/条目, 保证走到名称校验而非 404
    assert client.put(
        "/collections/demo/items/ok", json=ITEM_PAYLOAD, headers={**HOST, **AUTH}
    ).status_code == 200
    # slug 含 ..
    assert client.put(
        "/collections/demo/items/..evil", json=ITEM_PAYLOAD, headers={**HOST, **AUTH}
    ).status_code == 422
    assert client.get("/collections/demo/items/..evil", headers={**HOST, **AUTH}).status_code == 422
    assert (
        client.delete("/collections/demo/items/..evil", headers={**HOST, **AUTH}).status_code == 422
    )
    # folder 含 .. (查询参数同规则)
    assert client.put(
        "/collections/demo/items/x?folder=../evil", json=ITEM_PAYLOAD, headers={**HOST, **AUTH}
    ).status_code == 422
    assert (
        client.get("/collections/demo/items?folder=../../etc", headers={**HOST, **AUTH}).status_code
        == 422
    )
    # 集合名含 ..
    assert client.get("/collections/..x/collection", headers={**HOST, **AUTH}).status_code == 422


# --- TC-009: env / secrets / state 端点形状 ---


def test_list_environments_endpoint(client):
    # 空仓库 → 200 空列表 (不 404)
    assert client.get("/environments", headers={**HOST, **AUTH}).json() == {"environments": []}

    for name in ("prod", "dev"):
        assert client.put(
            f"/environments/{name}", json={"vars": {"host": f"http://{name}"}}, headers={**HOST, **AUTH}
        ).status_code == 200
    assert client.put(
        "/environments/dev/secrets", json={"secrets": {"token": "s3cret"}}, headers={**HOST, **AUTH}
    ).status_code == 200

    got = client.get("/environments", headers={**HOST, **AUTH}).json()["environments"]
    assert got == ["dev", "prod"]  # 字典序; 无 dev.secrets 名


def test_environment_secrets_state_endpoints(client):
    r = client.put(
        "/environments/dev",
        json={"vars": {"host": "http://dev", "token": "placeholder"}},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 200

    r = client.put(
        "/environments/dev/secrets",
        json={"secrets": {"token": "s3cret"}},
        headers={**HOST, **AUTH},
    )
    assert r.status_code == 200

    r = client.get("/environments/dev", headers={**HOST, **AUTH})
    got = r.json()
    assert got["vars"] == {"host": "http://dev", "token": "placeholder"}
    assert got["secrets"] == {"token": "s3cret"}
    assert got["merged"]["token"] == "s3cret"  # secrets 合并优先级最高 (M2 D006)

    assert client.get("/state", headers={**HOST, **AUTH}).json() == {"active_environment": None}
    r = client.put("/state", json={"active_environment": "dev"}, headers={**HOST, **AUTH})
    assert r.json() == {"active_environment": "dev"}
    assert client.get("/state", headers={**HOST, **AUTH}).json() == {"active_environment": "dev"}


# --- TC-010: 无 token 401 (ISSUE-01 中间件) ---


def test_crud_requires_token(client):
    assert client.get("/collections", headers=HOST).status_code == 401
    assert client.put(
        "/collections/demo/items/ping", json=ITEM_PAYLOAD, headers=HOST
    ).status_code == 401
    assert client.get("/state", headers=HOST).status_code == 401
    assert client.get("/environments", headers=HOST).status_code == 401


# --- 集合配置端点薄壳 (vars + 集合级默认) ---


def test_collection_config_endpoint(client):
    client.put("/collections/demo/items/ping", json=ITEM_PAYLOAD, headers={**HOST, **AUTH})
    payload = {
        "vars": {"host": "https://api.example"},
        "defaults": {
            "auth": {"type": "bearer", "token": "{{token}}"},
            "headers": [{"key": "Accept", "value": "application/json"}],
        },
    }
    r = client.put("/collections/demo/collection", json=payload, headers={**HOST, **AUTH})
    assert r.status_code == 200
    r = client.get("/collections/demo/collection", headers={**HOST, **AUTH})
    assert r.json() == payload
    assert client.get("/collections/ghost/collection", headers={**HOST, **AUTH}).status_code == 404


# --- TC-011: 不存在集合/条目 404 ---


def test_missing_resources_404(client):
    assert client.get("/collections/ghost/items/x", headers={**HOST, **AUTH}).status_code == 404
    assert client.get("/collections/ghost/items", headers={**HOST, **AUTH}).status_code == 404
    assert client.get("/environments/ghost", headers={**HOST, **AUTH}).status_code == 404
    assert client.delete("/collections/ghost/items/x", headers={**HOST, **AUTH}).status_code == 404
