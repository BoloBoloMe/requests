"""FastAPI 应用工厂: 服务骨架 (health 路由 + token 校验 + 安全中间件).

不装 CORSMiddleware: 默认不放行任何跨站 origin (D004-3).
"""

from pathlib import Path

from fastapi import Depends, FastAPI

from ..store import Store
from .crud import create_crud_router
from .execute import create_execute_router
from .git import create_git_router
from .run import create_run_router
from .security import (
    AccessLogMiddleware,
    ContentSecurityPolicyMiddleware,
    HostAllowlistMiddleware,
    make_token_dependency,
)
from .static import default_spa_dir, mount_static


def create_app(
    token: str,
    data_dir: Path | str | None = None,
    spa_dir: Path | str | None = None,
) -> FastAPI:
    """创建服务 app; token 为本次启动的随机凭证 (D004-4).

    data_dir 提供时挂资源 CRUD 路由 (M3 D010); 缺省仅骨架 (供安全中间件单测).
    spa_dir 缺省时从包路径推断仓库根 spa/ (dist 托管 + token 注入, D003/D004-4).
    """
    app = FastAPI()
    require_token = make_token_dependency(token)

    if data_dir is not None:
        store = Store(data_dir)
        app.include_router(create_crud_router(store, require_token))
        app.include_router(create_execute_router(store, require_token))
        app.include_router(create_run_router(store, require_token))
        app.include_router(create_git_router(store.data_dir, require_token))

    @app.get("/health", dependencies=[Depends(require_token)])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # 静态托管挂在所有 API 路由之后: Mount("/") 兜底, 显式路由优先匹配
    mount_static(app, token, Path(spa_dir) if spa_dir is not None else default_spa_dir())

    # add_middleware 后添加者在最外层: 访问日志记全量 (含 403), Host 白名单其次
    app.add_middleware(ContentSecurityPolicyMiddleware)
    app.add_middleware(HostAllowlistMiddleware)
    app.add_middleware(AccessLogMiddleware)
    return app
