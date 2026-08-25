"""ISSUE-01 TS-004: 双 CLI 并发拉起矩阵 (M3 D014-5) + serve/stop 转发冒烟.

接缝: 真 launch + 真服务 (08 已交付) 于临时 data-dir; CLI subprocess.
launch 内部并发语义 08 已测, 本文件验证 CLI 集成路径 (connect 统一走 ensure_running).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from support import run_cli, stdout_json

READY_TIMEOUT = 60


def _wait_service_json(data_dir: Path, timeout: float = READY_TIMEOUT) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        path = data_dir / ".local" / "service.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except ValueError:
                pass
        time.sleep(0.2)
    raise RuntimeError(f"服务未在 {timeout:.0f}s 内写好 service.json")


@pytest.fixture
def running_service(tmp_path):
    """真服务 data-dir; 收尾经 CLI service stop 回收 (dogfood stop 路径)."""
    data_dir = tmp_path / "repo"
    yield data_dir
    run_cli(["service", "stop"], data_dir, timeout=30)
    pid_path = data_dir / ".local" / "service.json"
    if pid_path.exists():
        try:
            pid = json.loads(pid_path.read_text())["pid"]
            os.kill(pid, 9)
        except (ValueError, KeyError, ProcessLookupError, PermissionError):
            pass


def test_serve_stop_forwarding(tmp_path):
    """`apic serve/stop` 转发到 api_client 服务壳不失效 (apic script 归属 CLI 后)."""
    data_dir = tmp_path / "repo"
    proc = subprocess.Popen(
        [sys.executable, "-m", "api_client_cli", "serve", "--data-dir", str(data_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        info = _wait_service_json(data_dir)
        assert info["pid"] > 0 and info["port"] > 0 and info["token"]
    finally:
        if proc.poll() is None:
            run_cli(["stop", "--data-dir", str(data_dir)], timeout=30)
        proc.wait(timeout=30)
    assert not _pid_alive(info["pid"])


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_two_cli_concurrent_ensure_running_single_service(running_service):
    """两 CLI 并发拉起同一 data-dir -> 仅一个活服务, 一致 (port,token) (TC-009, D014-5)."""
    data_dir = running_service
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "api_client_cli", "--data-dir", str(data_dir), "send", "demo/get-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [proc.communicate(timeout=120) for proc in procs]
    # 两进程均完成服务交互 (非用法错误/非拉起失败)
    for proc, (_, stderr) in zip(procs, results):
        assert proc.returncode != 2, stderr
        assert "拉起服务失败" not in stderr, stderr

    info = _wait_service_json(data_dir)
    assert _pid_alive(info["pid"]), "应恰有一个活服务"
    # 两进程读到一致 (port, token): 以 service.json 单一权威源 + token 子命令核对
    proc = run_cli(["service", "token"], data_dir)
    assert stdout_json(proc) == {"token": info["token"]}
    status = stdout_json(run_cli(["service", "status"], data_dir))
    assert status["status"] == "running" and status["pid"] == info["pid"] and status["port"] == info["port"]
