# 交接 — G 系列执行中: G1~G3 已提交, G4 收尾卡壳, G5/G6 未动

日期: 2026-08-30 · 项目根: `/var/mnt/DATA/Workspace/requests` · 上一会话角色: G1~G6 逐项实现

## 下一会话用途

继续完成 G4 收尾 + G5 + G6, 全部落测试/build/dist 入库/提交后, 可考虑推送.

用户补充需求: **G6 — 新增 README.md (项目介绍 + 使用教程)**, 排最后做 (收录 G1~G5 新能力).

## 现状 (增量事实)

- **G1~G3 已提交** (`66e98bd` G1 / `d95f982` G2 / `1e5aa2f` G3), 各含测试, 提交时后端 260 / SPA 103 全绿. 三件判据已达成:
  - G1: run 逐条跳过未解析变量条目 (合成 done status=null + error.code=UNRESOLVED_VARIABLES, 计 summary failed + JUnit errors); send 单条硬失败 exit 2 不变. 真服务 CLI 实测: run total=3 passed=1 failed=2 exit 1; send exit 2.
  - G2: 后端补 `Store.delete_environment` + `DELETE /environments/{name}` (vars+secrets 清理, 激活态联动归空); SPA EnvMenu 下拉尾「管理环境…」入口 → 新 `EnvEditor.vue` 弹层 (列表/新建/改名=写新删旧+激活迁移/编辑 vars+secrets 分栏/删除/设为激活); store 扩 createEnvironment/saveEnvironment/removeEnvironment/refreshEnvs; services 扩 putEnvironmentSecrets/deleteEnvironment (http+mock+types 三处).
  - G3: 方案 A 内存缓存. store.run() 按 slug 缓存 meta/chunk/done 到 `state.runViews`; selectItem 内调 viewRunResult 注入响应面板; `state.runViewing` 标记回看态; loadDraft 回看态例外不清面板; send 置 runViewing=false; ResponsePane 顶部加「⏱ 运行回看」提示条.
- **G4 实现已写, 测试 1 条卡壳** (未提交, 工作区改动): CSS 动画段 (pop/fold/tabpane/badge-in + prefers-reduced-motion 降级) 在 spa/src/style.css 1125 行起; Transition 已应用 — EnvMenu (pop×2: 下拉+EnvEditor), CollectionMenu (pop), Sidebar VarEditor (pop), FolderTree (非根子树 fold; 状态徽标 badge-in, `mode="out-in"` + `:key=stClass(element)`), RequestBuilder (kvwrap 内 `<Transition name="tabpane" mode="out-in">` 包 `<div :key="builderTab" class="tabpane">`), ResponsePane (r-body 内同款, `:key="responseTab"`).
  - **卡点**: `spa/src/components/sidebar/__tests__/Anim.spec.ts` TC-002 断言 CSS 内容, 用 `import css from "../../../style.css?raw"` 在 vitest 3.2.7 下**返回空串** (vitest 对 css 模块默认 stub, ?raw 被吞). TC-001 (组件开合冒烟) 过. 候选修法 (未试): ① `import.meta.glob("../../../style.css", { as: "raw" })` (vite importGlob 类型含 `raw: string`); ② vitest config 试 `css: true`/`css: { modules: false }`; ③ 退回 fs 读取 (需 tsconfig types 加 "node", 当前 `["vite/client"]`, node:fs/node:url 会 TS2307 — 已实测); ④ 干脆删 TC-002 只留 TC-001.
  - **已知未验证项**: FolderTree 在 G4 改动里被整体重写过一次 (非根分支包 Transition, 根分支 `<template v-else>` 平铺), 现有 Tree.spec/DragCrud.spec 全过, 但建议人工浏览器里核一次树展开动画观感.
  - dist 已 build 出新产物 (index-5mfdjeuh.css / index-C7mNbTbG.js), **未提交**.
- **G5 未动**: 弹窗/下拉点击外部自动折叠. 方案已勘察 (交接 08-27): 全局 click-outside 指令挂 document, `el.contains(e.target)` 判断, 应用到 CollectionMenu/EnvMenu/VarEditor/EnvEditor; 注意多弹层互斥与输入框内点击不误关. 现有弹层均无遮罩/外部监听, 纯 v-if + 局部 @click.stop (EnvEditor 根已 @click.stop).
- **G6 未动**: README.md (根目录, 确认不存在). 素材: pyproject.toml 命令面 (apic/testbed), docs/changes/api-client/*, CLI guide 文本 (src/api_client_cli/commands_meta.py 全文即教程底料), SPA 功能 (侧栏集合树/环境管理/运行回看/动画).
- **git 推送线已了结** (上个交接记载已过时): `git ls-remote` 实测 GitHub main = 02fdee2, 12 提交已在远端. 当前本地 3 个新提交 (G1~G3) 未推送, 无凭据配置 (credential.helper 空), 推送成败未知 — 上次 push 成功的途径未记录.
- **数据目录**: `/tmp/g1-demo` 为本会话 G1 演示所建 (collections/demo: echo/unresolved/missing 三条); 验收目录 `/tmp/apic-acc` 已随关机消失 (预期), 重建样例见 08-26 handoff.
- **测试基线当前**: 后端 pytest 260; SPA vitest 104 过 + 1 失败 (Anim TC-002); typecheck 干净; build 出产物.

## 关键坑位 (本会话踩过, 勿复踩)

1. **cwd 漂移 (会话级)**: bash 工具会话目录在仓库根与 spa/ 间漂移多次 (工具行为, 原因未明, 疑似子命令后台化后重置). 已致一次事故: `cat >> src/style.css` 在仓库根创建了假文件, 后合并回 spa/src/style.css 并删根文件. **每条 shell 命令开头显式 `cd`**, 勿依赖上一条 cwd.
2. **vitest 启动方式**: 必须从 spa/ 跑 `npm run test` 或 `./node_modules/.bin/vitest`; `npx vitest` 会拉到无 vue 插件的孤立 vitest 报 "Failed to parse source... install @vitejs/plugin-vue".
3. **异步 store 动作测试**: trigger() 后断言必须 `await vi.waitFor(...)` (惯例见 DragCrud.spec.ts); EnvEditor.spec 首轮败于此.
4. **G3 调试发现的真实 bug (已修, 1e5aa2f 内)**: viewRunResult 幂等守卫若用 `state.selected.slug === slug` 会吞掉所有切换注入 (selectItem 先更新 selected 再调 viewRunResult, 恒真); 判据必须用注入标记 `state.response?.meta?.item?.endsWith(`/${slug}`)`.
5. **mock.ts putEnvironment 用 `this.getEnvironment`**: 对象字面量方法 this 依赖调用形态, 复刻时小心.
6. Vue 内置 `<Transition>`/`<TransitionGroup>` 在 script setup 模板无需 import.
7. TransitionGroup 插进 v-if 链曾踩坑 (中间提交又撤回), 现 FolderTree 用普通 `<Transition>` 包子树 div + 根分支 `<template v-else>` 平铺, 测试全过.

## 必读推荐

1. `docs/changes/handoff/2026-08-27-g-tasks-execute-handoff.md` + `2026-08-27-m11-closed-g-tasks-handoff.md` — 上一份交接与 G1~G5 原始需求/判据/方案勘察 (G5 方案在其中, G6 是本会话新增).
2. `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` — 12 条裁定 (D-AFK-005/007/008/009/011/012 已被 G1/G2 实现引用; summary/done 三态口径是 G1/G3 判据依据).
3. 本会话改动文件: `src/api_client/runner.py`(G1) `src/api_client/store.py`+`web/crud.py`(G2 DELETE) `spa/src/stores/app.ts`(G2 store 动作+G3 runViews) `spa/src/components/sidebar/EnvEditor.vue`(G2 新组件) `spa/src/components/response/ResponsePane.vue`(G3 提示条+G4 tabpane) `spa/src/style.css` 1125 行起 (G4 动画段).
4. `spa/vite.config.ts` + `spa/tsconfig.json` (types=["vite/client"]) — Anim TC-002 的 ?raw 卡点环境.
5. 弹层组件清单 (G5 目标面): `CollectionMenu.vue` `EnvMenu.vue` `VarEditor.vue` `EnvEditor.vue`.

## 路线图

1. 起点: 空仓库 → 目的地: 自用本地优先 Postman 替代品 (Python 后端 + SPA 供人 + CLI 供 AI, uv run 即起, 数据本地文件 git 管理).
2. M1~12 全关闭 → M11 验收收官 (08-27) → Roadmap 清空, 目的地达成.
3. 回访待办 G1~G5 立项 (08-27 裁定) + G6 新增 (08-30 用户追加 README 需求).
4. 当前: G1/G2/G3 已提交; G4 实现写完但 1 条测试卡壳未提交; G5/G6 未动; 本地 3 提交领先 origin/main.
5. 剩余距离: G4 修 TC-002 + 提交 → G5 click-outside → G6 README → (推送凭据若用户已有方案可一并推).
