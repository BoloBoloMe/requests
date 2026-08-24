# ISSUE-02 — send 单请求执行

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: `send <item-ref> [--env NAME] [--var KEY=VALUE]... [--output json|ndjson|pretty]` 连服务执行单个请求并渲染事件流 (M4-D002/D003). item-ref 格式 `<collection>/<slug>`; 客户端做格形式校验 (畸形引用 → USAGE_ERROR/USAGE exit 2), 存在性交服务端判定. 经 `client.connect` ensure_running 后 `POST /execute` (Accept `application/x-ndjson`) 携 `X-Auth-Token`, 请求体 `{collection, item, env?, vars?}` (08 契约协调点, 见停止条件); 逐行消费服务端 NDJSON 事件流 (meta/chunk/done). 输出三形态: ndjson 逐行 (默认) / json 收集为事件数组 / pretty 每行以事件 type 开头 + 完整 JSON (禁 repr, 第三轮 dogfood 修正). 退出码 (M4-D004): 0 成功 / 1 断言失败 (done.assertions 任一 not passed, stdout 仍产出数据) / 2 用法或未解析变量 (UNRESOLVED_VARIABLES, 服务端判定, 不产生事件流) / 3 SERVICE_ERROR / 4 未找到. 错误统一 stderr `{"error":{code,message,details}}`, stdout 保持干净. NOT_FOUND 细分 COLLECTION/ITEM/ENV_NOT_FOUND 并带 `details.candidates` (difflib + 子串并集, M4-D004/dogfood): 优先透传服务端 error.details.candidates, 无则 CLI 客户端经 inventory API (collection list / item list / env list) 取清单后用 difflib+子串算候选兜底 (错误恢复/展示, 非业务执行逻辑, M3-D001 允许). 适合 AFK: 命令/输出/错误模型全由 M4 原型与账本钉死.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-10.md`, CLI 实现 (send 单请求)
- 决策: `docs/changes/api-client/milestone-04/DECISIONS.md`, D002/D003/D004/D006; `docs/changes/api-client/milestone-03/DECISIONS.md`, D007/D010/D014-4

## 相关决策
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D002 (输出契约 NDJSON/JSON/pretty), D003 (meta/chunk/done 事件契约), D004 (退出码 0-4 + 细分错误码 + candidates), D006 (未解析变量硬失败, 无事件流)
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D007 (JSONL 单一事件流协商), D010 (REST+RPC 消费面, POST /execute), D014-4 (CLI 用 fake HTTP 测参数解析与输出渲染)

## 允许范围
- 新建 `src/api_client_cli/commands_send.py` (send handler) 及 `output.py` 流式渲染, `errors.py` 退出码/错误映射, `candidates.py` (difflib+子串候选兜底), `tests/api_client_cli/test_send.py`, `tests/api_client_cli/test_errors.py`.
- `contract.py` 常量源 (事件字段/退出码/错误码) 供本 issue 输出与 ISSUE-04 的 schema/guide 共用.
- 可调用 `collection list`/`item list <c>`/`env list` 端点 (见 08) 作 candidates 兜底清单.

## 禁止范围
- 不自己做变量解析/断言求值/执行 (M3-D001) — UNRESOLVED_VARIABLES/断言结果/not-found 一律以服务端响应为准, 只做映射与渲染.
- 不做 TUI; 不 import 核心库除 launch 外模块; 不接管 git.
- 不修改 `src/api_client/`、`tests/api_client/`、`src/testbed/`、`tests/testbed/`; 不改 DECISIONS/ADR.

## 代码定位提示
- 参照: `docs/changes/api-client/prototypes/cli-shell/apic.py` (`_cmd_send`/`_stream`/`_all_assertions_passed`/`_find_candidates`/`_emit_*`), `docs/changes/api-client/milestone-08/EXECUTION.md` (POST /execute, 事件模型), `docs/changes/api-client/milestone-08/issues/ISSUE-03` (execute 请求体/协商).
- 阅读顺序: `commands_send.py` → `output.py` → `errors.py` → `candidates.py` → 两个测试文件.

## TDD 切片
- TS-001 (NDJSON 流式渲染, fake HTTP):
  接缝: fake service.json 指向 fake HTTP server, fake server 对 `/execute` 回放 meta→chunk→done 三条 NDJSON; CLI subprocess.
  测试用例: TC-001 — 输出恰为三条逐行 NDJSON 事件 (字段与 meta/chunk/done 契约逐字一致), exit 0; TC-002 — 请求体携带 collection/item/env/vars, 请求头带 X-Auth-Token.
  先写的失败测试: `test_send_renders_ndjson_events_exit_0` — 预期失败: 未实现消费/渲染.
  最小绿色实现范围: send handler + connect + POST /execute (ndjson) + 逐行转发 stdout.
  不得测试: 服务端执行逻辑; 断言求值.
  覆盖: M4-D002/D003, M3-D007/D010.
- TS-002 (断言失败 exit 1): fake server 回放 done 含一条 not passed 断言.
  测试用例: TC-003 — 事件流完整渲染 (stdout 有数据), exit 1.
  先写的失败测试: `test_send_assertion_failure_exit_1` — 预期失败: 未按 done.assertions 判失败时 exit 0.
  最小绿色实现范围: 消费 done 时检测断言 passed, 据此定退出码, 不影响渲染.
  不得测试: 断言算法本身.
  覆盖: M4-D004.
- TS-003 (输出三形态): 同 fake server 回放; 分别 `--output json`/`pretty`.
  测试用例: TC-004 — json = 事件数组 (含全部事件); TC-005 — pretty 每行以事件 type 开头 + 完整 JSON, 字段值 JSON 渲染 (禁 repr, chunk.data 合法 JSON).
  先写的失败测试: `test_send_output_json_is_event_array` — 预期失败: 未按 --output 分流.
  最小绿色实现范围: 三种渲染原语 + --output 路由.
  不得测试: 内存布局; 私有 renderer 细节.
  覆盖: M4-D002.
- TS-004 (错误映射 + 退出码): fake server 对 /execute 返回错误对象.
  测试用例: TC-006 — COLLECTION_NOT_FOUND → stderr `{"error":{code,message,details}}`, stdout 空, exit 4; TC-007 — SERVICE_ERROR / 连接失败重试后仍败 → exit 3; TC-008 — 畸形 item-ref (缺斜杠) → USAGE_ERROR exit 2.
  先写的失败测试: `test_send_not_found_exit_4_stderr_only` — 预期失败: 未映射 code→退出码/未写 stderr.
  最小绿色实现范围: 服务端错误对象解析 + code→退出码映射 + stderr 渲染 + 客户端格式校验.
  不得测试: 服务端错误成因.
  覆盖: M4-D004, M3-D011.
- TS-005 (candidates 纠错): 场景对齐 dogfood "拼错 ref 只凭错误输出自动纠错".
  测试用例: TC-009 — 服务端返回 error.details.candidates → CLI 原样透传 stderr; TC-010 — 服务端无 candidates 时, CLI 经 inventory API 取清单, 客户端 difflib+子串算出 candidates (如 `get-jsn`→`get-json`).
  先写的失败测试: `test_send_not_found_client_candidates_fallback` — 预期失败: 服务端无候选时 details 无 candidates (dogfood 扣分项).
  最小绿色实现范围: candidates 优先透传 + 兜底经清单算 difflib+子串并集; details 缺省为空数组.
  不得测试: difflib 内部相似度实现.
  覆盖: M4-D004.
- TS-006 (未解析变量硬失败): fake server 返回 UNRESOLVED_VARIABLES + details.missing.
  测试用例: TC-011 — stderr 错误对象, 无事件流 (stdout 空), exit 2.
  先写的失败测试: `test_send_unresolved_variables_no_stream_exit_2` — 预期失败: 未识别该错误码时误 exit 0.
  最小绿色实现范围: UNRESOLVED_VARIABLES → exit 2 映射 + 不渲染任何事件.
  不得测试: 变量解析 (服务端职责).
  覆盖: M4-D006.

## 验证入口
- `uv run pytest tests/api_client_cli/test_send.py tests/api_client_cli/test_errors.py` — 全绿.
- 真实端到端 (待 08, 标人工/HITL): `uv run apic send <c>/<item> --env <e>` 打 testbed 靶子 → meta/chunk/done, exit 0; 失败断言条目 → exit 1; 拼错 ref → exit 4 且 stderr candidates 可纠错.

## 风险提示
- /execute 请求体须携带 env/vars: 08 ISSUE-03 验证体仅 `{collection,item}`; 若 08 未支持 env/vars, 本 issue 的 --env/--var 无法透传 → 报父会话 HITL 协调, 不擅自改 08.
- 服务端错误响应格式须为 `{"error":{code,message,details}}`; 若 08 返回非此格式 (如裸 404/500), CLI 需兜底解析并映射, 格式不符亦是协调点.
- candidates 兜底属 error-recovery 展示逻辑, 不得越界成执行/解析业务逻辑 (M3-D001).

## 停止条件
- 需改变 M4 输出/事件/错误契约或退出码, 或 /execute 消费契约与 08 无法协调时停止.

## 适合 AFK 的原因
- send 命令面/输出/事件/退出码/候选纠错全由 M4 原型 (三轮 dogfood 定稿) 与账本钉死, 无待定产品决策; 真端到端子项已标人工验证.

## 验收标准
- [ ] send 依默认 ndjson 流式渲染 meta/chunk/done, 三形态 (ndjson/json数组/pretty) 正确.
- [ ] 退出码 0/1/2/3/4 映射与错误 stderr JSON (stdout 干净) 一致.
- [ ] NOT_FOUND 细分 + details.candidates 可自动纠错 (服务端透传 + 客户端兜底).
- [ ] UNRESOLVED_VARIABLES → exit 2, 不产生事件流.

## 被阻塞于
- ISSUE-01 (服务 client/launch 接入/骨架/send 占位)
