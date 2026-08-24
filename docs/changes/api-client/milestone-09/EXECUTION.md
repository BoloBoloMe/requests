# MILESTONE-09 SPA 实现 Execution Spec

## 权威输入

- Product/Task: [MILESTONE-09.md](../roadmap/MILESTONE-09.md) (AFK 编码任务, 走 tdd-as-orchestra), [ROADMAP.md](../roadmap/ROADMAP.md) (阻塞关系)
- Decisions (界面形态): [MILESTONE-05/DECISIONS.md](../milestone-05/DECISIONS.md) 决策 1-5
- Decisions (后端契约/安全/分发): [MILESTONE-03/DECISIONS.md](../milestone-03/DECISIONS.md) D003/D004/D007/D010/D013
- 高保真原型 (变体 B 为唯一权威): [prototypes/spa-ui/2026-08-23-spa-ui-variants.html](../prototypes/spa-ui/2026-08-23-spa-ui-variants.html)
- 组件选型侦查: [directions/direction-a-spa.md](../directions/direction-a-spa.md)
- 术语: [UBIQUITOUS_LANGUAGE.md](../../language/UBIQUITOUS_LANGUAGE.md)

## 全局允许范围

- 新建并修改 `spa/` 目录 (Vite + Vue3 + TypeScript 前端工程), 含其 `dist/` 构建产物 (入库, 见 D003).
- 新建 SPA 源码: `spa/src/api/` (HTTP client + token 注入接线 + SSE 消费), `spa/src/services/` (面向各领域的适配层, 可注入替换以便单测), `spa/src/components/` (UI 组件), `spa/src/stores/` 或等效状态模型, `spa/src/**/__tests__/` (vitest).
- 可配置 Vite build 输出路径 (默认 `spa/dist/`), 可编辑 SPA 自身 package.json/tsconfig/vitest 配置.
- 可修改本 milestone-09 目录下文档.
- 契约范围: 仅依据 M3-D010 (REST CRUD `/collections/...`,`/environments/...`,`/history/...` + RPC `POST /execute`,`POST /collections/{x}/run`,`POST /git/sync`) 与 M3-D007 (`/execute` 按 Accept 协商 SSE, 事件模型 meta/chunk/done); token 经 D003 页面注入 + D004 header token 携带 + SSE 握手 `?token=`.
- 组件选型: CodeMirror 6 (URL/JSON/Python 编辑), JSON 树 (vue-json-pretty), 拖拽排序 (vuedraggable / sortablejs), 均为 direction-a 侦查确认的成熟库及其同场景先例.

## 全局禁止范围

- 不引入路由级多页面 (单页, 无 vue-router 多路由; D-决策 1 双栏纵向流各面同屏).
- 不做账号/云/团队协作 (ROADMAP 范围外).
- 不用 react-json-view / Shoelace 及其继任 Web Awesome (direction-a 侦查为停更/sunset, 硬风险).
- 不自建拖拽库, 用侦查结论的成熟库.
- 不修改任何 Python 后端/服务/CLI/核心库代码 (属 MILESTONE-08 并行实现); SPA issues 不假设超出 D010+D007 的后端能力.
- 不在 SPA 内自行引入 CORS 放宽或关闭 token 校验 (D004 本地安全模型由后端强约束).
- 不新增 WebSocket / gRPC / oauth2 交互 (M1 范围).

## 完成定义

- `spa/` 下 `npm run build` 通过, 产物写入 `spa/dist/` 且入库.
- `npm run test:unit` (vitest) 全绿, 每个 ISSUE 至少一个可执行 TDD 切片先红后绿.
- 动态展示由 mock 服务层驱动自测通过; 真实后端 (FastAPI 托管 + `/execute` SSE) 集成冒烟标记为人工验证/HITL, 待 MILESTONE-08 交付后完成.
- 视觉以原型变体 B 为唯一权威: 浅色低饱和暖灰底 (`#f5f4f1` 系), 方法着色 (GET 绿/POST 黄/PUT 蓝/DEL 红), 无边框输入悬停显框, 等宽字体用于 URL/JSON/日志, git 单行 (`⎇ main ↑N` + 同步).

## 测试策略

- 前端组件/逻辑测试: vitest + @vue/test-utils + jsdom, 位于 `spa/src/**/__tests__/`.
- 后端不可用阶段: 经 `spa/src/services/` 注入 mock 传输 (fetch/EventSource 抽象) 完成单元与组件测试, 不 mock 私有实现.
- 可执行切片 (每 ISSUE ≥1): 见各 ISSUE 的 TDD 切片节, 命令 `cd spa && npm run test:unit -- <path>`.
- 无法自动化项明确标记: FastAPI 真实托管 (ISSUE-01), `/execute` 真实 SSE 端到端 (ISSUE-04), git 真实同步 (ISSUE-05) 均标记人工验证/HITL, 依赖 MILESTONE-08 后端.

## 任务图

- ISSUE-01: [issues/ISSUE-01-vue3-shell-dist.md](issues/ISSUE-01-vue3-shell-dist.md); 覆盖: SK-01 (工程骨架), SK-02 (api client+token), SK-03 (dist 托管); 依赖: 无.
- ISSUE-02: [issues/ISSUE-02-sidebar-tree-env-vars.md](issues/ISSUE-02-sidebar-tree-env-vars.md); 覆盖: SIDE-01 (集合树 CRUD/折叠/拖拽排序), SIDE-02 (环境胶囊下拉切换), SIDE-03 (集合变量编辑); 依赖: ISSUE-01.
- ISSUE-03: [issues/ISSUE-03-request-builder.md](issues/ISSUE-03-request-builder.md); 覆盖: REQ-01 (方法着色+URL 变量高亮+解析预览), REQ-02 (Params/Headers/Body/Auth 四 tab + kv 行交互), REQ-03 (断言 tab 结构化表单+Python 编辑框); 依赖: ISSUE-02.
- ISSUE-04: [issues/ISSUE-04-response-viewer-sse.md](issues/ISSUE-04-response-viewer-sse.md); 覆盖: RES-01 (头行状态+元信息+断言计数), RES-02 (Body JSON 树折叠/行号/着色), RES-03 (Headers), RES-04 (日志完整收发转录), RES-05 (SSE 流式消费); 依赖: ISSUE-03.
- ISSUE-05: [issues/ISSUE-05-runner-inline-git.md](issues/ISSUE-05-runner-inline-git.md); 覆盖: RUN-01 (文件夹运行三态徽标+失败红字明细+跳断言), RUN-02 (侧栏 git 单同步按钮+状态); 依赖: ISSUE-04.

## 覆盖矩阵

| 覆盖依据 | ISSUE | 验证入口 |
| --- | --- | --- |
| M3-D003 (dist 入库+token 注入+no-store) / SK-01..03 | ISSUE-01 | vitest + 人工: FastAPI 托管 |
| M3-D004 (CSP self, token header) / SK-02 | ISSUE-01 | vitest (token 携带/缺失拒绝) |
| M5-D1 (布局) / ISSUE-01 骨架 | ISSUE-01 | vitest (App 骨架) |
| M5-D1 (左树+环境+变量) / SIDE-01..03 | ISSUE-02 | vitest 组件测试 |
| M5-D3 (树折叠/拖拽/CRUD) / SIDE-01 | ISSUE-02 | vitest |
| M5-D3 (请求构建器五面) / REQ-01..03 | ISSUE-03 | vitest |
| M5-D3 (响应查看器三 tab) / RES-01..04 | ISSUE-04 | vitest |
| M3-D007 (SSE meta/chunk/done) / RES-05 | ISSUE-04 | vitest (解析器) + 人工: 真实 SSE |
| M5-D3 (runner 内联徽标) / RUN-01 | ISSUE-05 | vitest |
| M5-D2 (git 单同步) / RUN-02 | ISSUE-05 | vitest + 人工: 真实 git |
| M5-D4 (视觉基调) / 全部 | 各 ISSUE 组件 | vitest (类名断言) + 人工比照原型 |
| M5-D5 (日志不脱敏) / RES-04 | ISSUE-04 | vitest |
| M3-D013 (API 不版本化) / 全部 | 各 ISSUE | 无路径前缀, 复用于同 API |

## 全局风险和停止条件

- 需要改变 PRODUCT/TECHNICAL/DECISIONS (含 M5 决策 1-5, M3 相关决策) 时停止.
- 需要扩大允许范围或触碰禁止范围 (多页面/云/停更库/自建拖拽/改后端) 时停止.
- Spec 与代码事实冲突或无法提供完成证据 (如后端契约与 D010/D007 不符) 时停止.
- MILESTONE-08 尚未交付时, 真实后端集成验证 (FastAPI 托管, /execute, /git/sync) 无法执行 — 属已声明的 HITL 停止点, 不阻塞前端可执行切片; 后端就绪后回补人工验证.
