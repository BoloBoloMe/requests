"""资源 CRUD 路由薄壳 (M3 D010): 参数校验 + Store 调用 + 404/422 语义, 无业务逻辑.

文件树↔资源映射: 集合=目录, 请求条目=slug 文件 (M2 D001/D003).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from ..store import (
    CollectionConfig,
    CollectionDefaults,
    NotFoundError,
    Store,
    item_from_dict,
    item_to_dict,
    kv_seq_from_yaml,
)

# 畸形 payload 统一归 422: 归一化入口抛 ValueError, 其余类型错误一并兜底
_SHAPE_ERRORS = (KeyError, ValueError, TypeError, AttributeError)


def _str_map(raw: Any, field: str) -> dict[str, str]:
    """vars/secrets 形状校验: 非 mapping 抛 ValueError (壳层归 422)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field} 应为 mapping: {raw!r}")
    return {str(k): str(v) for k, v in raw.items()}


def create_crud_router(store: Store, require_token) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_token)])

    def _item_or_404(collection: str, slug: str, folder: str):
        try:
            return store.read_item(collection, slug, folder)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="请求条目不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    # --- 集合 ---

    @router.get("/collections")
    async def list_collections() -> dict:
        return {"collections": store.list_collections()}

    # --- 请求条目 (PUT 即 upsert) ---

    @router.get("/collections/{collection}/items")
    async def list_items(collection: str, folder: str = "") -> dict:
        try:
            entries = store.list_items(collection, folder)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="集合或文件夹不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return {"items": [{"slug": e.slug, **item_to_dict(e.item)} for e in entries]}

    @router.get("/collections/{collection}/items/{slug}")
    async def get_item(collection: str, slug: str, folder: str = "") -> dict:
        return item_to_dict(_item_or_404(collection, slug, folder))

    @router.put("/collections/{collection}/items/{slug}")
    async def put_item(collection: str, slug: str, payload: dict[str, Any], folder: str = "") -> dict:
        try:
            item = item_from_dict(payload)
            store.write_item(collection, slug, item, folder)
        except _SHAPE_ERRORS as exc:
            raise HTTPException(status_code=422, detail=f"条目字段形状非法: {exc}") from None
        return item_to_dict(item)

    @router.delete("/collections/{collection}/items/{slug}", status_code=204)
    async def delete_item(collection: str, slug: str, folder: str = "") -> Response:
        try:
            store.delete_item(collection, slug, folder)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="请求条目不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return Response(status_code=204)

    # --- 集合配置 (vars + 集合级默认, M2 D010) ---

    def _config_to_dict(config: CollectionConfig) -> dict:
        return {
            "vars": config.vars,
            "defaults": {
                "auth": config.defaults.auth,
                "headers": [
                    {"key": kv.key, "value": kv.value, **({"disabled": True} if kv.disabled else {})}
                    for kv in config.defaults.headers
                ],
            },
        }

    def _config_from_dict(data: dict) -> CollectionConfig:
        defaults_raw = data.get("defaults")
        if defaults_raw is None:
            defaults_raw = {}
        if not isinstance(defaults_raw, dict):
            raise ValueError(f"defaults 应为 mapping: {defaults_raw!r}")
        return CollectionConfig(
            vars=_str_map(data.get("vars"), "vars"),
            defaults=CollectionDefaults(
                auth=defaults_raw.get("auth"),
                headers=kv_seq_from_yaml(defaults_raw.get("headers"), "defaults.headers"),
            ),
        )

    @router.get("/collections/{collection}/collection")
    async def get_collection_config(collection: str) -> dict:
        try:
            return _config_to_dict(store.read_collection(collection))
        except NotFoundError:
            raise HTTPException(status_code=404, detail="集合不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @router.put("/collections/{collection}/collection")
    async def put_collection_config(collection: str, payload: dict[str, Any]) -> dict:
        try:
            config = _config_from_dict(payload)
            store.write_collection(collection, config)
        except _SHAPE_ERRORS as exc:
            raise HTTPException(status_code=422, detail=f"集合配置形状非法: {exc}") from None
        return _config_to_dict(config)

    # --- 环境 / secrets / 激活状态 ---

    @router.get("/environments")
    async def list_environments() -> dict:
        return {"environments": store.list_environments()}

    @router.get("/environments/{name}")
    async def get_environment(name: str) -> dict:
        try:
            env = store.read_environment(name)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="环境不存在") from None
        return {"name": env.name, "vars": env.vars, "secrets": env.secrets, "merged": env.merged}

    @router.put("/environments/{name}")
    async def put_environment(name: str, payload: dict[str, Any]) -> dict:
        try:
            vars_ = _str_map(payload.get("vars"), "vars")
            store.write_environment(name, vars_)
        except _SHAPE_ERRORS as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return {"name": name, "vars": vars_}

    @router.put("/environments/{name}/secrets")
    async def put_secrets(name: str, payload: dict[str, Any]) -> dict:
        try:
            secrets = _str_map(payload.get("secrets"), "secrets")
            store.write_secrets(name, secrets)
        except _SHAPE_ERRORS as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return {"name": name, "secrets": secrets}

    @router.get("/state")
    async def get_state() -> dict:
        return {"active_environment": store.get_active_environment()}

    @router.put("/state")
    async def put_state(payload: dict[str, Any]) -> dict:
        name = payload.get("active_environment")
        try:
            store.set_active_environment(None if name is None else str(name))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return {"active_environment": store.get_active_environment()}

    return router
