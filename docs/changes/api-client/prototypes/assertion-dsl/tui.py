"""断言 DSL 原型 — 终端外壳 (一次性, 用后即焚).

问题陈述见 dsl.py 顶部. 样例响应取自测试后端 (src/testbed/) 真实形状.

运行: uv run python docs/changes/api-client/prototypes/assertion-dsl/tui.py

命令:
  1-4                              切换响应样例
  a <target> <op> <expect>         新增断言 (expect 先试 JSON 解析, 失败按字符串)
  a <target> schema <json>         新增 jsonschema 断言
  d <序号>                         删除断言
  y                                开关 YAML 序列化预览 (集合文件里的存储形态)
  q                                退出
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dsl import MISSING, OPS, Response, evaluate, to_yaml
from fixtures import FIXTURES


def parse_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def render(name: str, resp: Response, assertions: list[dict], show_yaml: bool):
    print("\033[2J\033[H", end="")
    print(f"\033[1m样例:\033[0m {name}")
    print(f"\033[2m  status={resp.status}  elapsed={resp.elapsed_ms}ms  headers={resp.headers}\033[0m")
    body = resp.body_text
    print(f"\033[2m  body={body[:200]}{'…' if len(body) > 200 else ''}\033[0m")
    print()
    print("\033[1m断言与结果:\033[0m")
    if not assertions:
        print("  \033[2m(空)\033[0m")
    results = evaluate(resp, assertions)
    passed = sum(1 for r in results if r.ok)
    for i, (a, r) in enumerate(zip(assertions, results), 1):
        mark = "\033[32m✓\033[0m" if r.ok else "\033[31m✗\033[0m"
        actual = "" if r.ok else f"  \033[2m实际={r.actual if r.actual is not MISSING else '<无>'}  {r.message}\033[0m"
        print(f"  {mark} [{i}] {json.dumps(a, ensure_ascii=False)}{actual}")
    print(f"\n  通过 {passed}/{len(results)}")
    if show_yaml:
        print()
        print("\033[1m集合文件中的形态 (YAML):\033[0m")
        print("\033[2massert:\033[0m")
        for line in to_yaml(assertions).splitlines():
            print(f"  {line}")
    print()
    print("\033[1m[1-4]\033[0m 样例  \033[1m[a]\033[0m 加断言  \033[1m[d n]\033[0m 删  \033[1m[y]\033[0m YAML  \033[1m[q]\033[0m 退出")


def main():
    idx, show_yaml = 0, True
    assertions = [list(f[2]) for f in FIXTURES]
    while True:
        name, resp, _ = FIXTURES[idx]
        current = assertions[idx]
        render(name, resp, current, show_yaml)
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd == "q":
            break
        if cmd in ("1", "2", "3", "4"):
            idx = int(cmd) - 1
        elif cmd == "y":
            show_yaml = not show_yaml
        elif cmd.startswith("d "):
            try:
                del current[int(cmd[2:]) - 1]
            except (ValueError, IndexError):
                pass
        elif cmd.startswith("a "):
            parts = cmd[2:].split(None, 2)
            if len(parts) == 3 and parts[1] == "schema":
                try:
                    current.append({"target": parts[0], "schema": json.loads(parts[2])})
                except json.JSONDecodeError:
                    input("schema JSON 解析失败, 回车继续")
            elif len(parts) == 3 and parts[1] in OPS:
                current.append({"target": parts[0], "op": parts[1], "expect": parse_value(parts[2])})
            elif len(parts) == 2 and parts[1] == "exists":
                current.append({"target": parts[0], "op": "exists"})
            else:
                input(f"用法: a <target> <{'|'.join(OPS)}> <expect>  或  a <target> schema <json>, 回车继续")


if __name__ == "__main__":
    main()
