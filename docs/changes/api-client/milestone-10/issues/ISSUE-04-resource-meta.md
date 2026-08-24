# ISSUE-04 — 资源组 CRUD + schema/guide 元命令

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: 资源名词组命令面 (M4-D001) — `collection list` / `collection show <ref>`, `item list <collection-ref>` / `item show <item-ref>`, `env list` / `env show <name>`: 经 `client.connect` 打 REST 端点 (M3-D010 `GET /collections`, `GET /collections/{c}/items`, `GET /collections/{c}/items/{slug}`, `GET /environments`, `GET /environments/{name}`, 08 协调点), 非流式命令默认单 JSON 对象 (M4-D002, `--output json` 同, `ndjson` 等同单行, `pretty` 表格/缩略可回退 JSON). NOT_FOUND 细分 + candidates 纠错沿用 ISSUE-02. 元命令可发现性 (M4-D005 双通道): `schema` 输出完整机读契约 (命令树/参数/输出模式/事件定义/退出码表/错误码表/错误格式, 事件字段精确逐字, 禁止 `...` 省略 — dogfood 第一轮扣分项) 由实现侧单一常量源 `contract.py` 直接产出, 与实现逐字一致; `guide` 输出 ~70 行 llms.txt 风格纯文本手册 (示例/命令面/输出模式/退出码/错误码/item-ref/变量/未解析变量语义). 每个子命令 `--help` 带示例 (第二/三轮 dogfood), 顶层 epilog 三节机器契约 (exit/error/event) 与 schema/guide 引用同一常量源, 杜绝首轮/二轮 dogfood 的 help 字段名与实现不符 (D005). 适合 AFK: 命令面/可发现性契约全由 M4 原型 (三轮 dogfood 定稿) 钉死.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-10.md`, CLI 实现 (资源管理 + 可发现性)
- 决策: `docs/changes/api-client/milestone-04/DECISIONS.md`, D001/D002/D005; `docs/changes/api-client/milestone-03/DECISIONS.md`, D010/D014-4

## 相关决策
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D001 (动作动词 + 资源名词组 collection/item/env + 元命令 schema/guide), D002 (非流式命令默认单 JSON 对象), D005 (双通道发现性, schema/guide/help 与实现逐字一致)
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D010 (REST 资源 CRUD 消费面), D014-4 (CLI 用 fake HTTP)

## 允许范围
- 新建 `src/api_client_cli/commands_resources.py` (collection/item/env list/show), `commands_meta.py` (schema/guide), `schema_data.py` (从 `contract.py` 常量源组装 schema 的机读结构), `tests/api_client_cli/test_resources.py`, `tests/api_client_cli/test_contract.py`.
- `contract.py` 常量源 (事件字段/退出码/错误码/命令面) 为本 issue 与 ISSUE-02 共用; 本 issue 使其成为 help/schema/guide 的唯一事实源.
- 可编辑 `__main__.py` 的 argparse 树 (list/show 参数 + 各层 help 示例 + 顶层/子命令 epilog).

## 禁止范围
- 不做资源写操作/创建/删除 (CLI 只读查询面, M4 原型命令面如此; 00 的 PUT/DELETE 不暴露 CLI); 不做 schema/guide 手写副本与实现漂移 (D005 要求同源).
- 不 import 核心库除 launch 外; 不接管 git; 不做 TUI; 不做 send/run (材质 ISSUE-02/03).
- 不修改 `src/api_client/`、`tests/api_client/`、`src/testbed/`、`tests/testbed/`; 不改 DECISIONS/ADR.

## 代码定位提示
- 参照: `docs/changes/api-client/prototypes/cli-shell/apic.py` (`_cmd_collection_*`/`_cmd_item_*`/`_cmd_env_*`/`_cmd_schema`/`_cmd_guide`/help epilog), `docs/changes/api-client/milestone-08/issues/ISSUE-02` (REST 端点/排序), `docs/changes/api-client/milestone-04/DECISIONS.md` D005.
- 阅读顺序: `contract.py` → `schema_data.py` → `commands_resources.py` → `commands_meta.py` → `__main__.py` (help/epilog 接线) → 两个测试文件.

## TDD 切片
- TS-001 (collection/item/env list/show 渲染, fake HTTP):
  接缝: fake HTTP server 回放各 REST 端点 canned 响应; CLI subprocess 带 `--data-dir`.
  测试用例: TC-001 — `collection list` 输出单 JSON 数组 (ref/name/item_count); `collection show <ref>` 单对象; TC-002 — `item list <c>` 输出 ref/method/url; `item show <ref>` 单对象; TC-003 — `env list`/`env show <name>` 同; TC-004 — 不存在资源 → 404 → exit 4 + stderr 错误 + candidates (若无服务端候选, 客户端经清单兜底).
  先写的失败测试: `test_collection_list_renders_json_array` — 预期失败: 未接 REST 端点.
  最小绿色实现范围: 六个资源 handler + GET 调用 + 单 JSON 渲染 + 404 映射 + 候选兜底 (复用 ISSUE-02).
  不得测试: Store 领域细节; 写操作.
  覆盖: M4-D001/D002, M3-D010.
- TS-002 (schema 机读契约同源): `schema` 输出.
  测试用例: TC-005 — schema 含命令树/参数/输出模式/事件定义/退出码表/错误码表/错误格式, 事件字段精确逐字 (无 `...` 省略); TC-006 — schema 的退出码/错误码/事件字段与 `contract.py` 常量源逐字一致 (自动比对, 防漂移).
  先写的失败测试: `test_schema_event_fields_match_contract_source` — 预期失败: 手写 schema 与常量源有 `...` 或字段名差异.
  最小绿色实现范围: schema 从 `contract.py` 组装, 事件字段/退出码/错误码不手写副本; 一致性测试比对.
  不得测试: 演进中未发布字段.
  覆盖: M4-D005.
- TS-003 (guide 文读手册 + help 契约一致): `guide` 输出 + 各层 `--help`.
  测试用例: TC-007 — guide 含快速示例/命令面/输出模式/退出码/错误码/item-ref/未解析变量语义 (UNRESOLVED 与 $now/$uuid 例外); TC-008 — 顶层 help epilog 的 exit/error/event 三节与 schema/contract 一致 (字段名逐字一致, 不回退 `url` vs `resolved_url` 类错配, dogfood 二轮扣分项).
  先写的失败测试: `test_help_epilog_matches_contract` — 预期失败: help 手写字段与常量源不一致.
  最小绿色实现范围: guide 内容 + help epilog 从 `contract.py` 模板化, 一致性测试.
  不得测试: REAME 文案措辞.
  覆盖: M4-D005, D002.
- TS-004 (pretty 可回退): 非流式命令 `--output pretty`.
  测试用例: TC-009 — `collection list --output pretty` 输出人可读表格/缩略, 值 JSON 渲染 (可回退 JSON, 不保证机器可读, M4 残留项).
  先写的失败测试: `test_resources_pretty_falls_back_json` — 预期失败: pretty 未对非流式命令定义.
  最小绿色实现范围: 非流式 pretty 渲染 (表格/缩略或回退 JSON).
  不得测试: 表格细节.
  覆盖: M4-D002.

## 验证入口
- `uv run pytest tests/api_client_cli/test_resources.py tests/api_client_cli/test_contract.py` — 全绿.
- `uv run apic schema` 输出完整机读契约且无省略号; `uv run apic guide` 输出文读手册; `uv run apic --help` epilog 三节与 schema 一致.
- 真实 agent 场景 (标人工/HITL): 全新上下文 agent 仅经 `--help` 与经 `schema`+`guide` 各完成一组资源查询/执行任务, 对标 DOGFOOD 自学习任务集, 契约零偏差.

## 风险提示
- 契约同源是 dogfood 扣分主力 (help 字段名, schema 省略号): 事件字段/退出码/错误码必须单源且逐字比对, 禁止手写副本.
- 资源 REST 端点路径为 08 协调点; 不符报父会话, 不擅自改 08.
- pretty 对非流式命令的表格回退为 M4 明示残留, 实现简化 (可回退 JSON) 即可, 不扩散.

## 停止条件
- 需改变 M4 命令面/可发现性契约, 或资源端点消费与 08 无法协调时停止.

## 适合 AFK 的原因
- 资源命令面与 schema/guide 双通道全由 M4 原型 (三轮 dogfood 定稿) 与账本钉死, 契约可自动比对防漂移, 无待定产品决策; agent 场景标人工验证.

## 验收标准
- [ ] collection/item/env list/show 非流式默认单 JSON 渲染, 404 → exit 4 + candidates.
- [ ] schema 从常量源产出, 事件字段/退出码/错误码与实现逐字一致, 无省略.
- [ ] guide 与顶层 help epilog 三节与 schema/contract 同源一致.
- [ ] pretty 对非流式命令可用 (可回退 JSON).

## 被阻塞于
- ISSUE-02 (服务 client/错误映射/candidates/contract.py 常量源)
