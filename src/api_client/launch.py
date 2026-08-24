"""launch 模块 (M3 D002): CLI 与服务共享的拉起/服务发现逻辑, 不含业务逻辑.

服务发现单一权威源: <data-dir>/.local/service.json {port, token, pid} (D011-1).
拉起串行化: flock + 锁内二次检查 (D011-3); ready 判定 = TCP 连通 + token 校验 (D011-5).
仅 POSIX (D012).
"""

import fcntl
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from http.client import HTTPConnection
from pathlib import Path

LOCAL_DIR = ".local"
LOCK_FILE = "launch.lock"
SERVICE_JSON = "service.json"
SERVICE_LOG = "service.log"
MAX_ATTEMPTS = 3
READY_TIMEOUT = 10.0


class LaunchError(RuntimeError):
    """拉起服务失败; 消息含原因 (D011-5)."""


@dataclass(frozen=True)
class ServiceInfo:
    port: int
    token: str


def atomic_write_json(path: Path, payload: dict) -> None:
    """tmp+rename 原子写 (D011-1); __main__ 与服务端共享."""
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload))
    os.replace(tmp, path)


def pid_alive(pid: int) -> bool:
    """进程存活判定 (kill(0) + /proc zombie 排除); __main__ 与测试共享."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # zombie (已退出未被父进程 reap) 对 kill(pid,0) 仍应答, 经 /proc 判定;
    # 无 /proc 的平台 (macOS) 退化为仅 kill(0)
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        if stat.rpartition(")")[2].split()[0] == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


def _read_service_info(local_dir: Path) -> tuple[int, int, str] | None:
    """读 service.json 并校验 schema; 缺键/坏 JSON 视为无效."""
    path = local_dir / SERVICE_JSON
    try:
        data = json.loads(path.read_text())
        port, token, pid = data["port"], data["token"], data["pid"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(port, int) or not isinstance(token, str) or not isinstance(pid, int):
        return None
    return port, pid, token


def _check_ready(port: int, token: str) -> bool:
    """ready 判定: TCP 连通 + token 校验通过 (D011-5)."""
    # 已知限制: ready 检查硬编码 127.0.0.1, 因服务发现不记录监听地址;
    # --host 仅接受回环变体, 默认 127.0.0.1 为常态路径, 此分支覆盖;
    # ::1 手动起服 + ensure_running 属已知限制 (已裁决接受), 此时 ensure_running 会另起 127.0.0.1 服务.
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/health", headers={"X-Auth-Token": token})
            resp = conn.getresponse()
            resp.read()
            return resp.status == 200
        finally:
            conn.close()
    except OSError:
        return False


def _try_existing(local_dir: Path) -> ServiceInfo | None:
    """锁内二次检查: service.json 有效 + pid 存活 (stale 防护) + ready."""
    parsed = _read_service_info(local_dir)
    if parsed is None:
        return None
    port, pid, token = parsed
    if not pid_alive(pid):
        return None
    if not _check_ready(port, token):
        return None
    return ServiceInfo(port=port, token=token)


def _spawn_service(data_dir: Path, local_dir: Path) -> subprocess.Popen:
    """detach 拉起服务子进程, stdout/stderr 落 .local/service.log (D011-5).

    日志文件打开失败 (如路径被占用) 抛 OSError, 作为拉起失败原因.
    """
    log_file = open(local_dir / SERVICE_LOG, "ab")
    try:
        return subprocess.Popen(
            [sys.executable, "-m", "api_client", "serve", "--data-dir", str(data_dir)],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_file.close()


def _wait_ready(local_dir: Path, proc: subprocess.Popen) -> tuple[ServiceInfo | None, str]:
    """等待子进程写好 service.json 且 ready; 返回 (info, 失败原因)."""
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        returncode = proc.poll()
        if returncode is not None:
            return None, f"服务子进程退出 (exit code {returncode}), 详见 .local/{SERVICE_LOG}"
        parsed = _read_service_info(local_dir)
        if parsed is not None:
            port, pid, token = parsed
            if pid == proc.pid and pid_alive(pid) and _check_ready(port, token):
                return ServiceInfo(port=port, token=token), ""
        time.sleep(0.05)
    return None, f"服务未在 {READY_TIMEOUT:.0f}s 内就绪"


def ensure_running(data_dir: str | Path) -> ServiceInfo:
    """幂等拉起: 服务在则复用, 不在则拉起; 并发安全 (flock 串行化)."""
    data_dir = Path(data_dir)
    local_dir = data_dir / LOCAL_DIR
    local_dir.mkdir(parents=True, exist_ok=True)

    with open(local_dir / LOCK_FILE, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        info = _try_existing(local_dir)
        if info is not None:
            return info

        last_reason = "未知原因"
        for _ in range(MAX_ATTEMPTS):
            try:
                proc = _spawn_service(data_dir, local_dir)
            except OSError as exc:
                last_reason = f"拉起子进程失败: {exc}"
                continue
            info, last_reason = _wait_ready(local_dir, proc)
            if info is not None:
                return info
            if proc.poll() is None:
                proc.terminate()  # 就绪超时, 回收残留子进程防泄漏
        raise LaunchError(f"拉起服务失败 ({MAX_ATTEMPTS} 次尝试): {last_reason}")
