# 交接 — M11 已关闭 · 回访待办 G1~G5 实现

日期: 2026-08-27 · 项目根: `/var/mnt/DATA/Workspace/requests` · 上一会话角色: M11 验收引导收官

## 下一会话用途

**执行 5 件回访待办 (G1~G5) 并落测试与提交.** 用户已裁定全部立项, 本会话只记录不实现. 用户偏好: 一次只做一件事, 每件做完可让用户亲测; 回复中文电报文.

## 现状 (M11 已关闭)

- 验收四纲全过 (亲测): uv run 即起 / SPA B1~B8 / CLI C1~C3 / agent 自学 D / git E1~E2. 12 条 AFK 裁定全部接受. MILESTONE-11 → 已关闭, ROADMAP 前沿清空 + 关闭条目已写 (2026-08-27 编辑, 未提交).
- 服务状态: apic 已 stop (F 步骤, status=stopped); testbed 是本会话 nohup setsid 起的后台进程, **可能仍活或随会话死** — 用前先 `curl --noproxy '*' -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9000/echo`, 死则 `nohup setsid uv run testbed --port 9000 >/tmp/testbed.log 2>&1 &`.
- 数据目录 `/tmp/apic-acc` (验收数据, 随时可重建): 集合 smoke (echo/bearer/sse/fail/vars 五条) / acc (echo) / d-agent (echo/bearer, 场景 D 子代理所建); 环境 env (host=http://127.0.0.1:9000, 已激活); git 已绑 `/tmp/apic-remote.git`, remote main 有 init+sync 双提交 (与本地一致). `/tmp` 重启即丢失, 需重建 (重建样例见 08-26 handoff 现场段).
- git 状态: **11 个缺陷修复提交未推送** (origin/main..HEAD=10) + 本会话文档改动未提交: ROADMAP.md / MILESTONE-11.md / UNAUTHORIZED_DECISIONS.md (D-AFK-011 补记) / handoff 文档 (新文件, 未跟踪). **提交时机未定** — 上次建议验收收尾即推, 用户未表态, 执行会话开头问用户 (推 or 等 G 系列完一起推).
- token/端口: 服务已停; 再起后 port/token 随机漂移, 一律 `cat /tmp/apic-acc/.local/service.json` 现查; 浏览器地址随端口变, 提醒用户强刷 (Ctrl+Shift+R). 本会话暴露过的旧 token 已随停止失效.

## 待办 G1~G5 (需求原文 + 已勘察方案)

### G1 — run 含未解析变量条目: 整批 exit 2 改为跳过 (用户裁定: 改)
- 语义: run 时未解析变量条目跳过 (不产生 HTTP), 其余条目照常执行; summary/JUnit 计入 (status=None 即 failed, JUnit errors); CLI event_failed → exit 1 自动生效. **send 单条保持硬失败 exit 2 不变** (M4-D006 仅留给 send).
- 方案 (已勘察): `src/api_client/runner.py` — `run_collection` 的 build_request 逐条捕获 `UnresolvedVariablesError` (从 `.resolve` import), prepared 元组捎带 missing; `Run._stream` 对跳过条目合成 done `{type, timestamp, item: item_ref, status: None, duration_ms: 0, assertions: [], error: {code: "UNRESOLVED_VARIABLES", message}}` (无 meta/chunk), 保"每条目必有 done"不变式. `web/run.py` 的 422 分支保留为防御. `src/api_client_cli/commands_meta.py` 约 92~97 行 guide 文案更新: send 硬失败 vs run 跳过. 新测试仿 `tests/api_client/test_runner.py` 现有 fixture (testbed_url / _collect / TestClient, 见文件内 `_write_three_item_collection` 风格), 另跑真服务 CLI 演示 (建含未解析条目的集合, run → summary + exit 1).
- 验收判据: run 集合 (echo 过 + {{nope}} 跳过 + 断言败) → summary total=3 passed=1 failed=2, exit 1; send 单条未解析仍 exit 2 无流.

### G2 — SPA 环境管理 UI (用户裁定: 要修, 手写 YAML 不接受)
- 需求: 环境创建/编辑/删除/切换激活要在 SPA 内完成 (本地文件优先, 数据仍落 environments/*.yaml).
- 已勘察: 后端有 GET /environments (D-AFK-012) + PUT /environments/{name} (store.write_environment); **DELETE 环境端点与激活环境切换端点存疑未核** — 实现前先核 `src/api_client/web/` 路由表 (state 端点: store.set_active_environment 存在于 store.py 421 行附近, 对应 HTTP 端点形状待核). 激活切换: 可能走 PUT /state 或类似, 以代码为准.
- 方案候选: 复用 `spa/src/components/sidebar/EnvMenu.vue` 旁加环境管理弹层 (仿 VarEditor.vue 交互), 列表/新建/改名/编辑 vars/删除/设为激活; vars 编辑复用现有 kv 编辑器样式; secrets (env.secrets.yaml) 是否纳入 UI 需用户确认 (建议: 本件含 secrets 编辑, 与 vars 同弹层分栏).
- 注意: 切换激活环境后 SPA envVars 缓存刷新 (见 store 里 activeEnv/envVars 计算), 避免旧变量残留.

### G3 — 集合运行结果回看 (用户裁定: 要修)
- 需求: run 之后点条目, 响应面板要能看该次运行的日志/响应 (现 run 只驱动树徽标, 点条目不代入).
- 方案候选 A (推荐): `stores/app.ts` `run()` 事件流循环里按 slug 缓存每条目 meta/chunk/done 到新 state 字段 (内存), 点条目时若该 slug 有缓存则注入 response 面板展示; B: 点条目拉 history 转录 (`services/http.ts` 已有 `/history/{collection}/{slug}` 读取, ResponsePane.vue 已消费 history 结构) — 但 history 是"最近一次"记录, run 后点浏览可接受, A 更即事.
- 判据: run smoke (含 fail 条目) 后点每个条目, 右侧显示该次运行的 meta/headers/body/断言明细; 树徽标与响应面板不互相污染 (切换条目/重新发送后清理).

### G4 — SPA 组件动画 (新诉求)
- 需求: 各组件加动画效果. 低成本候选: Vue `<Transition>` 于集合树展开/折叠、弹层显隐、徽标状态变化 (✓/✗ 出现)、响应 tab 切换、树条目插入/拖拽; CSS 只过渡 transform/opacity (避免布局抖动). 范围先做观感最明显的: 弹层 + 树展开 + tab 切换, 其余等用户反馈.
- 约束: 不引入新依赖 (vue 内置 Transition); 不拖慢 vitest (动画对测试无碍, 若 jsdom 卡 Transition 用 CSS 类直测).

### G5 — 弹窗/下拉点击外部自动折叠 (新诉求)
- 需求: 弹窗展开态时, 鼠标点击弹窗以外位置自动折叠.
- 方案: 全局 click-outside 指令 (或组合函数, 挂 `document` 收 click, 判断 `el.contains(e.target)`), 应用到 CollectionMenu.vue / EnvMenu.vue / VarEditor.vue / 新建弹层等所有 popover 类组件; 注意多弹层互斥 (开一个关其他) 与输入框内点击不误关.

## 关键约束与坑

- 一次只做一件事 (用户明令); 每件完成后可请用户亲测再继续.
- 测试基线: 后端 `uv run python -m pytest` (255) / SPA `cd spa && npm run test` (91) + `npm run build`; **SPA dist 入库**, 改 src 后必 build 并提交 dist; 运行中服务直读磁盘 dist, 改完浏览器强刷.
- 环境有 SOCKS 代理变量: 真 HTTP 一律 trust_env=False (后端已处理); 本机 curl 加 `--noproxy '*'`.
- 命令面已定: `apic service status/token` 是 service 子命令, 非顶层; 服务重启端口必变.
- 安全五件套勿动 (绑回环/Host 白名单/禁 CORS/启动 token/CSP); 数据仓库 YAML 子集 (version 字段/禁锚点/kv 值字符串化) 见 store.py.
- 上次会话修过的坑勿回退: 选中条目必 loadDraft (竞态守卫), send 前 saveDraft, 失败 done.error 展示, `.envmenu` 样式特异性覆盖坑 (复用样式注意选择器), 集合切换清空绑定状态.
- 提交时机未定 (上文 git 状态), 开头问用户.

## 必读推荐

1. `docs/changes/handoff/2026-08-26-m11-acceptance-resume.md` — 前件全貌: 验收流程 B~F 细节, 8 类已修缺陷清单 (提交号), G 待办的方案初稿/坑位记录, 数据目录重建样例, 命令面/测试基线/代理坑. **新会话必读**.
2. `docs/changes/handoff/2026-08-25-m11-acceptance-handover.md` — 更早前件: 验收步骤 A~F 原文与验收点语义 (G 判据的出处), 已知小缺口原始表述.
3. `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` — 12 条裁定全文 (含 08-27 补记的 D-AFK-011): G2 的 GET /environments 出处 (D-AFK-012), summary/done 契约语义 (G1/G3 判据依据).
4. `docs/changes/api-client/roadmap/MILESTONE-11.md` + `ROADMAP.md` — 已关闭状态与到达目的地注记, 未决迷雾 (实时协议二期/AI 高阶) 按回访条件不动.
5. 代码位置 (只读前核): `src/api_client/runner.py` + `web/run.py` (G1), `web/` 路由表 + `store.py` 环境/state 函数 (G2), `spa/src/stores/app.ts` run()/selectItem + `components/response/ResponsePane.vue` + `services/http.ts` (G3), `spa/src/components/sidebar/*` 全部 popover 组件 (G4/G5).

## 路线图

1. 起点 (空仓库) → 目的地: 自用本地优先 Postman 替代品 (Python 后端 + SPA 供人 + CLI 供 AI, uv run 即起, 数据本地文件 git 管理). 前缘: M1~12 全关闭, M11 成品验收 (本会话收官, 四纲+12 裁定+缺口裁定齐), Roadmap 已清空.
2. 当前位置: **目的地已达成, 5 件回访待办 (G1~G5) 为收官后的用户新诉求**, 已全部裁定立项、方案勘察完毕、未实现.
3. 剩余距离: G1~G5 逐一实现 + 测试 + build/dist 入库 + 提交 (推送时机待用户) = 新诉求全部落地; 未决迷雾 (实时协议二期 / AI 高阶) 仍按回访条件不动, 不在本交接范围.