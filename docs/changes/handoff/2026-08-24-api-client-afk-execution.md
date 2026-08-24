# 交接 — api-client AFK 执行段 (MILESTONE-08/09/10)

日期: 2026-08-24 · 项目根: `/var/mnt/DATA/Workspace/requests`

## 下一会话用途

逐个关闭 AFK Milestone 直到 HITL 停下: MILESTONE-08 (后端核心) → MILESTONE-09 (SPA) 与 MILESTONE-10 (CLI) 并行 → 遇 MILESTONE-11 (成品验收, HITL) 停止. 遍历流程按 probe skill 的「遍历 Roadmap」七步; 编码任务走 tdd-as-orchestra skill; 每轮结束停下等用户提示.

## 现状

- Roadmap 已关闭: 01/02/03/04/05/06/07/12. 前沿: 仅 MILESTONE-08 (阻塞者 03/06 已关闭).
- 三个 AFK Milestone 的 Execution Spec 已固化并提交 (7f18dc3):
  - `docs/changes/api-client/milestone-08/EXECUTION.md` + 7 issues (01 服务骨架/launch/安全 → 02 Store+CRUD → 03 Resolve+Engine+send → 04 Assert → 05 Runner; 02→06 Sync; 01→07 dist 托管)
  - `docs/changes/api-client/milestone-09/EXECUTION.md` + 5 issues (链式 01→05)
  - `docs/changes/api-client/milestone-10/EXECUTION.md` + 4 issues (01→02→03/04)
- 已有代码: `src/testbed/` 测试后端 (62 测试全绿, Engine/Runner 的测试靶子); 核心产品代码未开始.

## 关键协调点 (执行 08/10 时须裁决, 来自 MILESTONE-10 worker 报告)

1. `/execute` 与 `/collections/{x}/run` 请求体中 env/vars 字段形状 — 08 与 10 须一致, 以 08 实现为准, 10 对齐.
2. 服务端错误响应格式 (10 的 candidates 纠错依赖) — 同上.
3. `/history` 列表端点形状.
4. `apic` script 归属: pyproject `[project.scripts]` 现指向占位; 10 的方案 = `apic` 指 CLI, serve/stop 转发保留.
5. 目录约定已统一: SPA 源码 `spa/src/`, 构建产物 `spa/dist/` 入库, FastAPI 托管 `spa/dist/`; 后端服务壳模块 `src/api_client/web/`.

## 必读推荐

- `docs/changes/api-client/roadmap/ROADMAP.md` — 目的地/前沿/阻塞图/笔记; 遍历入口.
- 三份 EXECUTION.md + issues/ — 执行的唯一任务书; issue 模板内含 TDD 切片与验证入口.
- `docs/changes/api-client/milestone-03/DECISIONS.md` — 架构权威 (D001-D014); 与代码冲突时先停下报用户, 不擅自改决策.
- `docs/changes/api-client/prototypes/assertion-dsl/dsl.py` — Assert 模块重写参照 (MILESTONE-08 ISSUE-04).
- `docs/changes/api-client/prototypes/spa-ui/2026-08-23-spa-ui-variants.html` — SPA 视觉/交互唯一权威 (变体 B).
- `docs/changes/api-client/prototypes/cli-shell/` — CLI 命令面定稿 (apic.py + DOGFOOD*.md).
- `docs/language/UBIQUITOUS_LANGUAGE.md` — 术语表; 代码/文档用词须一致.
- `docs/changes/api-client/milestone-10/EXECUTION.md` 风险节 — 上述协调点的完整清单.

## 路线图 (脉络还原)

1. 空仓库起步, probe 绘制 Roadmap: 目的地 = 自用本地优先 Postman 替代品, Python 后端为本体, SPA 供人 + CLI 供 AI, 数据=本地文件 git 管理, `uv run` 即起.
2. 方向侦查四选一: A 全自研 SPA (Vue3) + C 复用组装后端入选; B htmx / D 二开 Hoppscotch 排除.
3. 决策链: M1 范围 (HTTP only, 砍 JS 脚本) → M2 数据格式 (每请求一 YAML) → M3 后端架构 (瘦 CLI+常驻服务, 六模块, 安全五件套) → M4 CLI 原型 → M6 断言 DSL (双形态: 结构化+Python 逃生舱, ADR 0006) → M5 SPA 原型 (双栏纵向流, 单同步按钮, 日志不脱敏) → M12 测试后端.
4. 当前位置: 全部决策/原型完成, Execution Spec 就绪, 进入纯执行段.
5. 剩余: 08/09/10 实现 → 11 HITL 验收 (uv run 即起 + SPA 真实工作流 + agent 真实调 CLI + git 同步跑通) = 目的地.
6. 迷雾两项 (不影响本段): 实时协议二期 (WS/SSE 转发, 触发条件未到); AI 高阶能力 (MILESTONE-10 关闭后回访).
