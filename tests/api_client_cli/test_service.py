"""ISSUE-01 TS-002/TS-003: 服务 client + launch 接入 + service status/stop/token.

接缝: fake HTTP 服务 + 手写 service.json (pid 存活) + CLI subprocess (M3 D014-4).
"""

import json
import os
import signal
import subprocess
import sys
import time

from support import (
    CLI_TOKEN,
    FAKE_VERSION,
    FakeService,
    run_cli,
    stderr_error,
    stdout_json,
    write_service_json,
)


def test_status_sends_token_and_echoes_health(service_data_dir, fake_service):
    """connect 读 service.json 的 port/token, 请求带 X-Auth-Token, 响应回显 stdout (TC-003/TC-006)."""
    proc = run_cli(["service", "status"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    payload = stdout_json(proc)
    assert payload == {"status": "running", "pid": os.getpid(), "port": fake_service.port, "version": FAKE_VERSION}
    health_calls = fake_service.requests_to("/health")
    assert health_calls, "status 应经 GET /health 取 version"
    assert all(r["headers"].get("X-Auth-Token") == CLI_TOKEN for r in health_calls)


def test_client_retries_request_once(service_data_dir, fake_service):
    """首次请求 5xx, 重试一次后成功 (TC-004, D011-4 请求级重试一次)."""
    calls = {"n": 0}

    def flaky_health(handler):
        calls["n"] += 1
        if calls["n"] == 1:
            FakeService.respond(handler, 500, {"detail": "boom"})
        else:
            FakeService.respond(handler, 200, {"status": "ok", "version": FAKE_VERSION})

    fake_service.routes[("GET", "/health")] = flaky_health
    proc = run_cli(["service", "status"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc)["version"] == FAKE_VERSION
    assert calls["n"] == 2, "首次 5xx 后应恰重试一次"


def test_connect_ensure_running_reuses_existing(service_data_dir, fake_service):
    """业务命令先 ensure_running: 服务在则不动作, 不重复拉起 (TC-005)."""
    before = (service_data_dir / ".local" / "service.json").read_text()
    proc = run_cli(["send", "demo/get-json"], service_data_dir)  # 占位命令也走 connect
    assert proc.returncode != 2, proc.stderr  # 非用法错误: 已到服务交互阶段
    after = (service_data_dir / ".local" / "service.json").read_text()
    assert before == after, "service.json 不应被重写 (未重复拉起)"
    assert not (service_data_dir / ".local" / "service.log").exists(), "不应 spawn 新服务进程"
    assert fake_service.requests_to("/health"), "ensure_running ready 判定应打到 fake 服务"


def test_service_token_matches_service_json(service_data_dir):
    """service token 输出 {token} 与 service.json 一致 (TC-007, M3 D005)."""
    proc = run_cli(["service", "token"], service_data_dir)
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == {"token": CLI_TOKEN}


def test_service_token_without_service_exits_3(tmp_path):
    """无 service.json 时 service token -> SERVICE_ERROR exit 3."""
    proc = run_cli(["service", "token"], tmp_path / "repo")
    assert proc.returncode == 3
    assert stderr_error(proc)["code"] == "SERVICE_ERROR"


def test_service_status_stopped_when_no_service_json(tmp_path):
    """无 service.json -> {status: stopped, pid/port/version null}, exit 0."""
    proc = run_cli(["service", "status"], tmp_path / "repo")
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc) == {"status": "stopped", "pid": None, "port": None, "version": None}


def test_service_stop_terminates_process(tmp_path):
    """service stop --data-dir <dir> 委托 launch 停止: 输出 {status,pid} 且进程结束 (TC-008)."""
    data_dir = tmp_path / "repo"
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    try:
        write_service_json(data_dir, port=1, token="x", pid=sleeper.pid)
        proc = run_cli(["service", "stop", "--data-dir", str(data_dir)])  # 子命令位全局选项
        assert proc.returncode == 0, proc.stderr
        assert stdout_json(proc) == {"status": "stopped", "pid": sleeper.pid}
        assert sleeper.wait(timeout=10) is not None, "被停进程应已退出"
    finally:
        if sleeper.poll() is None:
            sleeper.kill()


def test_service_stop_without_service_exits_3(tmp_path):
    """无 service.json 时 service stop -> SERVICE_ERROR exit 3."""
    proc = run_cli(["service", "stop"], tmp_path / "repo")
    assert proc.returncode == 3
    assert stderr_error(proc)["code"] == "SERVICE_ERROR"
