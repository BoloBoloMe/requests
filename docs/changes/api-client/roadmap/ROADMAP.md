# 自用 API 调试与测试工具 (Postman 替代品)

## 目的地

一个可被日常使用的成品: 自用, 本地优先的 Postman 替代品. Python 后端承载全部核心功能, 两个外壳: SPA 供人, CLI 供 AI. 数据为本地文件, git 管理, 可绑定远端仓库 (SPA 提供 git 同步入口, CLI 不接管 git); 无账号无云, 任何有 uv 的设备 `uv run` 即起. Roadmap 清空时, 成品已在用户设备上服役.

## 笔记

- 领域: API 开发/测试工具; 空仓库起步, 无既有领域文档.
- 遍历时会用到的 skill: deliberate, prototype, tdd-as-orchestra (AFK 编码任务), adaptive-presentation.
- 固定偏好: 中文; 电报文回复; 半角标点; uv 管理 Python; 用户偏好 Web 应用, 拒绝 TUI/CLI 作为人的界面 (CLI 仅供 AI 使用); 厌恶臃肿/账号/云 (弃用 Postman 的根因).
- 方向侦查结论 (完整报告在 `../directions/`):
  - **被选 A — 全自研 SPA (Vue3)** ([direction-a-spa](../directions/direction-a-spa.md)): 四个开源先例验证; 核心组件全有成熟库 (CodeMirror 6/拖拽/JSON 树), 自研面 30-50%; node 仅是构建期依赖, 产物为静态文件, 运行时仍 `uv run` 即起; MVP 量级 6-10 开发周.
  - **被选 C — 复用组装后端** ([direction-c-reuse](../directions/direction-c-reuse.md)): httpx + jsonschema + jmespath + pytest (CI 宿主, subprocess + JUnit); 后端复用度 60-70%; 自研面 = 数据模型/断言 DSL/runner/Web 壳; Postman JS 脚本无法执行, 侦查建议砍掉 (待 MILESTONE-01 确认).
  - **排除 B — htmx 轻量 SSR** ([direction-b-ssr](../directions/direction-b-ssr.md)): 无 API 客户端先例; 交互岛边界失控则复杂度反超 SPA (Gumroad 教训); 探路成本高于自用收益.
  - **排除 D — 二开 Hoppscotch** ([direction-d-fork](../directions/direction-d-fork.md)): CE 三容器 + Postgres 违背反臃肿痛点; Python 浓度低 (断言/runner 全是 JS/Node). 可借鉴: 可插拔 interceptor 执行层架构. 过渡方案 (先用 Hoppscotch 顶着) 亦被否决: 即用即弃的臃肿不值得.
- 既定约束 (用户拍板): 数据 = 本地文件 + git 管理, SPA 提供 git 绑定/同步入口, CLI 不接管 git; 后端是产品本体, SPA/CLI 皆为外壳.
- 领域文档已初始化: [领域语言](../../../language/UBIQUITOUS_LANGUAGE.md); ADR 目录 `docs/adr/`; 各 Milestone 决策账本在 `../milestone-NN/DECISIONS.md`.

## 已关闭决策

- [MILESTONE-01](MILESTONE-01.md) — v1 范围界定: HTTP/REST only + SSE 流式渲染; 认证五种 + 砍 oauth2 交互流程; 零导入 (hurl 走一次性外挂脚本); 砍 JS 脚本 (结构化断言 DSL); 两级变量 + 白名单动态变量 $now/$uuid; 测试后端随仓库. 产物: [DECISIONS.md](../milestone-01/DECISIONS.md), ADR [0001](../../../adr/0001-refuse-node-runtime-drop-postman-js-scripts.md)/[0002](../../../adr/0002-zero-importers-one-off-migration-script.md), [领域语言](../../../language/UBIQUITOUS_LANGUAGE.md)
- [MILESTONE-07](MILESTONE-07.md) — 实时协议流式转发调研: 激活条件未满足 (MILESTONE-01 砍 WS/gRPC, SSE 仅保留响应查看器流式渲染), 考察点并入未决迷雾 "实时协议二期形状"
- [MILESTONE-02](MILESTONE-02.md) — 数据存储与集合格式: 每请求一 YAML 文件 (version 字段, YAML 子集), 数据仓库布局 (collections/environments/files/.local), frontmatter seq 排序, 集合一级默认继承, 环境进 git + secrets gitignored, 文本传输历史 append 落盘. 产物: [DECISIONS.md](../milestone-02/DECISIONS.md), [ADR 0003](../../../adr/0003-yaml-per-request-format.md)
- [MILESTONE-03](MILESTONE-03.md) — 后端核心架构: CLI 瘦客户端 + 幂等拉起常驻服务 (launch 模块共享), 执行引擎内嵌服务进程 (async httpx, 无独立代理), SSE/JSONL 单一事件流, 六模块边界 (Store/Resolve/Engine/Assert/Runner/Sync), REST+RPC 混合 API, 本地安全五件套 (绑回环/Host 白名单/禁 CORS/启动 token/CSP), dist 入库, v1 仅 POSIX. 产物: [DECISIONS.md](../milestone-03/DECISIONS.md), [RESEARCH-local-security.md](../milestone-03/RESEARCH-local-security.md), ADR [0004](../../../adr/0004-thin-cli-service-convergence.md)/[0005](../../../adr/0005-commit-spa-dist.md), [领域语言](../../../language/UBIQUITOUS_LANGUAGE.md)
- [MILESTONE-04](MILESTONE-04.md) — AI CLI 外壳原型: 三轮 LLM dogfood 收敛; 命令面 = 动作动词 (send/run) + 资源名词组 (collection/item/env/history/service) + 元命令 (schema/guide); 流式 NDJSON/非流式 JSON/pretty; send/run 同构事件流 (meta/chunk/done/summary); 退出码 0-4 + 细分错误码带 candidates 纠错; 双通道可发现性; 未解析变量硬失败. 产物: [DECISIONS.md](../milestone-04/DECISIONS.md), [原型归档](../prototypes/cli-shell/)
- [MILESTONE-12](MILESTONE-12.md) — 自研测试后端 `testbed`: FastAPI+uvicorn 同栈, 8 ISSUE 全绿 (62 测试); echo/things CRUD/auth×4 (含手搓 RFC 7616 digest)/SSE/dynamic 校验/边界端点; `uv run testbed` 可起. 产物: [EXECUTION.md](../milestone-12/EXECUTION.md), `src/testbed/`, `tests/testbed/`, [README](../../../src/testbed/README.md)

- [MILESTONE-06](MILESTONE-06.md) — 断言 DSL 原型: 双形态拍板 — 结构化 DSL (target+op+expect / jsonschema) 为主 + Python 逃生舱 (exec 注入 response, 无沙箱); YAML 序列化, python 代码用块标量; 非 JSON 体降级裸文本 contains/matches; 已知缺口 (数组长度/浮点容差) 全由逃生舱覆盖. 产物: [DECISIONS.md](../milestone-06/DECISIONS.md), ADR [0006](../../../adr/0006-assertion-dsl-with-python-escape-hatch.md), [原型归档](../prototypes/assertion-dsl/)

- [MILESTONE-05](MILESTONE-05.md) — SPA 界面原型: 双栏纵向流胜出 (左树+git 行 | 上请求下响应); git 极简为单「同步」按钮; 响应查看器三 tab 含完整收发日志; 日志/历史落盘不脱敏 secrets; runner 内联树徽标; 浅色低饱和基调. 产物: [DECISIONS.md](../milestone-05/DECISIONS.md), [原型归档](../prototypes/spa-ui/2026-08-23-spa-ui-variants.html)

## 前沿

- [MILESTONE-08](MILESTONE-08.md) — `task` — 后端核心实现 (03, 06 均已关闭, 解锁)

## 未决迷雾

- 实时协议二期形状 — WS/SSE/gRPC 完整支持长什么样; 并入 MILESTONE-07 考察点: 后端代理转发方案 (取消/重连/缓冲语义), 前端流式渲染与转发端口, 大流渲染性能. 回访触发条件 (D002): 首次需调试 SSE 端点且 curl/现有能力不够用达两次以上 → 立项.
- AI 高阶能力 — AI 生成集合/断言, OpenAPI 自动转集合等; 粒度太粗, MILESTONE-04 已关闭 (CLI 命令面已定) 但仍不足立项, 回访触发改为 MILESTONE-10 (CLI 实现) 关闭后. OpenAPI 转集合回访优先级已降低 (ADR 0002: 集合预期从业务现场手建).

## 范围外

- 团队协作/账号/云同步 — 痛点反面, 自用无此需求; git 同步走用户自己的仓库, 不在此项.
- Mock server/文档生成/监控 — 目的地界定为调试 + 自动化测试.
- TUI/桌面 GUI — 用户已明确排除.
- 对外分发/商业化 — 自用.

## 阻塞关系

```text
03 ──► 04 (均已关闭)
05 (已关闭)
06 (已关闭)
12 (已关闭; 为 08/09/10 提供测试靶子)
03, 06 ──► 08 (阻塞者均已关闭, 08 已解锁)
05, 08 ──► 09 (05 已关闭, 仍阻塞于 08)
04, 08 ──► 10 (04 已关闭, 仍阻塞于 08)
09, 10 ──► 11 ──► 目的地
```
