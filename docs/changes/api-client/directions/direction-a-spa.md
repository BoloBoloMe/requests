# Research: 全自研 SPA 路线 — 本地 Postman 替代品前端 (可行性/成本/收益)

## Summary
- 可行性高: Hoppscotch (Vue3), Bruno (React), Yaak (React), Insomnia (React) 四个开源先例证明浏览器 SPA 可完整实现 API 客户端, 对标 Postman 无硬障碍.
- 成本: 单人 MVP (请求构建/响应查看/集合/环境变量/断言+批量运行) 估 6-10 开发周, 核心组件均有成熟库可借, 自研集中在状态模型与流式/测试逻辑.
- 关键风险: 编辑器/JSON 查看器/Web 组件库的维护状态 (Monaco 重, react-json-view 停更, Shoelace sunset), 本地 dev server 攻击面 (Vite 累计 22 个 CVE), SSE/WS 经 Python 代理的流式工程.

## Findings

### Q1 复杂组件清单与实现难度 (依据三个先例的依赖清单)
一手证据: Hoppscotch `packages/hoppscotch-common/package.json`, Bruno `packages/bruno-app/package.json`, Insomnia `packages/insomnia/package.json`.

1. **嵌套 key-value 编辑器** (请求头/查询参数/表单) — 难度中. 本质 = 行表格 + 类型切换(text/file) + 启用开关 + 自动补全. 无"即插即用"库, 属标准表格组件工作: Bruno 用 formik 管表单状态, Hoppscotch 自研. [Bruno deps](https://raw.githubusercontent.com/usebruno/bruno/main/packages/bruno-app/package.json)
2. **响应查看器** — 难度低-中, 全部有现成库: JSON 树 (vue-json-pretty / react-json-view), 语法高亮 (highlight.js), XML 格式化 (xml-formatter), 二进制 hex (hexy), PDF (pdfjs-dist), diff 视图 (diff2html), 大数保真 (lossless-json), jq 查询 (jq-wasm). [Hoppscotch deps](https://raw.githubusercontent.com/hoppscotch/hoppscotch/main/packages/hoppscotch-common/package.json)
3. **代码编辑器** — 难度低 (借库). CodeMirror 6: 模块化 (单包 unpacked ~1.2MB), 周下载 1205 万, 活跃 (2026-04 仍有提交). Monaco: 全量 npm 包 unpacked 93.4MB (重), 周下载 835 万, Microsoft 维护. 三个先例全用 CodeMirror, Hoppscotch/Insomnia 额外集成 Monaco (worker 配置是主要集成成本). [npm registry @codemirror/view](https://registry.npmjs.org/@codemirror/view/latest) [npm registry monaco-editor](https://registry.npmjs.org/monaco-editor/latest)
4. **标签页** — 难度低. 无专门库, 自研; 难点在标签页状态隔离 + 未保存提示, 标准工作.
5. **拖拽排序** (集合树/标签) — 难度低-中. sortablejs (422 万/wk), vuedraggable (143 万/wk, Hoppscotch 用), @dnd-kit (2295 万/wk), react-dnd (Bruno 用). 集合/文件夹嵌套树拖拽需处理嵌套语义, 唯一略费事点.
6. **SSE/WebSocket 响应流** — 难度中-高 (本项目特例). Hoppscotch 支持 WS/SSE/Socket.IO/MQTT 实时测试 (依赖 socket.io-client v2/v3/v4, paho-mqtt). 本项目浏览器直连受限、走 Python 后端代理: 前端用 fetch ReadableStream 解析 SSE 分块 + WS 连后端转发端口, 难点在取消/重连/缓冲/大流渲染, 是真正需要自研的部分. [Hoppscotch SSE docs](https://docs.hoppscotch.io/documentation/getting-started/realtime/sse.md) [Realtime 总览](https://docs.hoppscotch.io/documentation/features/realtime-api-testing.md)

### Q2 可借组件库与成熟度
- CodeMirror 6: 成熟/活跃/按需引入, 首选. 官方说明见 [codemirror.net](https://codemirror.net/), registry 数据见上.
- Monaco: 成熟 (Microsoft), 仅需 IDE 级能力时引入, 体积是代价.
- **react-json-view 已停维护**: README 明示 "no longer being maintained", 官方推荐 [@microlink/react-json-view](https://github.com/microlinkhq/react-json-view) (68 万/wk); 轻量替代 react-json-view-lite (166 万/wk). [react-json-view README](https://raw.githubusercontent.com/mac-s-g/react-json-view/master/README.md)
- **Shoelace 已 sunset**: README 明示 "no active development", 继任 Web Awesome (npm @awesome.me/webawesome v3.11.0, 周下载仅 67, 1.3k stars, Font Awesome 商业化项目). 选 Web 组件路线需直接上 Web Awesome 并承担年轻/商业化风险. [Shoelace README](https://raw.githubusercontent.com/shoelace-style/shoelace/next/README.md) [webawesome repo](https://github.com/shoelace-style/webawesome)
- 通用 UI 组件无完美现成匹配: Hoppscotch 自研 @hoppscotch/ui (其 deps 可见) 即为证据; 建议手写 + Tailwind.
- 面板/拖拽: splitpanes (Hoppscotch), react-resizable-panels (Insomnia), @dnd-kit (现代 React 方案).
- 结论: 自研面可压缩到约 30-50%: 数据模型/状态/请求执行/测试引擎自研, 编辑器/JSON/拖拽/高亮借库, 通用控件手写.

### Q3 前端构建链长期维护代价 (单开发者)
- 依赖面大: Hoppscotch 前端 ~90 个运行时依赖 + ~50 devDeps, 且维护 20+ 个 pnpm security overrides (cross-spawn/minimatch/postcss/js-yaml 等); Bruno 同样维护 overrides. 安全补丁跟进是例行成本. [Hoppscotch package.json](https://raw.githubusercontent.com/hoppscotch/hoppscotch/main/package.json)
- 工具链漏洞频发: Vite 累计 22 个 GitHub 安全公告 (OSV 数据), 多为 dev-server 本地端口攻击面 (server.fs.deny 绕过, 恶意网页读 dev server 响应, path traversal), 2025-2026 密集; esbuild GHSA-67mh-4wv8-2f99 (dev server CORS 任意站点可读写). 本地运行的产品必须跟进升级. [OSV vite](https://api.osv.dev/v1/query) [esbuild advisory](https://github.com/advisories/GHSA-67mh-4wv8-2f99)
- 大版本节奏: Vite 两年内 5→6→7→8 (当前 8.2.1, Hoppscotch 已上 7.x); React 19 / Vue 3.5 / Svelte 5 (runes) 各有迁移成本.
- 应对: 自用项目锁版本 + 季度批量升级 (dependabot/renovate) + 仅处理 CVE; 代价 = 每季度 0.5-1 天 + 偶发破坏性升级 1-2 天. 长期不升级则漏洞累积, 对本地工具是真实威胁 (恶意网页攻击 127.0.0.1 场景已被 esbuild/Vite CVE 证实).
- 增量成本本质: 相对纯 Python 方案, 前端链新增第二套运行时 (node) 与依赖面, 这是本方向主要增量维护项.

### Q4 Vue/React/Svelte 相对适配性
- **Vue 3**: Hoppscotch (80k stars) 全栈采用, 同场景依赖组合 (vue-json-pretty, vuedraggable, splitpanes, @guolao/vue-monaco-editor) 全部被实战验证; 模板语法 + 中文文档对单人友好. 周下载 1450 万.
- **React**: Bruno (46k stars), Yaak, Insomnia 三先例; 生态最大 (@dnd-kit 2295 万/wk, react-resizable-panels, @monaco-editor/react); JSX+hooks 心智负担略高; 组件选择最多.
- **Svelte 5**: 无主流 API 客户端参照; runes 对新建项目无历史包袱 (迁移痛只影响存量 4.x); 但 JSON 查看器/拖拽/面板专门库生态明显小. 周下载 540 万. 可行但"借库红利"最少.
- 建议: Vue 或 React 二选一, 跟随同场景成熟组合; 以 Hoppscotch 依赖组合为模板选 Vue, 偏好最大生态选 React. 数据: [npm registry](https://registry.npmjs.org/react/latest) [svelte docs runes](https://svelte.dev/docs/svelte/what-are-runes)

### Q5 结论
- 可行性: **高**. 四个开源先例验证; Postman 本体是 Electron, Web SPA 交互自由度更高, 体验上限无硬障碍.
- 开发成本: MVP 单人 **6-10 开发周** (推断): 请求/响应核心交互 2-3 周, 集合树+标签+拖拽 2-3 周, 测试引擎+批量运行 2-3 周, 打磨 1-2 周. 依据: 核心组件全有现成库.
- 维护成本: **中低**. 锁版本 + 季度升级可行; 增量 = node 工具链 + CVE 跟进 + 偶发迁移.
- 体验上限: **高**, 对标 Postman 主要交互 (嵌套表格/响应树/多标签/拖拽/流式日志) 均有组件支撑.
- 关键风险 (按严重度):
  1. **高** — 停更库陷阱: react-json-view (停更), Shoelace (sunset); 需预先选 fork/继任并接受其风险.
  2. **高** — 本地服务攻击面: dev server + 本地后端均应收紧 CORS, 跟进 Vite/esbuild 安全升级 (22+1 个 CVE 佐证).
  3. **中** — 流式响应 (SSE/WS) 经 Python 代理: 前端流解析/取消/重连是主要自研难点, 建议先砍范围 (REST 先行, SSE/WS 二期).
  4. **中** — Monaco 体积: 默认 CodeMirror 6, 按需再加 Monaco.
  5. **低** — 依赖锁定过度 → 技术债; 自用可接受, 保留升级路径即可.

## Sources
- Kept:
  - Hoppscotch common package.json (https://raw.githubusercontent.com/hoppscotch/hoppscotch/main/packages/hoppscotch-common/package.json) — 一手组件选型证据 (Vue3/CodeMirror6/Monaco/vue-json-pretty/socket.io 多版本).
  - Bruno bruno-app package.json (https://raw.githubusercontent.com/usebruno/bruno/main/packages/bruno-app/package.json) — 一手证据 (React19/CodeMirror5/react-json-view/react-dnd).
  - Insomnia package.json (https://raw.githubusercontent.com/Kong/insomnia/develop/packages/insomnia/package.json) — 第三先例 (React18/CodeMirror5/Monaco/react-resizable-panels).
  - react-json-view README (https://raw.githubusercontent.com/mac-s-g/react-json-view/master/README.md) — 停维护官方声明.
  - Shoelace README (https://raw.githubusercontent.com/shoelace-style/shoelace/next/README.md) — sunset 官方声明 + Web Awesome 迁移指引.
  - OSV vite 查询 (https://api.osv.dev/v1/query) — 22 个 CVE 一手数据.
  - esbuild advisory (https://github.com/advisories/GHSA-67mh-4wv8-2f99) — dev server CORS 攻击面.
  - Hoppscotch SSE docs (https://docs.hoppscotch.io/documentation/getting-started/realtime/sse.md) — SSE/WS 支持证据.
  - npm registry latest (https://registry.npmjs.org/@codemirror/view/latest 等) — 版本/体积/周下载一手数据.
- Dropped:
  - npmjs.com 包页面 — Cloudflare 拦截 (403), 改用 registry API.
  - agenthicks.com CodeMirror vs Monaco 对比页 — SEO 聚合文, 无一手数据.
  - YouTube 编辑器教程 — 非一手源且不可抓取.

## Gaps
- 搜索服务不可用 (多次查询返回空), 结论依赖直接抓取官方源与 registry/OSV/GitHub API; 未做二次交叉验证的仅有: Monaco 实际浏览器 bundle 体积 (仅有 npm 全量 93MB), 标记为近似.
- 未找到 Svelte 系主流 API 客户端参照 (Yaak 实为 React), Svelte 结论基于生态规模推断.
- 人周估算为推断, 无直接基准数据; 若要精确可对 Hoppscotch 前端代码量 (LOC/模块数) 做一次 repo 统计.
- Hoppscotch 内部请求执行 (kernel/代理) 未深挖 — 本项目已定 Python 代理架构, 不阻塞; 但其 interceptor 机制 (docs/features/interceptor) 可作代理 API 设计参考.