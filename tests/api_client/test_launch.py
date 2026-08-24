"""ISSUE-01 TS-001/TS-002/TS-005: launch 幂等拉起矩阵 (D011, D014-5).

接缝: api_client.launch.ensure_running(data_dir) -> ServiceInfo(port, token).
"""

import base64
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from api_client.launch import LaunchError, ensure_running, pid_alive


def _kill_service(data_dir: Path) -> None:
    """测试清理: 按 service.json 的 pid 终止服务进程."""
    service_json = data_dir / ".local" / "service.json"
    if not service_json.exists():
        return
    pid = json.loads(service_json.read_text())["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.05)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    yield d
    _kill_service(d)


def _ensure_running_in_subprocess(data_dir: Path) -> subprocess.CompletedProcess:
    code = (
        "import json, sys\n"
        "from api_client.launch import ensure_running\n"
        "info = ensure_running(sys.argv[1])\n"
        "print(json.dumps({'port': info.port, 'token': info.token}))\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code, str(data_dir)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_service_json_token_entropy(data_dir):
    """service.json 的 token 满足 >=128 bit (TC-010, D004-4/D011-1)."""
    info = ensure_running(data_dir)
    written = json.loads((data_dir / ".local" / "service.json").read_text())
    assert written["token"] == info.token
    raw = base64.urlsafe_b64decode(info.token + "=" * (-len(info.token) % 4))
    assert len(raw) * 8 >= 128


def test_stale_service_json_restarts(data_dir):
    """service.json 指向死 pid 时重新拉起而不是复用 (TC-002, D011-4)."""
    dead = subprocess.run([sys.executable, "-c", "pass"])
    dead_pid_holder = subprocess.Popen([sys.executable, "-c", "pass"])
    dead_pid_holder.wait()
    local = data_dir / ".local"
    local.mkdir()
    (local / "service.json").write_text(
        json.dumps({"port": 1, "token": "stale", "pid": dead_pid_holder.pid})
    )

    info = ensure_running(data_dir)

    assert info.port != 1
    assert info.token != "stale"
    written = json.loads((local / "service.json").read_text())
    assert written["port"] == info.port
    os.kill(written["pid"], 0)  # 新 pid 存活


def test_launch_failure_raises_with_reason(data_dir):
    """拉起连续失败 3 次后明确报错且含原因 (TC-003, D011-5).

    失败注入: .local/service.log 占为目录 => 子进程日志文件打不开, 每次拉起即败.
    """
    local = data_dir / ".local"
    local.mkdir()
    (local / "service.log").mkdir()

    with pytest.raises(LaunchError, match="service.log"):
        ensure_running(data_dir)


def test_concurrent_ensure_running_yields_single_service(data_dir):
    """两进程同时 ensure_running, 最终恰好一个活服务且两次返回一致 (TC-001)."""
    code = (
        "import json, sys\n"
        "from api_client.launch import ensure_running\n"
        "info = ensure_running(sys.argv[1])\n"
        "print(json.dumps({'port': info.port, 'token': info.token}))\n"
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(data_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [p.communicate(timeout=60) for p in procs]

    outputs = []
    for proc, (out, err) in zip(procs, results):
        assert proc.returncode == 0, f"子进程失败: {err}"
        outputs.append(json.loads(out))

    # 两次返回 (port, token) 一致 => 只有一个活服务
    assert outputs[0] == outputs[1]

    # service.json 完整可读且与返回值一致, pid 存活
    info = json.loads((data_dir / ".local" / "service.json").read_text())
    assert info["port"] == outputs[0]["port"]
    assert info["token"] == outputs[0]["token"]
    os.kill(info["pid"], 0)  # 不抛异常即存活
