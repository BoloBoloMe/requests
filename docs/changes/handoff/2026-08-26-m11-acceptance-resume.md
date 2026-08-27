# 交接 — MILESTONE-11 成品验收 (HITL) 继续

日期: 2026-08-26 · 项目根: `/var/mnt/DATA/Workspace/requests` · 上一会话角色: 验收引导 + 自测修复

## 下一会话用途

继续一步步指引用户完成 M11 剩余验收 (每步只给用户一件事), 直至关闭 M11 并清空 Roadmap. 用户明确要求: 一次只指引用户干一件事, 逐步进行.

## 现状

### 验收进度 (SPA 步骤 B)

- B1 双栏界面 ✓ (用户确认)
- B2 建集合 acc + 条目 + 改名 + 发送 + Body(漂亮 JSON)/Headers/日志 三 tab ✓
- B3 bearer /auth/bearer → 200 ✓ (用户亲测; 前置数据修正: env host 值改为含 http:// 协议头 — 缺协议发不出是数据问题非产品 bug)
- B4 断言 eq 200 ✓ / eq 500 ✗ + 明细 ✓ (用户已确认 "ok")
- B5 env {{host}} 解析 ✓ (随 B3 亲测三要素全过: 环境胶囊/URL 预览/发送层生效)
- B6 SSE 5 帧 ✓ (用户亲测, 逐帧流式)
- B7 集合运行徽标通过路径 ✓ (用户亲测: 树 ✓ 徽标 + 文件夹计数); 失败红字+跳断言 tab 未亲测; 2026-08-27 提新缺口"运行结果不可回看"待裁定
- B8 history list (agent 走通过)
- **未走**: C (CLI 命令面走查), D (agent 自学调用, 标 HITL), E git (agent 自测过: bind/init 提交/sync 提交/secrets=0, 用户未亲测), F (stop 收尾), AFK 12 条裁定复核, M11 关闭 + Roadmap 清空.

### 验收现场

- **2026-08-27 关机重建过现场**: /tmp 被清空, 数据目录全部重建 — env 环境 (host=http://127.0.0.1:9000, 手写 YAML + 已激活) + smoke 集合 (echo-simple/bearer-auth/sse-stream 三条, CLI item list 验证可读) + acc 集合 (acc-echo 一条); git 绑定与 /tmp/apic-remote.git 已丢, E 步骤需重建 (git init --bare 重来).
- testbed: `uv run testbed --port 9000` 运行中 (关机会死, 新会话若死则重启).
- apic 服务: 重启过两次且吃过一次关机, **当前端口随机, 以 `uv run apic service status --data-dir /tmp/apic-acc` + `cat /tmp/apic-acc/.local/service.json` 现查为准** (2026-08-27 重建后: 42961, token 9ozTagF5s-...).
- 数据目录 `/tmp/apic-acc`: 集合 smoke (3 条目) / 测试 / acc; 环境 env (host=127.0.0.1:9000, 手写 YAML 建的); git 已绑 `/tmp/apic-remote.git` (init+sync 提交已推).**2026-08-27 后此段作废, 见上方重建说明.**
- 浏览器自动化已就位: `/home/bolo/.agents/skills/access-web/browse/` 下 `uv run python` 可用 (本会话自测用它), 需 headless Chromium (已装). 用户亲自验收用普通浏览器.

### 本会话发现并修复的缺陷 (11 提交, 全部已提交未推送)

1. `4317207`+`cdcd9dd`: SPA 无新建/切换集合 UI (新组件 CollectionMenu.vue, 集合名下拉+内联新建; 审核修复: 切换清空集合绑定状态/mock 名称校验对齐 422/防重复提交).
2. `28f5354`: 集合下拉被 `.envmenu right:74px` 压窄 (同特异性后者胜, 已提高 `.vb .envmenu.collmenu` 特异性 — **类似覆盖顺序坑以后写复用样式时注意**).
3. `7390566`: selectItem 不装载草稿 → 点树/新建后构建器空白 (现在 selectItem 触发 loadDraft + 竞态守卫).
4. `1110d43`: 发送拿旧存储版本 (send 前自动 saveDraft) + 发送失败吞错成未处理拒绝 (catch 后合成 done.error 展示).
5. `fbbca5d`: 单次发送断言失败无明细 (ResponseHeader 加 .failnote 首失败明细).
6. `479a829`: 集合级 ▶ 运行无入口 (根集合无树头行; 侧栏头加「运行集合」按钮).
7. `18d06c1`: **后端契约窟窿** — CLI `history list/show` 对真服务 404 (M10 ISSUE-03 假设的 GET /history / GET /history/{id} 后端从未交付, CLI 只测过 fake HTTP). 修复: GET /history (最近优先 {"entries":[...]}) + GET /history/entry/{id:path} (id=历史相对路径, entry 前缀避开 {collection}/{slug} 路由歧义); engine 历史记录捎带 env + assertions 计数; CLI 解包/逐段引用. 后端测试 255 全绿, SPA vitest 91 全绿.
8. `348e68d`+`39d037e`: 用户三诉求 — 条目可改名 (构建器顶部 input.itemname, 失焦提交, 只改显示名不改 slug) / URL 首尾空白提交即截断 / Body 默认漂亮 JSON (可切树视图 .bodyview). 保存后树显示名原地同步.

## 新记录缺口 (待用户裁定, 原三缺口之外)

- **SPA 无环境管理 UI**: 环境创建/编辑只能手写 `environments/<name>.yaml` 或调 HTTP API (属"本地文件优先"设计内路径, 本会话 env 即手写建的). 用户尚未裁定接受与否.
- **运行结果不可回看**: 集合运行只驱动树徽标 + 失败红字, 点条目不代入该次运行日志/响应 (response 面板仅 send() 写), summary 不落 UI. 现成查看路径 = 点条目重发. 2026-08-27 用户亲测 B7 时提出, 已记待裁定 (候选改动: run 事件流缓存每条目 done/chunk 或点条目读 history).
- 原三缺口裁定汇总 (2026-08-27 全部亲验后): (a) git 行 branch 静态 main 无 ahead → **接受**; (b) run 含未解析变量条目整批 exit 2 → **裁定改** (跳过语义, 方案已记下方待办 G1, 不准当场改已记录); (c) `service status` version=null → **接受** (建议项, 用户未否).
- **缺口 4 裁定: 要修** — SPA 需环境管理 UI (环境 CRUD + 切换激活), 后端已有 GET /environments + PUT /environments/{name} (写环境), DELETE 端点存疑需核; 手写 YAML 不满足用户, 待办 G2.
- **缺口 5 裁定: 要修** — 集合运行结果必须回看 (点条目带出该次运行日志/响应; 候选: run 事件流缓存每条目 meta/chunk/done 到 store 内存, 点条目展示; 或点条目拉 history 转录), 待办 G3.
- **新诉求 f: SPA 动画** — 各组件加过渡动画 (候选: Vue Transition 于树展开/弹层/徽标/响应切换, 低成本), 待办 G4.
- **新诉求 g: 弹外点击折叠** — 弹窗/下拉展开态点外部自动折叠 (候选: 全局 click-outside 指令, 覆盖 CollectionMenu/EnvMenu/VarEditor/新建弹层), 待办 G5.
- G1~G5 实现避让基线: 后端 pytest 255, SPA vitest 91, typecheck/build, dist 入库.

## 关键约束与坑 (前件未尽事宜)

- 顶层命令面无 status/token 子命令: 正确形态 `apic service status` / `apic service token`.
- 服务重启端口必变 (service.json 里的才是真端口); 重启后提醒用户换浏览器地址.
- SPA dist 入库, 改 src 后须 `cd spa && npm run build` 并提交 dist; 运行中服务直接读磁盘 dist, 浏览器强刷即可 (Ctrl+Shift+R 防 CSS 缓存).
- 测试基线: 后端 `uv run python -m pytest` (255) / SPA `cd spa && npm run test` (91) + typecheck + build.
- 环境有 SOCKS 代理变量, 真 HTTP 一律 trust_env=False (后端已处理); curl 本机要 `--noproxy '*'`.
- 子代理选型先例: 执行 kimi-coding/k3 (thinking high), 审核 opencode-go/kimi-k2.7-code (异模型对抗); 本会话自测修复多为手改 (小改动直接改更快).

## 必读推荐

1. `docs/changes/handoff/2026-08-25-m11-acceptance-handover.md` — 前件: 验收步骤 A~F 全文, AFK 12 条裁定内容 (D-AFK-005/007/009/010/011/012 重点), 原三缺口, 路线图全貌. **新会话必读**, 本文档不重复.
2. `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` — 12 条裁定原文 (M11 关闭前提 = 用户逐条复核).
3. `docs/changes/api-client/roadmap/MILESTONE-11.md` + `ROADMAP.md` — 验收目的地与关闭条件.

## 路线图

1. 起点 → 目的地: 见前件 (自用本地优先 Postman 替代品).
2. 前情: M1~10, 12 关闭; M11 验收中 — 前件会话起了服务; 本会话用户开始亲测 SPA, 连续踩出 8 类缺陷并全部修复 (含 1 个后端契约窟窿), 期间 agent 用 access-web 浏览器自测了全部 SPA 流程 + git 同步 + CLI history.
3. 当前位置: 用户已完成 B1/B2/B4; B3/B5/B6/B7 已修好待用户亲测 (可合并为紧凑步骤或按需省略 — 由用户定节奏); 之后 C → D → E → F → 裁定复核 → 关 M11 清 Roadmap.
4. 剩余距离: 功能层验收走完 + 12 条裁定复核 + 三+一缺口裁定 = 到达目的地.
