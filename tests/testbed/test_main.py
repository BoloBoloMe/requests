"""ISSUE-08: 启动入口冒烟测试."""

import os
import re
import signal
import subprocess
import time

import httpx


def test_cli_startup_smoke():
    """`uv run python -m testbed --port 0` 启动后应可访问 /echo."""
    cmd = ["uv", "run", "python", "-m", "testbed", "--port", "0"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    url = None
    stdout_lines: list[str] = []
    deadline = time.time() + 15
    try:
        while time.time() < deadline and proc.poll() is None:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            stdout_lines.append(line)
            match = re.search(r"listening on (http://\S+)", line)
            if match:
                url = match.group(1)
                break

        assert url is not None, (
            "启动后未打印 listening 行\n"
            f"stdout: {''.join(stdout_lines)}\n"
            f"returncode: {proc.poll()}"
        )

        response = httpx.get(f"{url}/echo", timeout=5, trust_env=False)
        response.raise_for_status()
        data = response.json()
        assert data["method"] == "GET"
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
