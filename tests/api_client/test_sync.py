"""ISSUE-06: Sync git 同步 (M2 D004-D007/D011, M3 D008/D009/D010).

真实 git (临时目录数据仓库 + 本地 bare remote), 非 mock (EXECUTION 测试策略 6);
POSIX + git 可用为前提. 测试内 git 命令同样隔离全局/系统配置, 保证可重现.
"""

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_client.sync import SyncError, bind, sync
from api_client.web.app import create_app

# 隔离用户全局/系统 git 配置 (pull.rebase/init.defaultBranch 等不渗入)
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
}
# 测试手工提交用的身份 (不依赖用户 git config)
GIT_IDENTITY = ("-c", "user.name=test", "-c", "user.email=test@localhost")


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """测试内 git 助手: 非零退出即失败 (夹具构造期不预期失败)."""
    return subprocess.run(
        ["git", *GIT_IDENTITY, *args],
        cwd=cwd,
        env=GIT_ENV,
        text=True,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def repo(tmp_path) -> Path:
    """未绑定的数据仓库目录 (布局按 M2 D004 最小化手工构造)."""
    d = tmp_path / "repo"
    (d / "environments").mkdir(parents=True)
    return d


@pytest.fixture
def remote(tmp_path) -> Path:
    """本地 bare remote (真远端, 离线可验)."""
    r = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(r))
    return r


# --- TS-001 TC-001/TC-002: bind 写 .gitignore + 初始 commit + 环境 tracked/secrets 忽略 ---


def test_bind_writes_gitignore_and_tracks_env(repo, remote):
    (repo / "environments" / "dev.yaml").write_text("version: 1\nvars: {}\n")
    (repo / "environments" / "dev.secrets.yaml").write_text(
        "version: 1\nvars:\n  token: s3cret\n"
    )
    (repo / ".local").mkdir()
    (repo / ".local" / "state.yaml").write_text("active: dev\n")

    bind(repo, str(remote))

    # TC-001: 数据仓库是 git 仓库, .gitignore 含规则, 初始 commit 存在
    assert (repo / ".git").is_dir()
    gitignore = (repo / ".gitignore").read_text()
    assert ".local/" in gitignore
    assert "*.secrets.yaml" in gitignore
    git(repo, "rev-parse", "--verify", "HEAD")

    # TC-002: 环境文件 tracked (M2 D005); secrets 与 .local 永不进 git (M2 D006/D007/D011)
    tracked = git(repo, "ls-files").stdout
    assert "environments/dev.yaml" in tracked
    assert "dev.secrets.yaml" not in tracked
    assert ".local/" not in tracked
    status = git(repo, "status", "--porcelain").stdout
    assert status == ""


# --- TS-001 TC-003: 修改条目 + 同步 → bare remote 出现对应提交 ---


def test_sync_pushes_commit_to_remote(repo, remote):
    bind(repo, str(remote))
    item = repo / "collections" / "demo" / "ping.yaml"
    item.parent.mkdir(parents=True)
    item.write_text("version: 1\nname: ping\n")

    sync(repo)

    # bare remote 出现对应提交, 且条目文件已 tracked 进远端树
    log = git(remote, "log", "main", "--format=%s").stdout.splitlines()
    assert any(msg.startswith("sync") for msg in log)
    tree = git(remote, "ls-tree", "-r", "main", "--name-only").stdout
    assert "collections/demo/ping.yaml" in tree
    # 同步后工作区干净
    assert git(repo, "status", "--porcelain").stdout == ""


# --- TS-001 TC-004: 未绑定调用 sync → 明确错误 ---


def test_sync_unbound_errors(repo):
    with pytest.raises(SyncError, match="未绑定"):
        sync(repo)

    # 已 init 但未绑 remote 同样明确报错
    git(repo, "init", "-b", "main")
    with pytest.raises(SyncError, match="未绑定"):
        sync(repo)


# --- TS-002 TC-005/TC-006: 冲突即停 (M3 D009) ---


@pytest.fixture
def diverged(repo, remote, tmp_path) -> Path:
    """构造分叉场景: 远端与本地对同一条目文件分别修改, 下次 sync 必冲突."""
    item = repo / "collections" / "demo" / "ping.yaml"
    item.parent.mkdir(parents=True)
    item.write_text("version: 1\nname: base\n")
    bind(repo, str(remote))
    sync(repo)  # base 推上远端

    # 另一工作副本改同一文件并推远端
    other = tmp_path / "other"
    git(tmp_path, "clone", str(remote), str(other))
    (other / "collections" / "demo" / "ping.yaml").write_text(
        "version: 1\nname: remote\n"
    )
    git(other, "add", "-A")
    git(other, "commit", "-m", "remote change")
    git(other, "push", "origin", "main")

    # 本地改同一文件 (尚未同步)
    item.write_text("version: 1\nname: local\n")
    return repo


def test_sync_conflict_stops_with_git_output(diverged):
    with pytest.raises(SyncError) as excinfo:
        sync(diverged)
    out = str(excinfo.value)
    # git 原样输出: 含冲突文件与冲突信息, 不清洗不摘要
    assert "ping.yaml" in out
    assert "CONFLICT" in out or "could not apply" in out
    # 绝不自动合并: 未解决冲突仍在工作区
    status = git(diverged, "status", "--porcelain").stdout
    assert any(line.startswith("UU") for line in status.splitlines())


def test_sync_dirty_state_stops(diverged):
    # 上次 sync 冲突留下的 rebase 中途态/未合并路径: 再同步必须即停,
    # 不得 add -A 把冲突标记扫进提交
    with pytest.raises(SyncError):
        sync(diverged)
    with pytest.raises(SyncError) as excinfo:
        sync(diverged)
    out = str(excinfo.value)
    assert "ping.yaml" in out  # git status 原样输出含冲突文件
    # 状态未被接管: 冲突仍在
    status = git(diverged, "status", "--porcelain").stdout
    assert any(line.startswith("UU") for line in status.splitlines())


# --- TS-003 TC-007/TC-008: RPC 壳薄测 (M3 D010, D014-3) ---

TOKEN = "test-token"
HOST = {"Host": "localhost"}
AUTH = {"X-Auth-Token": TOKEN}


@pytest.fixture
def client(tmp_path) -> TestClient:
    return TestClient(create_app(TOKEN, data_dir=tmp_path / "repo"))


def test_git_sync_unbound_errors(client):
    # 未绑定 → 明确错误 (409 + 中文指引), 不得 500 穿透
    r = client.post("/git/sync", headers={**HOST, **AUTH})
    assert r.status_code == 409
    assert "未绑定" in r.json()["detail"]


def test_git_bind_and_sync_rpc(client, remote):
    # 合法 remote → 200, 数据仓库完成绑定
    r = client.post(
        "/git/bind", json={"remote_url": str(remote)}, headers={**HOST, **AUTH}
    )
    assert r.status_code == 200

    # 非法 URL (空/纯空白) → 明确错误, 不得 500
    r = client.post("/git/bind", json={"remote_url": "  "}, headers={**HOST, **AUTH})
    assert r.status_code == 400
    assert "remote_url" in r.json()["detail"]

    # 绑定后 sync → 200, 初始 commit 已推上 bare remote
    r = client.post("/git/sync", headers={**HOST, **AUTH})
    assert r.status_code == 200
    log = git(remote, "log", "main", "--format=%s").stdout
    assert "init" in log


def test_git_routes_require_token(client):
    # TC-008: 无 token → 401
    r = client.post("/git/bind", json={"remote_url": "/tmp/x"}, headers=HOST)
    assert r.status_code == 401
    r = client.post("/git/sync", headers=HOST)
    assert r.status_code == 401
