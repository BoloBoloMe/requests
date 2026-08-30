"""SPA dist 静态托管 + token 内存注入 + 产物漂移时间戳警告 (M3 D003/D004-4, ADR 0005).

token 注入是运行时动作: 每次请求读盘并在内存内替换占位符 serve, 从不写盘;
index.html 响应 Cache-Control: no-store, 防浏览器缓存旧 token 页面后 401 (D004-4).
CSP script-src 'self' 由 ISSUE-01 中间件对 text/html 响应注入 (D004-6), 此处不重复.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("api_client.static")

# 占位符约定: JS 属性名 __APIC_TOKEN__ 固定, 只有值占位符参与替换 (审核返工: 防属性名被全局替换成含 - 的非法 JS)
TOKEN_PLACEHOLDER = "__APIC_TOKEN_VALUE__"


def default_spa_dir() -> Path:
    """从包路径推断仓库根下的 spa/ 目录 (src/api_client/web/static.py -> 上溯 3 级即仓库根)."""
    return Path(__file__).resolve().parents[3] / "spa"


def _latest_mtime(directory: Path) -> float | None:
    """目录内全部文件 (递归) 的最新 mtime; 目录不存在或无文件返回 None."""
    if not directory.is_dir():
        return None
    mtimes = [p.stat().st_mtime for p in directory.rglob("*") if p.is_file()]
    return max(mtimes, default=None)


# 容差: git checkout/clone 按索引序写文件, dist 字母序在 src 前, 克隆后 src 天然新几毫秒;
# 真实漂移 (改源码未构建) 的间隔远大于 1s, 故小于该差值视为同刻.
STALENESS_TOLERANCE_SECONDS = 1.0


def check_dist_staleness(src_dir: Path, dist_dir: Path) -> bool:
    """dist 最新 mtime 旧于 src 最新 mtime 超过容差则 True (产物漂移, F005).

    口径: 两侧各自取全部文件的最新 mtime 比较, src 超前不足 STALENESS_TOLERANCE_SECONDS
    视为同刻 (git checkout 顺序抖动, 防克隆后误报); src 目录不存在/无文件则跳过 (False).
    """
    src_mtime = _latest_mtime(src_dir)
    if src_mtime is None:
        return False
    dist_mtime = _latest_mtime(dist_dir)
    if dist_mtime is None:
        return False
    return src_mtime - dist_mtime > STALENESS_TOLERANCE_SECONDS


def mount_static(app: FastAPI, token: str, spa_dir: Path) -> bool:
    """托管 spa/dist 并做启动时漂移检查; spa/dist/index.html 缺失则跳过托管 (优雅降级).

    返回是否挂载成功.
    """
    src_dir, dist_dir = spa_dir / "src", spa_dir / "dist"
    if check_dist_staleness(src_dir, dist_dir):
        logger.warning(
            "SPA 产物漂移: dist (%s) 旧于源码 (%s), 请重新构建前端 (M3 D003/F005)",
            dist_dir,
            src_dir,
        )

    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        logger.warning("SPA dist 不存在 (%s), 跳过静态托管", dist_dir)
        return False

    # / 与 /index.html 同语义: 均返回注入后页面 + no-store (直接访问 index.html 也需注入)
    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    async def index() -> HTMLResponse:
        # 内存内占位符替换 serve (D004-4): token 只存在于内存, 不落任何磁盘文件
        html = index_path.read_text(encoding="utf-8").replace(TOKEN_PLACEHOLDER, token)
        # no-store: 防旧 token 页面被缓存后 401 (D004-4, ADR 0005)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    dist_root = dist_dir.resolve()

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException) -> JSONResponse | FileResponse:
        """404 回退托管 dist 静态资源 (不用 Mount("/"): 按序匹配会遮蔽后注册的路由)."""
        if exc.status_code == 404 and request.method == "GET":
            target = (dist_root / request.url.path.lstrip("/")).resolve()
            # 防路径穿越: 目标必须仍在 dist 目录内
            if target.is_file() and dist_root in target.parents:
                return FileResponse(target)
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    return True
