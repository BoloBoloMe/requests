# CLI 实现 (AI 外壳) (MILESTONE-10) Execution Spec

## 权威输入
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-10.md` (AI 外壳全量实现, AFK 编码任务, 走 tdd-as-orchestra; 验收含真实 agent 调用场景)
- 命令面决策 (核心信源): `docs/changes/api-client/milestone-04/DECISIONS.md` (D001-D006, M4)
- 架构决策: `docs/changes/api-client/milestone-03/DECISIONS.md` (D001/D002/D005/D007/D010/D011/D012/D013/D014, 记作 M3-Dxxx)
- 定稿原型 (命令面/输出/错误模型以此为准, 重写不直接复用): `docs/changes/api-client/prototypes/cli-shell/` (README.md 三轮修正 + apic.py + 四份 DOGFOOD*.md)
- 后端契约/包结构 (并行实现, 只读不改): `docs/changes/api-client/milestone-08/EXECUTION.md` 及 `issues/` (launch 模块 API, /execute, /collections/{x}/run, 资源 REST 端点形状)
- 术语: `docs/language/UBIQUITOUS_LANGUAGE.md`

## 全局允许范围
- 新建 `src/api_client_cli/` (全部 CLI 代码: 入口/argparse 树/服务 client/输出渲染/错误映射/schema-guide 契约), `tests/api_client_cli/` (fake HTTP 服务 + launch 矩阵).
- 修改 `pyproject.toml`: [project.scripts] 将 `apic` 指向 `api_client_cli.__main__:main` (08 临时把 apic 指向 api_client.__main__ serve/stop, 本里程碑由 CLI 承接完整 `apic` 程序, 行为兼容); hatch packages 增 `src/api_client_cli`; pytest testpaths 增 `tests/api_client_cli`. 复用既有依赖 fastapi/uvicorn/httpx/pytest, 不新增第三方依赖 (difflib/stdlib 即可).
- CLI 唯一允许 import 核心库的模块是共享 `api_client.launch` (M3-D002 唯一例外), 用于 ensure_running/stop/token/读 service.json.

## 全局禁止范围
- CLI 不含任何业务逻辑: 不 import 核心库其余模块 (M3-D001), 不自己做变量解析/断言求值/执行 — 全部交给服务, 服务是唯一执行与安全边界. UNRESOLVED_VARIABLES / NOT_FOUND / 断言结果一律以服务端响应为准, 客户端只做参数解析/输出渲染/错误映射.
- 不接管 git (ROADMAP 范围外; 无 git/sync 子命令).
- 不做 TUI/交互式界面 (纯命令行, 供 AI subprocess 调用; 无 REPL/提示符/ANSI 交互).
- 不修改 `src/testbed/`, `tests/testbed/` (M12 产物), 不修改 `src/api_client/` 与 `tests/api_client/` 任何文件 (MILESTONE-08 产物) 及其所属文档.
- 不改任何 DECISIONS/ADR; 不扩大任一 issue 边界.
- 不做 Windows 支持 (M3-D012, flock/pid164 语义按 POSIX).

## 完成定义
- `uv run pytest` 全绿: 存量 `tests/testbed` (62) + `tests/api_client` (08) + 新增 `tests/api_client_cli`; 每个 issue 验收标准逐条可观察.
- `apic` CLI 命令面完整可用: send/run/collection/item/env/history/service/schema/guide, 全局 `--output` 三形态, 退出码 0-4, 错误走 stderr `{"error":{code,message,details}}`, stdout 保持干净.
- CLI 连服务执行真实请求 (打 MILESTONE-12 测试后端作靶子): send 一条 → meta/chunk/done 事件流; run 一集合 → summary; 断言失败 → exit 1.
- 真实 agent 调用场景: 以全新上下文 agent 仅经 `--help` 与经 `schema`+`guide` 各完成一组任务 (可标人工验证/HITL), 对标 DOGFOOD 自学习任务集.

## 测试策略
按 M3-D014:
1. 参数解析与输出渲染: CLI 以 subprocess 调 `apic` 打 **fake HTTP 服务** (本地 socket 起假服务, 回放 canned 路由), D014-4 指定此测法. 断言 stdout 逐行/JSON 形态, stderr 错误对象, 退出码.
2. launch 接入/矩阵 (D014-5): 双 CLI 并发拉起同一 data-dir → 单服务 + 一致 (port,token); stale service.json / 请求级重试一次 (D011-4); 依赖 08 已交付的 launch 与真服务.
3. schema/guide/help 一致性: 单测断言 schema 事件字段/退出码/错误码与实现侧单一常量源逐字一致 (M4-D005 对 dogfood 扣分项的硬要求).
4. 真实端到端 (打 testbed): 待 08 交付后, send/run/认证/SSE 真实往返, 验收含 agent 场景, 可标人工验证.

## 任务图
- ISSUE-01: `issues/ISSUE-01-cli-skeleton-launch.md`; 覆盖: M3-D001/D002/D005/D011/D014-5, M4-D001 骨架; 依赖: 无 (逻辑上待 08 交付 launch, 见风险).
- ISSUE-02: `issues/ISSUE-02-send-single-request.md`; 覆盖: M4-D002/D003/D004/D006, M3-D010/D007; 依赖: ISSUE-01.
- ISSUE-03: `issues/ISSUE-03-run-history.md`; 覆盖: M4-D002/D003, M3-D010/D013; 依赖: ISSUE-02.
- ISSUE-04: `issues/ISSUE-04-resource-meta.md`; 覆盖: M4-D001/D002/D005, M3-D010; 依赖: ISSUE-02.

## 覆盖矩阵
- M3-D001 (CLI 纯 API client, 仅 launch 例外) -> ISSUE-01 -> TS-001/TS-002 -> `uv run pytest tests/api_client_cli/`
- M3-D002 (launch 共享) -> ISSUE-01 -> TS-002 -> 同上
- M3-D005 (token 子命令) -> ISSUE-01 -> TS-003 -> `uv run pytest tests/api_client_cli/test_service.py`
- M3-D011 (服务发现/生命周期/请求级重试一次) -> ISSUE-01 -> TS-002/TS-004 -> `tests/api_client_cli/test_launch_matrix.py`
- M3-D014-4 (CLI 用 fake HTTP) -> 全部 ISSUE -> 各 TS 一律 fake HTTP 服务 -> 同上
- M3-D014-5 (launch 矩阵, 双 CLI 并发拉起) -> ISSUE-01 -> TS-004 -> `tests/api_client_cli/test_launch_matrix.py`
- M3-D010 (REST+RPC 消费面) -> ISSUE-02/03/04 -> 各 TS -> 同上
- M3-D013 (runner 顺序执行) -> ISSUE-03 -> TS-001 -> `tests/api_client_cli/test_run.py`
- M4-D001 (命令面: 动作动词+资源名词组+元命令) -> ISSUE-01/04 -> TS -> 同上
- M4-D002 (输出契约 NDJSON/JSON/pretty) -> ISSUE-02/03/04 -> TS -> 同上
- M4-D003 (send/run 同构事件流 + summary, 不吞 chunk) -> ISSUE-02/03 -> TS -> `tests/api_client_cli/test_send.py test_run.py`
- M4-D004 (退出码 0-4 + 细分错误码 + candidates 纠错) -> ISSUE-02/03 -> TS -> `tests/api_client_cli/test_errors.py`
- M4-D005 (双通道可发现性 schema/guide + help 契约一致) -> ISSUE-04 -> TS -> `tests/api_client_cli/test_contract.py`
- M4-D006 (未解析变量硬失败, 无事件流) -> ISSUE-02 -> TS-006 -> `tests/api_client_cli/test_errors.py`

## 全局风险和停止条件
- 需要改变任一 DECISIONS/ADR/任务定义 (命令面/输出/错误模型), 或扩大允许范围/触碰禁止范围时停止并回报.
- CLI 消费契约与 08 服务不符时停止: /execute 与 /collections/{x}/run 请求体须能携带 env 与 vars(CLI 的 --env/--var 依赖), 服务错误须以 `{"error":{code,message,details}}` 返回(未解析变量/not-found/服务错误需能区分). 08 是并行实现, 不得修改其文件; 若契约缺口需由 08 补, 报父会话 HITL 协调, 不擅自改 08.
- candidates 计算归属: 优先透传服务端 error.details.candidates; 08 当前 CRUD/执行未声明确返回 candidates, CLI 在 ISSUE-02 以客户端 difflib+子串实现纠错兜底 (错误恢复/展示, 非业务执行逻辑), 并对齐 M4-D004/dogfood 要求.
- `apic` console script 归属: 08 临时把 apic 指向 api_client.__main__ (serve/stop). 本里程碑 ISSUE-01 将 apic 改指 CLI, 并保留 serve/stop 转发到 api_client.launch, 使 08 的 `uv run apic serve` 路径不失效; 若归属冲突需协调报父会话.
- 测试靶子 `tests/api_client_cli` 的 launch 矩阵依赖 08 已交付的真 launch+服务; 在 08 未交付前该子项标记为待 08 预置.

## 备注 (08 协调约定, 只读依据)
- 包结构: 08 用 `src/api_client/` (核心库+launch+服务壳), CLI 用 `src/api_client_cli/`; 共享面只有 `api_client.launch` (M3-D002 唯一例外).
- launch 公开 API (08 ISSUE-01 钉死): `launch.ensure_running(data_dir) -> ServiceInfo(port, token, ...)`, 内含 flock/pid 存活/有限重试/ready 判定; CLI 复用之.
- API 地面 (08 EXECUTION.md): `POST /execute` (协商 SSE/NDJSON), `POST /collections/{c}/run`, 资源 CRUD `/collections/...` `/environments/...` `/history/...` `/state`, `GET /health`; token 经 `X-Auth-Token` header.
- 事件模型字段 (M4-D003, 08 ISSUE-03/05 沿用): meta(type,timestamp,item_ref,item,method,resolved_url,env) / chunk(type,timestamp,item,index,data) / done(type,timestamp,item,status,duration_ms,assertions) / summary(type,timestamp,total,passed,failed,items); run 末尾附 report 事件 (JUnit).
