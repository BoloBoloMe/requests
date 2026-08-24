# ISSUE-01: Vue3 工程骨架 + dist 联调

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
在仓库根新建 `spa/` 的 Vite + Vue3 + TypeScript 前端工程: 可 `npm run dev` 开发, `npm run build` 产出到 `spa/dist/` 并入库. 建立共享 API client (`spa/src/api/http.ts`) 从页面读取注入的 token (见 D003/D004), 所有请求带 `X-Token` header, 缺失/空 token 时明确拒绝并记录可诊断错误. 组一个 `App.vue` 空白骨架: 左 `Sidebar` 占位 + 右 `RequestPanes` 占位, 预留上下分区 (变体 B 布局, M5-D1). 建立 `services/` 适配层抽象 (INJECTABLE transport), 使后续 ISSUE 可用 mock 传输做组件测试. 接入 vitest 使首个冒烟测试可跑. 适合 AFK: 纯工程搭建 + 契约固定的 client, 无新决策.

## 覆盖依据
- Task: `../roadmap/MILESTONE-09.md` — Vue3 SPA 全量实现, dist 分发按 M3-D003.
- Technical: `../milestone-03/DECISIONS.md` D003 (dist 入库+token 注入+no-store), D004 (token header 携带, SSE `?token=`).

## 相关决策
- `../milestone-03/DECISIONS.md`: D003, D004, D010 (本 ISSUE 确立 client 对接的 REST/RPC 契约面), D013 (API 不版本化, 无前缀).
- `../milestone-05/DECISIONS.md`: 决策 1 (双栏布局骨架), 决策 4 (视觉基调起底).

## 允许范围
- `spa/` 目录全部内容: 工程配置 (package.json/tsconfig/vite config/vitest config), 入口 (main.ts/index.html), `src/api/`, `src/services/`, `src/components/App` 骨架与空占位.

## 禁止范围
- 不实现具体功能面 (树/构建器/响应/runner/git 交互 — 属 ISSUE-02..05).
- 不引入路由级多页面 (无 vue-router 多路由).
- 不修改 dist 之外的仓库根、Python 后端、`pyproject.toml`.
- 不由 SPA 关闭/绕过 token 校验或放宽 CORS (D004).

## 代码定位提示
- 参照原型 `../prototypes/spa-ui/2026-08-23-spa-ui-variants.html` 的 `.vb` 区 (section 变体 B) 作骨架目标; 视觉色板取 `:root` 变量.
- 组件选型侦查 `../directions/direction-a-spa.md` Q4 (Vue 生态) 定栈; 建 `src/services` 抽象 transport 便于注入 mock (后续 ISSUE 复用).
- token 来源: 后端按 D003 在 serve 时注入 index.html (占位符替换); SPA 从 `window.__TOKEN__` 读取.

## TDD 切片
- TS-001:
  接缝: `src/api/http.ts` 的公开请求函数 (注入可替换的 fetch 与 token provider).
  测试用例: TC-001 请求自动带 `X-Token`; TC-002 token 缺失/空时抛可诊断错误且不发起请求.
  先写的失败测试: `http.ts 的 request 在缺 token 时不应 fetch` — 先写断言缺失 token 抛错, 预期失败 (尚未实现).
  最小绿色实现范围: 读 token source, 校验非空, fetch 前附加 header; 引入注入点 (token 与 fetch 均可替换).
  不得测试: 私有 header 拼接细节内幕, 具体 fetch 实现.
  覆盖: SK-02.
- TS-002:
  接缝: `App.vue` 渲染的骨架占位结构 (左 side + 右 panels).
  测试用例: TC-003 挂载 App 后同时存在 Sidebar 与 Request/Response 占位容器.
  先写的失败测试: `App 渲染左容器与右容器` — 预期失败 (骨架未建).
  最小绿色实现范围: 最小 `App.vue` + 两个占位子组件 + vitest/jsdom 冒烟装配 (顺带搭好测试底座).
  不得测试: 具体面内布局细节.
  覆盖: SK-01.

## 验证入口
- `cd spa && npm run test:unit` (vitest) 通过 TS-001/TS-002.
- `cd spa && npm run build` 产出 `spa/dist/` 且成功; dist 纳入 git 提交 (D003).
- 人工验证 (HITL, 依赖 MILESTONE-08 后端): 由 FastAPI 托管 `spa/dist/`, 页面加载后 `window.__TOKEN__` 注入生效、index.html 带 `Cache-Control: no-store`.

## 风险提示
- dist 漂移 (改源码忘 build) — 以 D003 的时间戳警告为准, 不在 SPA 内处理; 本 ISSUE 保证 `npm run build` 产物路径稳定即可.
- token 缺失会导致全部请求失败 — 用可诊断错误提示而非静默, 便于接后端时定位.

## 停止条件
- 需改变 M3-D003/D004 分发/安全语义或引入多页面时停止.
- 后端契约与本 client 假设不符 (REST/RPC 面, token 传输方式) 时停止并与父会话核对.

## 适合 AFK 的原因
- 工程搭建、client token 契约与骨架均无新产品/架构决策; 唯一 HITL 子项 (FastAPI 真实托管) 已独立标记为人工验证.

## 验收标准
- [ ] `spa/` 工程可 `npm run dev` / `npm run build`, 产物入 `spa/dist/` 且入库.
- [ ] api client 自动携带 `X-Token`, 缺 token 抛可诊断错误, 有可注入传输供后续 mock 测试.
- [ ] `App.vue` 渲染左右双栏骨架, 视觉起底为原型变体 B 色板.
- [ ] vitest 可跑且 TS-001/TS-002 全绿.

## 被阻塞于
- 无
