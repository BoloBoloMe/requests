# ISSUE-03: 请求构建器

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
右主区上半请求构建器 (变体 B), 对选中请求条目 (ISSUE-02 树联动):
- URL 栏: 方法徽章 (GET 绿/POST 黄/PUT 蓝/DEL 红, 原型 `.m`/`MCOLOR`) + URL 展示 (其中 `{{var}}` 高亮, `.urlin .var`) + 「发送」主按钮 (发送动作本 ISSUE 只触发展示态/交由 ISSUE-04 接 SSE).
- 解析预览行 (`{{var}}` 按当前环境即时替换显示的 `→` 行) — 环境切换 (ISSUE-02) 后实时更新.
- 五个 tab: Params / Headers / Body / Auth / 断言 (带计数胶囊, 原型 `.tabs .n`).
- Params/Headers: kv 行无边框悬停显框 + 描述列 (`.kv`/`.desc`), 末行回车增行, 行可删 (`×`).
- Body: 无体提示或 CodeMirror 6 编辑器 (JSON/文本).
- Auth: 继承集合默认 / 覆盖 (Basic/Bearer/API Key/Digest) / 无认证 三选 (原型 `.authbox`).
- 断言 tab: 结构化表单 (target: jmespath 路径 / op: 比较符 / expect: 期望值) + Python 逃生舱编辑框 (CodeMirror 6, 高亮 python); 可增删行 (M6 双形态, ADR 0006).
- 适合 AFK: 全由原型变体 B + M6 断言形态 + direction-a 选型确定.

## 覆盖依据
- Technical: `../milestone-05/DECISIONS.md` 决策 3 (请求构建器五面: 方法着色/URL 高亮/解析预览/kv 行/Auth 三选).
- Technical: `../milestone-01/DECISIONS.md` 断言 DSL 形态 (结构化 + Python 逃生舱, 见 MILESTONE-06 原型), ADR 0006.
- Technical: `../milestone-03/DECISIONS.md` D010 (条目文件结构字段).

## 相关决策
- `../milestone-05/DECISIONS.md`: 决策 3, 4 (视觉).
- `../milestone-01/DECISIONS.md`: D-断言 DSL (结构化+逃生舱双形态, 经 MILESTONE-06 原型固化).
- `../milestone-03/DECISIONS.md`: D010 (条目字段经 REST 读写), D013.

## 允许范围
- `spa/src/components/builder/` (UrlBar, MethodBadge, KvEditor, BodyEditor, AuthEditor, AssertionEditor), 相关 store 与方法/Tab 状态, services 适配层对应方法 + mock.

## 禁止范围
- 不实现响应/日志/SSE 消费 (ISSUE-04) 与 runner 批量 (ISSUE-05).
- 不亲自执行 HTTP 请求/不解析响应 (属后端 Engine; SPA 只经 `/execute` SSE, ISSUE-04).
- 不用 react-json-view/Shoelace; 不手写拖拽 (本 ISSUE 无拖拽需求).
- 断言逻辑 (target 求值/op 比较) 不落在 SPA — 属后端 Assert; SPA 仅编辑与展示表单结构.

## 代码定位提示
- 原型变体 B `urlbar`/`msel`/`urlin`/`resolved`/`tabs`/`kvwrap`/`kv`/`desc`/`bodyedit`/`authbox`/`alist`/`py` 为目标结构; 断言原型见 `../prototypes/assertion-dsl/` (M6) 与 ADR 0006.
- CodeMirror 6 选型 `../directions/direction-a-spa.md` Q1-3 (CodeMirror 6 首选, 单体轻量); vue-json-pretty/highlight 供 Body 用 (ISSUE-04 接).
- URL 变量高亮可复用 ISSUE-02 的环境状态 (store) 做解析预览.

## TDD 切片
- TS-001:
  接缝: UrlBar 组件 + 环境 store.
  测试用例: TC-001 `{{var}}` 高亮为变量 span (非纯文本); TC-002 环境切换后解析预览行 `→ URL` 相应替换变量值.
  先写的失败测试: `URL 解析预览随环境切换变化` — 预期失败 (高亮/预览未实现).
  最小绿色实现范围: 正则高亮 `{{var}}` 渲染 span; 可注入的变量解析器输出预览行.
  不得测试: 后端 Resolve 求值逻辑.
  覆盖: REQ-01.
- TS-002:
  接缝: MethodBadge/方法选择.
  测试用例: TC-003 每方法 (GET/POST/PUT/DELETE) 渲染对应语义着色类.
  先写的失败测试: `DELETE 方法徽章带 del 类` — 预期失败 (未实现着色).
  最小绿色实现范围: 方法→类名映射表渲染.
  不得测试: 颜色具体值 (由 CSS/原型).
  覆盖: REQ-01.
- TS-003:
  接缝: KvEditor (Params/Headers 共用).
  测试用例: TC-004 末行回车新增空白 kv 行; TC-005 行删除; TC-006 描述列可编辑.
  先写的失败测试: `kv 末行回车追加新行` — 预期失败 (kv 交互未实现).
  最小绿色实现范围: kv 行渲染 + 末行 Enter 追加 + 删除行 + 描述列输入.
  不得测试: 表格库内部.
  覆盖: REQ-02.
- TS-004:
  接缝: AuthEditor.
  测试用例: TC-007 三选一 (继承/覆盖/无) 选中态正确; TC-008 覆盖态展示类型选择 (Basic/Bearer/API Key/Digest).
  先写的失败测试: `Auth 三选切换选中态` — 预期失败 (auth 表单未实现).
  最小绿色实现范围: radios + 覆盖类型下拉 + 关联字段输入占位.
  不得测试: 认证握手 (属后端 Engine).
  覆盖: REQ-02.
- TS-005:
  接缝: AssertionEditor (结构化行 + Python 逃生舱).
  测试用例: TC-009 结构化行 target/op/expect 字段渲染与编辑; TC-010 切到 Python 逃生舱时挂载 CodeMirror 编辑框, 输入可读回.
  先写的失败测试: `断言 Python 编辑框输入可读回` — 预期失败 (CodeMirror 未接入).
  最小绿色实现范围: 结构化表单行 + CodeMirror 6 实例 + 值读写双向绑定 + 行增删.
  不得测试: 断言求值结果 (由后端).
  覆盖: REQ-03.

## 验证入口
- `cd spa && npm run test:unit -- src/components/builder` 通过 TS-001..005.
- 人工: `npm run dev` 对照原型变体 B 请求构建器 (五 tab, URL 高亮+预览, kv 悬停显框, Auth 三选, 断言双形态).

## 风险提示
- CodeMirror 6 在 tab 切换/组件重挂时状态丢失 — 用稳定 key + 组件生命周期持有 EditorView, 避免反复重建 (原型演示与 direction-a Q1-3 提示).
- 断言结构化字段的 target 为 jmespath 路径字符串, SPA 不校验其合法性, 仅原样编辑保存 (求值归后端 Assert).

## 停止条件
- 需在 SPA 内实现断言求值/HTTP 执行时停止 (违反模块边界).
- 引入停更库或手写拖拽时停止.

## 适合 AFK 的原因
- 构建器形态由原型变体 B (M5-D3) + M6 断言双形态 + direction-a 组件选型完整确定, 无未决决策.

## 验收标准
- [ ] URL 栏方法着色, `{{var}}` 高亮, 解析预览随环境即时切换.
- [ ] Params/Headers/Body/Auth 四 tab 的 kv/编辑交互 (无边框悬停显框, 回车增行, 描述列, Auth 三选) 达成.
- [ ] 断言 tab 结构化 (target/op/expect) + Python 逃生舱 (CodeMirror 6) 可编辑并保存回条目.
- [ ] 编辑结果经 services 适配层可写回 (mock), 视觉得到原型.

## 被阻塞于
- ISSUE-02 (`issues/ISSUE-02-sidebar-tree-env-vars.md`): 依赖树选中条目联动与全局环境状态.
