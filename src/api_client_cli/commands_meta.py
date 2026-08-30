"""元命令 (M4 D005 双通道可发现性): schema 机读契约 + guide 文读手册.

两命令离线可答 (不拉起服务); 内容全部由 contract.py 常量源组装, 禁止手写副本
(防 dogfood 扣分项: help/schema 字段名与实现漂移).
"""

import sys

from . import contract
from .output import emit_object
from .schema_data import build_schema


def cmd_schema(args) -> int:
    """输出完整机读契约 (单 JSON 对象, 事件字段精确逐字无省略)."""
    emit_object(build_schema(), "json")
    return contract.EXIT_OK


def _guide_text() -> str:
    """llms.txt 风格文读手册; 机器契约节 (退出码/错误码/事件字段) 由常量源拼装."""
    exit_line = " / ".join(f"{c['code']} {c['label']}" for c in contract.EXIT_CODES)
    error_line = ", ".join(c["code"] for c in contract.ERROR_CODES)
    output_lines = "\n".join(f"  --output {name:<7} {desc}" for name, desc in contract.OUTPUT_MODES.items())
    return f"""# apic 指南 (AI agent 文读手册)

apic 是 AI 友好的 API client 命令行外壳: 瘦客户端, 连本地服务执行.
服务由 CLI 按 --data-dir 幂等拉起; 无交互, stdout 只出数据, 错误走 stderr.

## 快速示例

  apic schema
  apic guide
  apic send demo/get-json
  apic send demo/get-json --env dev --var host=127.0.0.1:9000
  apic run demo
  apic collection list

## 命令面

执行 (流式事件):
  send <item-ref> [--env NAME] [--var KEY=VALUE]...
  run <collection-ref> [--env NAME] [--var KEY=VALUE]...

资源查询 (非流式, 单 JSON):
  collection list | collection show <ref>
  item list <collection-ref> | item show <item-ref>
  env list | env show <name>
  history list | history show <id>

服务:
  service status | service stop | service token

元命令:
  schema   # 完整机读契约 (命令树/参数/事件/退出码/错误码/错误格式)
  guide    # 本文档

## 全局参数

  --output json|ndjson|pretty   输出形态 (send/run 默认 ndjson, 其余 json)
  --data-dir PATH               数据仓库目录 (默认 {contract.DEFAULT_DATA_DIR}/)

## 输出模式

{output_lines}

## 事件流 (send/run)

  {contract.EVENT_STREAM_LINE}

send 末尾为 done; run 逐条目 meta/chunk/done (不吞 chunk), 末尾 summary.
{contract.RUN_REPORT_NOTE}

## Exit codes

  {exit_line}

断言失败为领域失败 (exit 1): 数据正常产出, 但至少一条断言未通过.

## Error codes

  {error_line}

错误形状: stderr 单行 {{"error":{{"code","message","details"}}}}, stdout 保持干净.
NOT_FOUND 类错误 details.candidates 列出相近引用 (集合/条目/环境名) 供纠错.

## item-ref

<item-ref> 恒为 <collection>/<slug>, 例: demo/get-json.
collection-ref 为集合名, 例: demo.

## 变量与未解析变量

--var KEY=VALUE 覆盖环境变量, 可重复, send/run 均可用; 优先于环境变量.
变量替换后 URL/headers/body 仍残留 {{{{NAME}}}} 占位符:
send 单条 -> exit 2 UNRESOLVED_VARIABLES, 不产生事件流 (硬失败);
run 整批 -> 该条目跳过 (不发 HTTP, 合成 done 含 error.code=UNRESOLVED_VARIABLES,
计入 summary failed 与 JUnit errors), 其余条目照常, 整批 exit 1.
动态变量 {{{{$now}}}} / {{{{$uuid}}}} 由引擎在运行时求值, 不视为未解析.
"""


def cmd_guide(args) -> int:
    """输出文读手册 (纯文本)."""
    sys.stdout.write(_guide_text())
    return contract.EXIT_OK
