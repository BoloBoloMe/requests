# apic CLI Shell 原型

本目录放置一个可丢弃的 CLI 外壳原型, 用来验证命令面、结构化输出、退出码和可发现性的设计.

## 运行方式

仓库使用 `uv`, 但脚本本身只依赖 Python 标准库, 也可以直接用 `python3` 运行.

```bash
# 默认执行方式
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py <command> [args]

# 单个请求, 默认 NDJSON 流
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py send demo/get-json

# 使用环境变量
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py send demo/get-json --env dev

# 带额外变量
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py send demo/get-json --env dev --var host=localhost:8000

# 调试阅读
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py send demo/get-json --output pretty

# 批量运行集合
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py run demo

# 资源浏览
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py collection list
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py item list demo
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py env list
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py history list

# 服务生命周期
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py service status
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py service token

# Agent 自发现
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py schema
uv run python docs/changes/api-client/prototypes/cli-shell/apic.py guide
```

## 设计提案要点

1. 命令面 (command surface)
   - 执行: `send <item-ref>` / `run <collection-ref>`
   - 资源: `collection` / `item` / `env` / `history`
   - 服务: `service status/stop/token`
   - 自描述: `schema` / `guide`
   - 多级 `--help` 可用, epilog 带面向 AI 的调用示例与退出码/错误码/事件流契约.

2. 结构化输出
   - 全局 `--output json|ndjson|pretty`
   - `send` / `run` 默认 `ndjson`, 实时流式输出事件
   - 其余命令默认 `json`, 输出单个 JSON 对象到 stdout
   - `pretty` 仅供人类调试, 不保证机器可读; 字段值统一用 JSON 渲染

3. 事件流
   - `send`: `meta` → 若干 `chunk` → `done`
   - `run`: 每个 item 一组 `meta` / `chunk` / `done`, 末尾 `summary`
   - `meta` / `chunk` / `done` 均带 `item` 字段 (等于 `<collection>/<slug>`)
   - `done` 包含 `status` / `duration_ms` / `assertions` 结果
   - `summary` 包含 `total` / `passed` / `failed` / `items`

4. 退出码
   - `0` OK
   - `1` ASSERTION_FAILED (领域失败, stdout 仍产出数据)
   - `2` USAGE_ERROR (包括未解析变量与错误 CLI 调用)
   - `3` SERVICE_ERROR
   - `4` NOT_FOUND
   - `schema` 和 `guide` 都列出此表.

5. 错误输出
   - 错误统一输出到 stderr, 格式 `{"error": {"code": "...", "message": "...", "details": {...}}}`
   - stdout 保持干净, 便于 agent 解析
   - `NOT_FOUND` 细分为 `COLLECTION_NOT_FOUND` / `ITEM_NOT_FOUND` / `ENV_NOT_FOUND`,
     并在 `details.candidates` 中给出子串/前缀匹配的候选 (无候选则为空数组)
   - 未解析变量 `{{...}}` 会报 `UNRESOLVED_VARIABLES`, 不产出正常事件流

6. 可发现性
   - `schema` 输出完整命令树、参数、输出模式、事件定义、退出码表、错误码表、错误格式
   - `schema` 中 `event_stream` 使用精确字段列表, 禁止 `...` 省略
   - `guide` 输出 ~70 行的 llms.txt 风格纯文本手册
   - 帮助 epilog 提供可直接复制的 AI 示例与机器契约摘要

## 第二轮修正

两轮 AI 实弹试用后, 针对以下 5 个问题做了修复:

1. **未解析变量静默成功**
   原 `send demo/get-json` 不带 `--env` 时 URL 仍含 `{{host}}` 且 exit 0.
   现在 `send`/`run` 在解析后扫描 URL/headers/body 残留占位符, 存在则 stderr 输出
   `UNRESOLVED_VARIABLES` (exit 2) 并携带 `details.missing`, 不生成正常事件流.
   原因: agent 依赖退出码判断请求是否真正执行, 残留模板应视为调用错误.

2. **run 与 send 事件契约不一致**
   原 `run` 每个 item 只发 `meta` + `done`, 吞掉了 `chunk`.
   现在 `run` 与 `send` 同构: 每个 item 输出完整 `meta` / `chunk` / `done` 序列;
   每个事件都带 `item` 字段; 末尾仍发 `summary`.
   原因: agent 解析器可以复用同一套事件处理逻辑.

3. **NOT_FOUND 过粗, 无纠错支持**
   原所有资源缺失统一返回 `NOT_FOUND`.
   现在细分为 `COLLECTION_NOT_FOUND` / `ITEM_NOT_FOUND` / `ENV_NOT_FOUND` (exit 仍 4),
   `details.candidates` 按简单子串/前缀匹配给出候选, 无候选时为空数组.
   原因: agent 需要区分缺失类型并自动纠错.

4. **--help 缺机器契约**
   原顶层 `--help` epilog 只有一句话示例.
   现在 epilog 增加紧凑三节: Exit codes / Error codes / Event stream,
   列出所有机器可识别的代码与事件字段.
   原因: agent 第一次调用前就能从帮助文本读出完整契约.

5. **pretty 输出 repr 而非 JSON**
   原 `pretty` 模式使用 `str()`/`repr()` 打印字段值.
   现在统一用 `json.dumps(..., ensure_ascii=False)` 渲染, 特别是 `chunk.data`.
   原因: 人类调试输出也应保持 JSON 语义, 方便与 stdout 流对比.

## 第三轮修正

第三轮 AI 复测后, 针对以下 5 个契约出入再做修复:

1. **help 事件流字段名与实现不符**
   顶层 `--help` epilog 的 Event stream 节写 `meta(...,url)`, 实现字段为 `resolved_url`;
   chunk 实际带 `index`/`timestamp` 等字段也未列出.
   现已对照 `send demo/sse-stream --env prod` 与 `run demo --env prod` 的实测字段,
   将 help 的事件流字段列表改为与实现逐字一致.

2. **candidates 匹配过弱**
   原仅做大小写不敏感子串匹配, `get-jsn` 对 `get-json` 返回空候选.
   现已统一使用 `difflib.get_close_matches` (cutoff 0.6) 与子串匹配取并集,
   collection/item/env 三处候选提示均生效.

3. **--var 优先级与动态变量未文档化**
   `--var KEY=VALUE` 本就覆盖环境变量, `{{$now}}`/`{{$uuid}}` 本应由引擎求值;
   但 help/guide 未写明, 且未解析变量检查未排除动态变量.
   现已在 `send`/`run` 的 `--help` 与 `guide` 中写明覆盖关系与动态变量例外,
   并确保 `_extract_unresolved` 将 `$now`/`$uuid` 排除在报错范围外.

4. **--output 组合语义不清**
   原 schema/guide 对 `json`/`ndjson`/`pretty` 的描述未区分流式与非流式命令.
   现已改为: 流式命令 (send/run) json=事件数组, ndjson=逐行事件, pretty=人类可读事件 dump;
   非流式命令 json=单对象, ndjson=等同 json (单行), pretty=表格/缩略.
   行为未改, 仅契约描述与行为一致.

5. **pretty 模式丢 type 字段**
   原 pretty 输出用 `[META]`/`[CHUNK]` 节头, 行首不含事件 type.
   现已改为每行以事件 type 开头, 后接完整 JSON 对象, 字段值仍用 `json.dumps(..., ensure_ascii=False)`.

## 已知偏差

- 本原型是命令行外壳原型, 不是交互式 TUI, 也不是 UI 变体.
- 执行核心是进程内 stub, 只验证 CLI 形状, 不验证真实 HTTP、进程模型、认证、安全或持久化.
- `--output json` 在 `send` / `run` 下会收集全部事件后输出 JSON 数组, 主要用于人类调试; 真实瘦客户端应当与服务端保持 NDJSON 流.
- `--var` 只做简单字符串替换, 不做类型推断.
- 无测试、无泛化抽象、无状态保存.
