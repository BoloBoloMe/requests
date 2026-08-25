"""POST /git/bind 与 POST /git/sync RPC 路由 (M3 D010).

薄壳: git 语义全在 sync 模块 (M3 D008 只碰数据仓库文件路径);
失败原样透传 git 输出 (M3 D009), 壳只映射状态码.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..sync import SyncError, bind, sync


class BindRequest(BaseModel):
    remote_url: str


def create_git_router(data_dir: Path, require_token) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_token)])

    @router.post("/git/bind")
    async def git_bind(payload: BindRequest) -> dict[str, str]:
        remote_url = payload.remote_url.strip()
        if not remote_url:
            raise HTTPException(status_code=400, detail="remote_url 不能为空")
        try:
            bind(data_dir, remote_url)
        except SyncError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"status": "bound", "remote_url": remote_url}

    @router.post("/git/sync")
    async def git_sync() -> dict[str, str]:
        try:
            sync(data_dir)
        except SyncError as exc:
            # 未绑定/冲突/dirty 皆为前置状态不满足: 409 + 原样 git 输出
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return {"status": "synced"}

    return router
