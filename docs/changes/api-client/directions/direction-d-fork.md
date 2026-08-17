# Research: 二开/嵌入现有开源 API 客户端 (自用 Postman 替代品: 浏览器 UI + Python 后端代理执行)

## Summary

存在低成本可行路径: **Hoppscotch (MIT, monorepo 全开源) 是唯一真正契合"浏览器 UI + 自研 Python 执行后端"的候选**. 其前端执行层是可插拔的 KernelInterceptor 抽象, 官方就支持把请求路由到自定义代理 (Proxyscotch 协议, MIT, Go 实现可参考), 因此最低成本方案甚至不用 fork: 自托管 CE + 把前端 Proxy URL 指向自研 Python 代理即可; fork 加自定义 interceptor 也只需薄改动. Bruno/Insomnia/Yaak 均为纯桌面 (Electron/Tauri), 无浏览器版, 二开成 web + Python 后端需重构执行层与存储层, 成本远高于 Hoppscotch, 不推荐.

## Findings

### 1. Hoppscotch — 许可证 MIT, 前后端全开源, 有可插拔执行层 (最佳候选)
- 许可证: 主仓库 MIT (LICENSE 头), CE 自托管免费开源; EE (open-core, SAML/审计等) 闭源收费. 自用完全用 CE 即可.
- 架构: pnpm monorepo, 前端 = Vue 3.5 + Vite + CodeMirror/Monaco (`packages/hoppscotch-common` + `hoppscotch-selfhost-web`); 后端 = NestJS 11 + Apollo GraphQL + Prisma/Postgres (`packages/hoppscotch-backend` 就在 monorepo 内, MIT); 另有 admin dashboard (`hoppscotch-sh-admin`), desktop (Tauri), agent (Tauri 本地代理), CLI (Node, isolated-vm 沙箱).
- 自托管: docker compose 三容器 (frontend:3000, backend:3170, admin:3100) + Postgres, 或 AIO 容器 `hoppscotch/hoppscotch`; 支持 Helm.
- 执行层可替换的证据: 前端所有请求经 `KernelInterceptorService` 分派, 接口为 `execute(RelayRequest) -> RelayResponse` (见 `packages/hoppscotch-common/src/services/kernel-interceptor.service.ts`); 官方 interceptor = 浏览器直发 (受 CORS 限制), Proxyscotch 代理, 本地 Agent, 浏览器扩展. 文档明确: "You can replace the default Proxy URL with your own proxy middleware".
- 绕 CORS 的官方推荐 = Desktop App 或 Proxy/扩展; web 版默认直发必遇 CORS — 这与本项目"Python 后端代理执行"的需求天然互补.
- 成本估计: (a) 零 fork 方案: 前端设置 Proxy URL 指向自研 Python 服务, 需实现 proxyscotch 兼容协议 (参考 `hoppscotch/proxyscotch`, Go, MIT) — POC 约 1-2 天; (b) fork 方案: 实现自定义 KernelInterceptor (TS) 直连 Python 后端 API — 改动面约 1 个 interceptor 文件 + 设置项, 3-5 天.
- [Source: 仓库](https://github.com/hoppscotch/hoppscotch), [自托管文档](https://docs.hoppscotch.io/documentation/self-host/getting-started), [CE 安装](https://docs.hoppscotch.io/documentation/self-host/community-edition/install-and-build), [Interceptor 文档](https://docs.hoppscotch.io/documentation/features/interceptor.md), [CORS 排查](https://docs.hoppscotch.io/documentation/getting-started/troubleshooting.md), [kernel-interceptor.service.ts](https://github.com/hoppscotch/hoppscotch/blob/main/packages/hoppscotch-common/src/services/kernel-interceptor.service.ts), [Proxyscotch](https://github.com/hoppscotch/proxyscotch)

### 2. Hoppscotch — 自动化测试/集合运行能力齐全
- Tests: 请求级 JS 断言脚本 + pre-request 脚本 (`@hoppscotch/js-sandbox` 沙箱执行), 断言失败可标记请求失败.
- Runner: 集合顺序运行, 可配 delay / stop-on-error / persist responses / keep variables, 实时结果视图 (每请求状态码 + 测试通过/失败明细).
- CLI `hopp test`: 本地集合文件或连自托管实例的集合 ID, 支持环境文件、JUnit 报告 (CI 可用); CLI 目前 alpha, 要求 Node >= 22.
- [Source: Scripts](https://docs.hoppscotch.io/documentation/features/scripts.md), [Runner](https://docs.hoppscotch.io/documentation/features/runner.md), [CLI](https://docs.hoppscotch.io/documentation/clients/cli/overview.md)

### 3. Bruno — MIT, Electron 纯桌面, 无 web 版 (方向不匹配)
- 许可证: MIT (Anoop M D 等).
- 架构: Electron 37 + React monorepo (`bruno-app`, `bruno-electron`, `bruno-cli`, `bruno-common`, `bruno-js`, `bruno-lang`, `bruno-sqlite` 等); 集合 = 本地文件夹 Bru 文本格式, Git 协作; 官方 FAQ 确认: 无账号, 无云组件, 离线优先.
- web 模式: 无官方浏览器版, 只有桌面二进制 (Mac/Win/Linux); 二开成 web 需把本地 fs 访问与本地执行层改成后端 API, 属于重构而非薄改造.
- 自动化测试: 有 — 请求内 JS 断言, UI 集合运行, CLI `bru run` (Safe/Developer 沙箱模式, JSON/JUnit/HTML 报告, CI 集成). V4 刚发布, 含 secrets/env 持久化/WebSocket/JUnit 破坏性变更.
- 与 Python 后端结合: 只能 fork 整个 Electron 应用大改, 或只复用 CLI 测试引擎 (Node) — 均偏离"浏览器 UI + Python 后端"目标.
- [Source: 仓库 README](https://github.com/usebruno/bruno), [官网 FAQ](https://www.usebruno.com/), [CLI 文档](https://docs.usebruno.com/bru-cli/overview), [V4 发布说明](https://www.usebruno.com/v4-release)

### 4. Insomnia / Yaak — 快速扫描, 均不推荐
- **Insomnia** (Kong): Apache-2.0, Electron + React monorepo, repo 活跃 (2026-08 仍有推送, 39.9k stars). 存储 = Local Vault / Git Sync / Cloud Sync (云需免费账户, 本地 Vault 无云); 无自托管后端, 无浏览器版; 测试能力有 (原生测试套件 + collection runner + Inso CLI lint/test). 二开为 web + Python 后端 = 同 Bruno 的桌面重构成本.
- **Yaak**: MIT, Tauri 2 + Rust + React, 纯桌面, 离线优先, 无遥测; 主作者单人 (gschier), 贡献只收 bug fix; 无官方 CLI, 无测试断言体系 (只有 template tags/plugins/JSONPath 检查响应). 二开价值最低.
- [Source: Insomnia README](https://github.com/Kong/insomnia), [Yaak README](https://github.com/yaakapp/yaak), [Yaak LICENSE](https://github.com/yaakapp/yaak/blob/main/LICENSE)

### 5. 结论 — 推荐路线与风险
- 可行路径 (按成本升序):
  1. 零 fork: 自托管 Hoppscotch CE (docker compose) + 前端 Proxy 指向自研 Python 执行服务, 实现 proxyscotch 兼容协议. 自用单用户, 集合同步/执行全走本地.
  2. 薄 fork: fork 前端, 注册自定义 KernelInterceptor 直连 Python 后端 (可同时去掉浏览器直发路径, 统一执行入口); 集合存储仍用 CE backend 或改本地.
  3. 不推荐: Bruno/Insomnia/Yaak 桌面改造 (重构级成本), 或自研全部 UI (与本方向前提相悖).
- 许可证风险: Hoppscotch CE / Bruno / Yaak = MIT, Insomnia = Apache-2.0, 全部宽松无 copyleft; 自用不分发, 风险可忽略. 注意点: (a) Hoppscotch EE 为 open-core 闭源, 只碰 CE; (b) "Hoppscotch"/"Bruno" 商标属原作者, 自用/本地 fork 无碍, 勿对外以官方名义发布; (c) 主仓库 npm 依赖各带自有许可证, 不涉及分发即不触发义务.
- 长期维护: Hoppscotch 季度发布、6k+ commits、80k stars, 前端 API (kernel/relay 抽象) 处于演进中, 追上游需持续小成本 rebase; 自用单用户建议**冻结分叉于某稳定版** (MIT 无更新义务), 或只维护薄改动层 (自定义 interceptor + 配置), 升级冲突面可控制在个位数文件. 结论: 追上游 vs 冻结, 对自用场景冻结分叉 + 按需手动拉取安全修复更划算; 若选薄改动层, 追上游也现实.

## Sources

- Kept:
  - Hoppscotch 仓库 (github.com/hoppscotch/hoppscotch) — MIT 主仓库, monorepo 结构, packages 清单, 一手来源
  - Hoppscotch Self-Host 文档 (docs.hoppscotch.io/documentation/self-host/getting-started) — CE/EE 对比, MIT 声明
  - Hoppscotch CE install-and-build (docs.hoppscotch.io/documentation/self-host/community-edition/install-and-build.md) — 三容器自托管组件与端口
  - Hoppscotch Interceptor 文档 (docs.hoppscotch.io/documentation/features/interceptor.md) — Agent/Proxyscotch/自定义 proxy URL, 关键可行性证据
  - Hoppscotch Troubleshooting (docs.hoppscotch.io/documentation/getting-started/troubleshooting.md) — web 版 CORS 限制与解法
  - Hoppscotch kernel-interceptor.service.ts (github raw) — KernelInterceptor 接口定义, 执行层可插拔证据
  - Hoppscotch network.ts / RequestRunner.ts (github raw) — 前端执行核心与分派流程
  - Hoppscotch CLI 文档 (docs.hoppscotch.io/documentation/clients/cli/overview.md) — hopp test, JUnit, Node 要求
  - Hoppscotch Runner 文档 (docs.hoppscotch.io/documentation/features/runner.md) — 集合顺序运行能力
  - Proxyscotch (github.com/hoppscotch/proxyscotch) — MIT 代理, 协议参考实现
  - Bruno 仓库 README + license.md (raw.githubusercontent) — MIT, 离线优先, CLI/Docker
  - Bruno 官网 FAQ (usebruno.com JSON-LD) — 无账号无云离线客户端确认
  - Bruno CLI 文档 (docs.usebruno.com/bru-cli/overview) — 报告格式, Safe Mode
  - Bruno V4 发布说明 (usebruno.com/v4-release) — 活跃开发证据
  - Insomnia README + repo 元数据 (raw + GitHub API) — Apache-2.0, Electron, Inso CLI, 活跃度
  - Yaak README + LICENSE (raw) — MIT, Tauri/Rust, 单人维护, 无 CLI
- Dropped:
  - 多个 SEO/聚合站 (openapps.pro, opentechhub.io, YouTube 教程) — 二手信息且与官方文档重复
  - pkg.go.dev hoppscotch-backend — 过时 (后端已并入 monorepo, 该路径 404)
  - Reddit 讨论帖 — 观点非事实, 无权威性

## Gaps

1. Proxyscotch 的请求/响应 wire 协议字段细节未深读 (需看 Go 源码或前端 Proxy interceptor 代码) — 影响零 fork 方案的精确定义, 但协议简单 (POST 请求体到 proxy, 返回响应体), POC 阶段可对照源码补齐.
2. Hoppscotch 2026 版 web 前端能否完全不依赖 backend (纯 localStorage 集合) 未验证 — 稳妥方案 (自托管 CE 全套) 已绕开此问题.
3. hoppscotch-kernel 的 worker/relay 抽象对自定义 interceptor 的运行时约束未深读 (RelayRequest 结构, 是否 worker 内执行) — fork 方案开发时需先读 kernel 包文档.
4. Insomnia 团队规模/商业化方向仅以 repo 活跃度验证, 未核实传闻 (不影响结论: 桌面架构本身已排除).
5. Bruno 二开成本为架构推断, 未做深度代码审计 (不影响结论: 无 web 版即不满足前提).