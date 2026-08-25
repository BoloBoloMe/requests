"""tests/api_client 共享 fixture: testbed 子进程 (M3 D014-2 真 HTTP, 不 mock httpx)."""

import os
import re
import select
import signal
import subprocess
import time

import pytest


@pytest.fixture(scope="session")
def testbed_url():
    """拉起 `uv run testbed --port 0` (内核分配端口), 解析 listening 行得基地址."""
    proc = subprocess.Popen(
        ["uv", "run", "testbed", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,  # 独立进程组: pgid == proc.pid, 清理按组杀
    )
    url = None
    lines: list[str] = []
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline and proc.poll() is None:
            # select 轮询代替裸 readline: 无输出时每秒醒一次复查 deadline/进程存活,
            # 不会永久阻塞 (总 deadline 30s 不变)
            ready, _, _ = select.select([proc.stdout], [], [], 1.0)
            if not ready:
                continue
            line = proc.stdout.readline()
            if not line:
                break  # EOF: 进程已关管道, 交给 poll/deadline 判定
            lines.append(line)
            match = re.search(r"listening on (http://\S+)", line)
            if match:
                url = match.group(1)
                break
        if url is None:
            raise RuntimeError("testbed 未就绪:\n" + "".join(lines))
        yield url
    finally:
        # 进程组清理 (防泄漏): proc.terminate() 只杀 uv 包装进程, testbed 孙进程
        # 会变孤儿长期存活; 按组递进 SIGTERM -> SIGKILL, 整组灭口
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # 整组已退
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
