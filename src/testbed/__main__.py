"""testbed 启动入口: `python -m testbed` 或 console script `testbed`."""

import argparse
import asyncio
import socket
import sys

import uvicorn


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="testbed", description="自研最小 HTTP 测试后端")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="监听端口 (默认: 8000; 0 表示由内核分配)",
    )
    return parser


async def _serve(host: str, port: int) -> None:
    try:
        addr_info = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
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
    actual_port = sock.getsockname()[1]
    print(f"listening on http://{host}:{actual_port}", flush=True)

    config = uvicorn.Config("testbed.app:app", log_level="info")
    server = uvicorn.Server(config)
    await server.serve(sockets=[sock])


def main() -> None:
    args = _build_parser().parse_args()
    try:
        asyncio.run(_serve(args.host, args.port))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
