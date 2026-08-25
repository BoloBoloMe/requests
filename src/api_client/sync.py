"""Sync: 数据仓库 git 绑定/提交/推拉封装 (M3 D008/D009, M2 D004-D007/D011).

只碰数据仓库文件路径, 不进核心库依赖链 (M3 D008).
冲突策略 = 冲突即停 (M3 D009): add -A / commit / pull --rebase / push,
遇冲突/dirty 异常即停, git 原样输出抛给用户手工处理, 绝不自动合并.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# 绑定仓库时自动写入的 .gitignore 规则 (M2 D006/D007/D011: secrets/.local/历史永不进 git)
GITIGNORE_RULES = (".local/", "*.secrets.yaml")

# 隔离全局/系统 git 配置, 保证行为可重现 (用户全局 pull.rebase 等不渗入);
# LC_ALL=C: git 输出语言稳定 (供 AI/日志消费, 原样透传语义不变)
_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "LC_ALL": "C",
}
# 提交身份由工具代写, 不依赖用户 git config
_IDENTITY = ("-c", "user.name=apic", "-c", "user.email=apic@localhost")


class SyncError(Exception):
    """git 绑定/同步失败: message 原样携带 git 输出 (M3 D009, 不清洗不摘要)."""


def _git(data_dir: Path, *args: str) -> str:
    """跑一条 git 命令; 非零退出即 SyncError, stdout+stderr 原样透传 (D009).

    stdin=DEVNULL: 隔离输入通道, credential/SSH host-key 等交互提示
    立即失败而非悬挂服务 (本模块所有 git 子进程统一隔离).
    """
    proc = subprocess.run(
        ["git", *_IDENTITY, *args],
        cwd=data_dir,
        env=_GIT_ENV,
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise SyncError(
            f"git {' '.join(args)} 失败 (退出码 {proc.returncode}):\n"
            f"{proc.stdout}{proc.stderr}"
        )
    return proc.stdout + proc.stderr


def _has_head(data_dir: Path) -> bool:
    """仓库是否已有任一提交."""
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=data_dir,
            env=_GIT_ENV,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def _ensure_gitignore(data_dir: Path) -> None:
    """追加缺失的 .gitignore 规则, 不覆盖用户已有内容 (M2 D006)."""
    path = data_dir / ".gitignore"
    text = path.read_text() if path.exists() else ""
    lines = text.splitlines()
    missing = [rule for rule in GITIGNORE_RULES if rule not in lines]
    if not missing:
        return
    with path.open("a") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        for rule in missing:
            fh.write(rule + "\n")


def bind(data_dir: Path | str, remote_url: str) -> None:
    """绑定数据仓库到远端: git init + 自动 .gitignore + 初始 commit + remote add origin.

    幂等: 已 init 且 origin 一致时只补缺失的 .gitignore 规则与初始 commit (若缺);
    origin 指向不同远端则明确报错, 不擅自改绑.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    if not (data_dir / ".git").is_dir():
        _git(data_dir, "init", "-b", "main")
    _ensure_gitignore(data_dir)

    if "origin" not in _git(data_dir, "remote").split():
        _git(data_dir, "remote", "add", "origin", remote_url)
    else:
        existing = _git(data_dir, "remote", "get-url", "origin").strip()
        if existing != remote_url:
            raise SyncError(f"数据仓库已绑定远端 {existing}, 与 {remote_url} 不一致")

    # 初始 commit: 仓库无提交时才建 (--allow-empty 覆盖全空仓库)
    if not _has_head(data_dir):
        _git(data_dir, "add", "-A")
        _git(data_dir, "commit", "--allow-empty", "-m", "init: 绑定数据仓库")


def sync(data_dir: Path | str) -> None:
    """同步: add -A / commit / pull --rebase / push (M3 D009 顺序).

    远端尚无本地分支时跳过 pull (首次推送); 任何 git 非零退出即停并原样透传.
    """
    data_dir = Path(data_dir)
    if not (data_dir / ".git").is_dir() or "origin" not in _git(
        data_dir, "remote"
    ).split():
        raise SyncError("数据仓库未绑定远端: 先执行 bind (POST /git/bind)")

    # dirty 异常即停 (M3 D009): 上次冲突留下的未合并路径或 rebase/merge 中途态,
    # 不接管不清扫 (add -A 会把冲突标记扫进提交), git status 原样输出抛给用户
    status = _git(data_dir, "status", "--porcelain")
    unmerged = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    conflicted = any(line[:2] in unmerged for line in status.splitlines())
    git_dir = data_dir / ".git"
    in_progress = any(
        (git_dir / marker).exists()
        for marker in ("REBASE_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD")
    )
    if conflicted or in_progress:
        raise SyncError(
            "数据仓库存在未解决的冲突或 rebase/merge 中途态, 先手工处理:\n"
            + _git(data_dir, "status")
        )

    _git(data_dir, "add", "-A")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=data_dir,
        env=_GIT_ENV,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if staged.returncode != 0:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _git(data_dir, "commit", "-m", f"sync: {stamp}")

    branch = _git(data_dir, "symbolic-ref", "--short", "HEAD").strip()
    # 注: ls-remote 失败 (网络/鉴权) 与远端无分支在此不作区分 (已裁决 defer):
    # 统一按"远端无分支"处理跳过 pull; 真实远端网络失败随后由 push 拒绝暴露, 不静默.
    remote_has_branch = (
        subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin", branch],
            cwd=data_dir,
            env=_GIT_ENV,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    if remote_has_branch:
        _git(data_dir, "pull", "--rebase", "origin", branch)
    _git(data_dir, "push", "-u", "origin", branch)
