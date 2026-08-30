"""ISSUE-07: dist 托管 + token 内存注入 + 时间戳漂移警告 (M3 D003/D004-4/D004-6, ADR 0005).

TestClient 一律显式 Host: localhost (Host 白名单, 同 test_security 惯例).
GET / 不需 token: token 正是经托管页注入送达 SPA 的 (D004-4).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_client.web.app import create_app
from api_client.web.static import check_dist_staleness

TOKEN = "test-token-dist"
HOST = {"Host": "localhost"}
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(TOKEN))


# --- TS-001: 托管 + 内存注入 (D004-4) ---


def test_index_injects_current_token_no_placeholder(client):
    """TC-001: 首页 HTML 固定属性名注入当前 token 值, 值占位符不残留.

    TOKEN 含 `-`: 属性名若参与替换会产生非法 JS (审核返工, ISSUE-07).
    """
    r = client.get("/", headers=HOST)
    assert r.status_code == 200
    assert f'window.__APIC_TOKEN__ = "{TOKEN}";' in r.text
    assert "__APIC_TOKEN_VALUE__" not in r.text


def test_index_cache_control_no_store(client):
    """TC-002: index.html 响应 Cache-Control: no-store (防旧 token 页面缓存后 401, D004-4)."""
    r = client.get("/", headers=HOST)
    assert r.headers["cache-control"] == "no-store"


def test_index_carries_csp_script_src_self(client):
    """TC-003: 首页携带 CSP script-src 'self' (ISSUE-01 中间件注入, D004-6)."""
    r = client.get("/", headers=HOST)
    assert r.headers["content-security-policy"] == "script-src 'self'"


def test_index_injection_uses_current_token_per_app():
    """TC-004: 换 token 的 app 实例 GET / 注入新 token (证明内存替换非写盘)."""
    other_token = "another-token-instance"
    other = TestClient(create_app(other_token))
    r = other.get("/", headers=HOST)
    assert other_token in r.text
    assert TOKEN not in r.text


def test_index_html_direct_access_injects_token(client):
    """TC-009: GET /index.html 直接访问同 / 语义: 注入 token + no-store."""
    r = client.get("/index.html", headers=HOST)
    assert r.status_code == 200
    assert f'window.__APIC_TOKEN__ = "{TOKEN}";' in r.text
    assert "__APIC_TOKEN_VALUE__" not in r.text
    assert r.headers["cache-control"] == "no-store"


# --- TS-002: 时间戳漂移警告 (D003/F005) ---


def _make_tree(spa: Path, src_ts: float, dist_ts: float) -> tuple[Path, Path]:
    """造 spa/src 与 spa/dist 各一文件, 用 os.utime 显式钉死 mtime (测试确定性)."""
    import os

    src_dir, dist_dir = spa / "src", spa / "dist"
    src_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True)
    src_file, dist_file = src_dir / "placeholder.txt", dist_dir / "index.html"
    src_file.write_text("src")
    dist_file.write_text("dist")
    os.utime(src_file, (src_ts, src_ts))
    os.utime(dist_file, (dist_ts, dist_ts))
    return src_dir, dist_dir


def test_stale_dist_warns(tmp_path, caplog):
    """TC-005: dist 最新 mtime 旧于 src → 返回 True 且启动日志含警告 (含两侧路径)."""
    import logging

    spa = tmp_path / "spa"
    src_dir, dist_dir = _make_tree(spa, src_ts=2_000_000_000, dist_ts=1_000_000_000)

    assert check_dist_staleness(src_dir, dist_dir) is True

    with caplog.at_level(logging.WARNING, logger="api_client.static"):
        create_app(TOKEN, spa_dir=spa)
    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert str(src_dir) in messages
    assert str(dist_dir) in messages


def test_fresh_dist_no_warning(tmp_path, caplog):
    """TC-006: dist 新于 src → 返回 False 且启动无警告."""
    import logging

    spa = tmp_path / "spa"
    src_dir, dist_dir = _make_tree(spa, src_ts=1_000_000_000, dist_ts=2_000_000_000)

    assert check_dist_staleness(src_dir, dist_dir) is False

    with caplog.at_level(logging.WARNING, logger="api_client.static"):
        create_app(TOKEN, spa_dir=spa)
    assert "产物漂移" not in "\n".join(r.getMessage() for r in caplog.records)


def test_equal_mtime_no_warning(tmp_path, caplog):
    """TC-010: src_mtime == dist_mtime (同刻构建) → 返回 False 且无警告."""
    import logging

    spa = tmp_path / "spa"
    src_dir, dist_dir = _make_tree(spa, src_ts=1_500_000_000, dist_ts=1_500_000_000)

    assert check_dist_staleness(src_dir, dist_dir) is False

    with caplog.at_level(logging.WARNING, logger="api_client.static"):
        create_app(TOKEN, spa_dir=spa)
    assert "产物漂移" not in "\n".join(r.getMessage() for r in caplog.records)


def test_subsecond_checkout_jitter_no_warning(tmp_path):
    """TC-011: git checkout 顺序抖动 (src 比 dist 新几毫秒) → False, 不误报.

    克隆/切分支后 dist 文件先于 src 落盘 (索引序), 差值仅毫秒级, 不足容差.
    """
    spa = tmp_path / "spa"
    src_dir, dist_dir = _make_tree(spa, src_ts=1_500_000_000.004, dist_ts=1_500_000_000.0)

    assert check_dist_staleness(src_dir, dist_dir) is False


def test_stale_beyond_tolerance_warns(tmp_path):
    """TC-012: src 超前 dist 超过容差 (1s) → True, 真实漂移仍报警."""
    spa = tmp_path / "spa"
    src_dir, dist_dir = _make_tree(spa, src_ts=1_000_000_002.0, dist_ts=1_000_000_000.0)

    assert check_dist_staleness(src_dir, dist_dir) is True


def test_missing_src_dir_skips_check(tmp_path, caplog):
    """TC-007: spa/src 不存在 → 跳过不警告."""
    import logging

    spa = tmp_path / "spa"
    dist_dir = spa / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("dist")

    assert check_dist_staleness(spa / "src", dist_dir) is False

    with caplog.at_level(logging.WARNING, logger="api_client.static"):
        create_app(TOKEN, spa_dir=spa)
    assert "产物漂移" not in "\n".join(r.getMessage() for r in caplog.records)


# --- TS-003: 占位产物 tracked (M3 D003, ADR 0005) ---


def test_dist_placeholder_is_tracked():
    """TC-008: spa/dist/index.html 与 spa/src/ 占位文件存在于仓库且被 git tracked."""
    import subprocess

    out = subprocess.run(
        ["git", "ls-files", "spa/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert "spa/dist/index.html" in out
    assert "spa/src/placeholder.txt" in out
    assert (REPO_ROOT / "spa" / "dist" / "index.html").is_file()
    assert (REPO_ROOT / "spa" / "src" / "placeholder.txt").is_file()
