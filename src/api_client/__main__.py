"""api-client 服务入口: `apic` (默认 serve) / `apic serve` / `apic stop`.

参照 src/testbed/__main__.py 的 getaddrinfo/bind(0) 样板 (D011-2: 内核分配端口).
"""

import argparse
import asyncio
import json
import os
import secrets
import signal
import socket
import sys
import time
from pathlib import Path

import uvicorn

from .launch import atomic_write_json, pid_alive
from .web.app import create_app

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "api-client"


def _bind(host: str) -> socket.socket:
    """bind(0): 内核分配随机空闲端口, 消除探测-绑定 TOCTOU (D011-2)."""
    try:
        addr_info = socket.getaddrinfo(
            host, 0, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
        )
    except socket.gaierror as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    family, _, _, _, sockaddr = addr_info[0]
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(sockaddr)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        sock.close()
        sys.exit(1)
    sock.listen()
    return sock


def _cmd_serve(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    local_dir = data_dir / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)

    token = secrets.token_urlsafe(32)  # 256 bit, >=128 bit 要求 (D004-4)
    sock = _bind(args.host)
    port = sock.getsockname()[1]
    atomic_write_json(
        local_dir / "service.json",
        {"port": port, "token": token, "pid": os.getpid()},
    )

    config = uvicorn.Config(create_app(token), log_level="info", access_log=False)
    server = uvicorn.Server(config)
    try:
        asyncio.run(server.serve(sockets=[sock]))
    except KeyboardInterrupt:
        pass


def _cmd_stop(args: argparse.Namespace) -> None:
    """按 --data-dir 定位 service.json, SIGTERM 停止 (D011-7); 不删 service.json."""
    service_json = Path(args.data_dir) / ".local" / "service.json"
    try:
        pid = int(json.loads(service_json.read_text())["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        print(f"Error: 无可停止的服务 ({service_json} 缺失或损坏)", file=sys.stderr)
        sys.exit(1)
    if not pid_alive(pid):
        print(f"服务已不在运行 (pid {pid}, stale service.json)")
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            print(f"已停止服务 (pid {pid})")
            return
        time.sleep(0.05)
    print(f"Error: 服务 (pid {pid}) 未在 10s 内退出", file=sys.stderr)
    sys.exit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apic", description="api-client 本地服务")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="前台起服务 (默认子命令)")
    serve.add_argument("--host", default="127.0.0.1", help="监听地址 (默认: 127.0.0.1)")
    serve.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="数据仓库目录 (默认: ~/.local/share/api-client/)",
    )
    serve.set_defaults(func=_cmd_serve)
    stop = sub.add_parser("stop", help="停止指定数据仓库的服务")
    stop.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="数据仓库目录 (默认: ~/.local/share/api-client/)",
    )
    stop.set_defaults(func=_cmd_stop)
    return parser


def main() -> None:
    argv = sys.argv[1:]
    # 默认子命令为 serve: `apic --data-dir X` 等价 `apic serve --data-dir X`
    if not argv or argv[0] not in ("serve", "stop"):
        argv = ["serve", *argv]
    args = _build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
