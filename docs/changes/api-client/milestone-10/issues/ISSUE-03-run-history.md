# ISSUE-03 — run 集合批量 + history 历史查询

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: `run <collection-ref> [--env] [--var]... [--output ...]` 连服务批量执行集合并渲染事件流 (M4-D003): 经 `client.connect` 后 `POST /collections/{c}/run` (Accept `application/x-ndjson`, 请求体携 env/vars, 08 协调点), 逐行消费每个条目的完整 meta/chunk/done (不吞 chunk — agent 须能从 run 输出直接定位失败条目响应体, M4-D003 首轮 dogfood 教训) + 末尾 summary(total/passed/failed/items) 与 report 事件. run 与 send 复用同一套事件渲染逻辑 (同构, M4-D003). 输出三形态 (M4-D002): ndjson 逐行 / json 事件数组 / pretty 每行 type 开头. 退出码: 依 summary.failed>0 → exit 1, 否则 0; 服务端错误映射 2/3/4 同 ISSUE-02. `history list` / `history show <id>` 非流式命令, 默认单 JSON 对象 (M4-D002): 经 `GET /history` (最近优先, 08 协调点) 与 `GET /history/{id}` 取数渲染; 条目含 id/item_ref/env/status/started_at/duration_ms/assertions 计数. runner 顺序执行语义交服务端 (M3-D013), CLI 只消费渲染. 适合 AFK: 批量/事件/历史语义全由 M4 原型与账本钉死.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-10.md`, CLI 实现 (run 批量 + 历史查询)
- 决策: `docs/changes/api-client/milestone-04/DECISIONS.md`, D002/D003; `docs/changes/api-client/milestone-03/DECISIONS.md`, D010/D013/D014-4

## 相关决策
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D003 (run/send 同构事件流 + summary, 不吞 chunk), D002 (输出三形态)
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D010 (REST /history/... + RPC POST /collections/{x}/run), D013 (runner v1 顺序执行), D014-4 (CLI 用 fake HTTP)

## 允许范围
- 新建 `src/api_client_cli/commands_run.py` (run handler, 复用 ISSUE-02 事件渲染) 与 `commands_history.py` (list/show), `tests/api_client_cli/test_run.py`, `tests/api_client_cli/test_history.py`.
- 复用 `output.py`/`errors.py`/`contract.py`; 可调用 `GET /history` 与 `GET /history/{id}` (08 协调点).

## 禁止范围
- 不做顺序/并发执行 (M3-D013 服务端职责); 不做历史落盘/聚合 (服务端 Engine/Store 职责, M3-D008) — 纯查询渲染.
- 不吞 chunk 或重排事件; 不 import 核心库除 launch 外; 不接管 git; 不做 TUI.
- 不修改 `src/api_client/`、`tests/api_client/`、`src/testbed/`、`tests/testbed/`; 不改 DECISIONS/ADR.

## 代码定位提示
- 参照: `docs/changes/api-client/prototypes/cli-shell/apic.py` (`_cmd_run`/`_event_summary`/summary 统计/`_cmd_history_*`), `docs/changes/api-client/milestone-08/issues/ISSUE-05` (POST /collections/{x}/run, report 事件) 与 `ISSUE-03` (历史端点), `docs/changes/api-client/milestone-04/DECISIONS.md` D003.
- 阅读顺序: `commands_run.py` → `commands_history.py` → 两个测试文件.

## TDD 切片
- TS-001 (run 事件流 + summary, fake HTTP):
  接缝: fake service.json 指向 fake HTTP server, fake 对 `/collections/demo/run` 回放 2 条目 (ECHO 通过 + 1 失败) 的 meta/chunk/done x2 + summary + report; CLI subprocess.
  测试用例: TC-001 — 每个条目完整 meta/chunk/done, chunk 不吞 (失败条目响应体在 run 输出可定位), 末尾 summary(total/passed/failed/items); TC-002 — summary.failed>0 → exit 1, 失败=0 → exit 0; TC-003 — 请求体携 collection/env/vars.
  先写的失败测试: `test_run_emits_chunk_per_item_no_swallow` — 预期失败: 若只发 meta/done 吞 chunk 则失败条目响应体不可定位 (M4-D003 教训).
  最小绿色实现范围: run handler + POST /collections/{c}/run + 逐事件渲染 (复用 send 渲染器) + summary 退出码判定.
  不得测试: 批量顺序/统计 (runner 已测); 报告生成.
  覆盖: M4-D003, M3-D010/D013.
- TS-002 (run 三形态): 同 fake 回放.
  测试用例: TC-004 — `--output json` 事件数组含全部条目事件; TC-005 — `--output pretty` 每行 type 开头 + JSON.
  先写的失败测试: `test_run_output_json_is_full_event_array` — 预期失败: 未按 --output 分流.
  最小绿色实现范围: 复用 ISSUE-02 渲染原语于 run 流.
  不得测试: 渲染内部.
  覆盖: M4-D002.
- TS-003 (run 错误映射): fake 对 run 返回错误对象.
  测试用例: TC-006 — COLLECTION_NOT_FOUND → exit 4 + stderr 错误 + candidates; TC-007 — UNRESOLVED_VARIABLES → exit 2 无事件流; TC-008 — SERVICE_ERROR → exit 3.
  先写的失败测试: `test_run_not_found_exit_4` — 预期失败: 未映射 run 侧错误.
  最小绿色实现范围: 复用 ISSUE-02 的服务端错误映射于 run.
  不得测试: 服务端成因.
  覆盖: M4-D004 (沿用).
- TS-004 (history list/show, fake HTTP):
  接缝: fake 对 `GET /history` 回列表、`GET /history/{id}` 回单条.
  测试用例: TC-009 — `history list` 默认单 JSON 输出 (数组), 条目字段含 id/item_ref/status/started_at/duration_ms; TC-010 — `history show <id>` 输出单 JSON 对象; TC-011 — 不存在的 id → 404 → exit 4 + stderr.
  先写的失败测试: `test_history_list_renders_json_array` — 预期失败: 未接 GET /history.
  最小绿色实现范围: 两个 history handler + GET 调用 + 单对象渲染 + 404 映射.
  不得测试: 历史落盘逻辑.
  覆盖: M4-D002, M3-D010.

## 验证入口
- `uv run pytest tests/api_client_cli/test_run.py tests/api_client_cli/test_history.py` — 全绿.
- 真实端到端 (待 08, 标人工/HITL): `uv run apic run <c> --env <e>` 打 testbed 3 条目集合 → 每条目 meta/chunk/done + summary, 失败条目只需从 run 输出取其 chunk 响应体 (不重放 send); exit 1 当有失败; `uv run apic history list` / `show <id>` 可见刚执行记录.

## 风险提示
- run 吞 chunk 是 M4 首轮 dogfood 最大不一致 (D003), TS-001 必须钉死.
- /collections/{x}/run 请求体 env/vars 与 /history 列表端点语义为 08 协调点; 不符报父会话, 不擅自改 08.
- history 为 08 Store 派生数据, CLI 只读查询渲染, 不落不聚合.

## 停止条件
- 需改变 M4 事件/输出契约、summary 字段, 或 run/history 消费契约与 08 无法协调时停止.

## 适合 AFK 的原因
- run/send 同构事件流、summary 统计、history 查询渲染全由 M4 原型与账本钉死, 无待定产品决策; 真端到端标人工验证.

## 验收标准
- [ ] run 每个条目完整 meta/chunk/done (不吞 chunk) + summary, 三形态渲染, failed>0 → exit 1.
- [ ] run 输出可直接定位失败条目响应体 (无需重放 send).
- [ ] history list/show 默认单 JSON 渲染, 404 → exit 4 + stderr.

## 被阻塞于
- ISSUE-02 (事件渲染原语 / 错误映射 / send 消费面)
