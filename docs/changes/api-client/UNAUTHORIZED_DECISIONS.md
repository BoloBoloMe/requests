# AFK 模式自主决策账本

规则: 每条含 问题/决策/理由/影响/风险 五项. 来自 tdd-as-orchestra skill 的 AFK 授权.

## D-AFK-001 — D005 `token` 子命令归属 MILESTONE-10

- 问题: 审核发现 ISSUE-01 实现缺少 D005 要求的 CLI `token` 子命令 (显示/复制当前 token); ISSUE-01 覆盖依据含 D005, 但任务书正文与验收标准均未列该命令.
- 决策: 不补. `token` 子命令属 CLI 命令面, 按 EXECUTION.md 全局禁止范围 "不实现 CLI 命令面 (MILESTONE-10)", 留到 MILESTONE-10 实现, 并确保 M10 对齐 D005.
- 理由: EXECUTION.md 明文将 CLI 命令面整体划归 M10; ISSUE-01 对 D005 的覆盖 = `--host` 语义与 serve/stop 定位, 任务书验收标准未提 token 子命令.
- 影响: M10 任务书需包含 `apic token` 子命令; 已在交接协调点之外新增一条 M10 待办.
- 风险: M10 实现时遗漏该命令 → 在 M10 EXECUTION 的风险节补记一条.

## D-AFK-002 — ready 检查地址硬编码 127.0.0.1 接受

- 问题: launch._check_ready 硬编码 127.0.0.1; 若用户 `--host ::1` 手动起服, ensure_running 的 ready 检查连不上.
- 决策: 接受现状, 记录限制. D005 明示 `--host` 仅服务本机回环变体, 默认绑定 127.0.0.1 是唯一常态路径.
- 理由: 自用单机场景, ::1 手动起服 + CLI 幂等拉起同用属边缘中的边缘; 修复 (从监听地址推导) 成本大于当前收益.
- 影响: 无代码变更; 若日后遇到 ::1 起服 + ensure_running 场景, 回访修复.
- 风险: 低. 行为可预期 (报错含原因, 不悬挂).

## D-AFK-004 — ISSUE-02 CRUD API 形状裁定 (M10 须对齐)

- 问题: ISSUE-02 任务书未钉死 kv 键名/multipart 字段/请求体与列表响应形状, 执行者按 D009 措辞与 REST 惯例裁定.
- 决策: 采用执行者裁定并记为 API 事实: kv 列表键 `key/value/disabled`; multipart 文件键 `contentType`; env PUT 体 `{"vars":...}`; secrets PUT 体 `{"secrets":...}`; state 体 `{"active_environment":...}`; GET /collections → `{"collections":[...]}`; GET /collections/{c}/items → `{"items":[{"slug",...条目字段}]}`; 空集合配置 `_collection.yaml` 不存在时读为空配置不 404, 集合目录不存在才 404.
- 理由: 任务书/账本无更细形状约定; 这些形状即 M10 CLI 对齐基准 (EXECUTION 协调点 1-3 同族).
- 影响: M10 与 M09 (SPA store 层) 按此形状对接; 若后续发现形状问题须改 API, 属新决策, 报 HITL.
- 风险: 低-中. 形状一旦被 M09/M10 消费, 改动成本上升; 故此处显式记录.

## D-AFK-005 — ISSUE-03 done.error 字段授权 (M4 D003 事件契约扩展)

- 问题: 审核发现 done 事件新增可选 error {code,message} 字段, M4 D003 事件契约未列; 但 ISSUE-03 验收标准要求超时/大小上限可观察 (TC-009/TC-010 钉死), 契约与验收存在账本内部冲突.
- 决策: 保留 done.error (可选, 仅传输失败时出现, 既有字段不变): error.code ∈ TIMEOUT/RESPONSE_TOO_LARGE/REQUEST_FAILED/UNEXPECTED_ERROR, 失败时 status=null. 记录为 ISSUE-03 授权的执行裁定; M11 验收时提请修订 M4 D003 或 ADR 注明.
- 理由: 无错误位的 done 无法满足验收标准; 不改则超时/超限原因在事件流里丢失; 可选字段不破坏既有消费者.
- 影响: Runner (ISSUE-05) 与 CLI (M10) 可消费 error.code; SPA (M09) 可展示失败原因; 下游 schema 同步.
- 风险: 低. 若 HITL 否决, 回退成本 = 移除字段 + 改 4 处测试断言.

## D-AFK-006 — ISSUE-03 审核建议处置 (defer 清单)

- 问题: 审核提出 7 条建议级发现, 均不阻塞.
- 决策: 全部接受并分派: (1) Accept 协商 q 值简化语义 (含 text/event-stream 即 SSE, 否则 NDJSON) — 在 ISSUE-04 接线时于 execute.py 加注释钉死简化语义; (2) 历史文件名并发覆盖风险 (微秒级并发同 slug) — 接受, Runner v1 顺序执行无并发, M11 后回访; (3) multipart 重复 part 名折叠 — 接受为已知行为 (httpx 0.28 data 需 dict); (4) part 路径解析重复/5) _write_history 参数过多/6) _run 过长 — 属重构, defer 到后端稳定后; (7) execute 路由不 await task 产生的异常未 retrieve 噪音 — ISSUE-04 接线时于路由补 await task (与断连不取消不冲突, 排干后再 await).
- 理由: 均为 Standards 级, 不影响验收与行为正确性.
- 影响: 无行为变化; ISSUE-04 执行者须在允许范围内顺带处理 (1)(7).
- 风险: 低.

## D-AFK-007 — ISSUE-04 执行裁定 (done.status 三态/actual null/块标量泛化)

- 问题: 任务书只要求 done.status 标记断言失败, 未给字面值; schema/python 通过时 actual 取值未定; 块标量 representer 作用域未定.
- 决策: (a) done.status 三态: 传输成功且断言全过 → HTTP 状态码 int; 传输失败 → null + error 字段; 断言任一失败 → 字符串 "assert_failed"; (b) schema/python 断言通过时 actual=null (保证 NDJSON 可序列化); (c) store 块标量 representer 作用于全部多行字符串字段 (M6 决策 2 的合理泛化, 往返语义不变).
- 理由: 任务书未钉死字面值, 需最小自洽选择; 三态可被 Runner/CLI/SPA 无歧义消费.
- 影响: M10 CLI 错误模型与 M09 SPA 状态展示按三态对齐; Runner 统计 = assertions ok 计数 + done.status != "assert_failed".
- 风险: 低-中. 若 HITL 偏好不同字面值 (如数字失败码), 改动点集中在 engine.done_event 与消费方判别处.

## D-AFK-008 — ISSUE-05 执行裁定 (summary 口径/report 形状/env 参数)

- 问题: M4 D003 未钉死 summary.items 细节; run 的 env 选择方式未定; JUnit errors 计数口径未定.
- 决策: (a) summary 口径: passed = done.status 为 int 且非 "assert_failed"; failed = 断言失败或传输失败; items = [{item, status, passed}]; (b) report 事件 = {type:"report", format:"junit", content:<XML 字符串>}, 附 summary 之后; XML 根为裸 testsuite (pytest --junitxml 兼容), errors 计传输失败条目; (c) POST /collections/{c}/run 支持 `?env=` 查询参数, 缺省读激活环境 (与 /execute 一致).
- 理由: 账本未钉死, 取最自洽形状; M10 CLI 按此消费.
- 影响: CLI run 输出渲染与退出码 0-4 映射 (M4 D001) 以此为依据; SPA runner 徽标统计同源.
- 风险: 低.

## D-AFK-009 — ISSUE-05 单条目意外异常不中断整批 + 空集合语义

- 问题: 审核发现 engine UNEXPECTED_ERROR 会中断整批 (无 summary/report, run API 可能 500), 与批量"失败不中断"语义冲突; 空集合行为未定义.
- 决策: (a) runner 对单条目 execute 做异常隔离: 意外异常 → 该条目记传输失败结果 (failed, error 信息透传), 继续后续条目, summary/report 正常收尾; (b) 空集合 → 200 + summary total=0 + 空 testsuite 报告, 不 404.
- 理由: 批量工具的直观语义 = 单条目任何失败不拖垮整批; 空集合属合法状态, 稳定返回空报告最小自洽.
- 影响: run API 不再因单条目畸形定义返回 500; M10 CLI 退出码映射据此.
- 风险: 低.

## D-AFK-010 — ISSUE-06 执行裁定 (bind 幂等/dirty 语义/错误映射/git 环境隔离)

- 问题: 任务书未钉死 bind 幂等性/commit 消息/.gitignore 合并; TC-006 "dirty 停止"与 TC-003 "未提交改动经 add -A 提交"字面矛盾; 错误码映射未定.
- 决策: (a) bind 幂等: 已 init 且 origin 一致 → 只补缺失 .gitignore 行与初始 commit; origin 不同 → SyncError 明确报错不擅自改绑; (b) commit 消息: 初始 "init: 绑定数据仓库", 同步 "sync: <UTC ISO 时间戳>"; (c) .gitignore 精确行合并仅追加缺失行, 不覆盖用户内容; (d) dirty 语义 = add -A 无法安全处理的态 (未合并路径 UU/rebase|merge 中途态) → 即停; 普通未提交改动是 add -A 的正常输入 (与 TC-003 一致), 化解任务书内部矛盾; (e) 错误映射: bind 失败→400, sync 失败 (未绑定/冲突/dirty)→409, detail 原样携带 git 输出; (f) git 子进程 LC_ALL=C + 隔离全局配置, 输出仍原样透传.
- 理由: 最小自洽化解账本空白与任务书矛盾; D009 未触碰 (绝无自动合并).
- 影响: CLI 不接管 git (既定约束), SPA 同步按钮按 400/409 展示; M10 无 git 面.
- 风险: 低. (d) 若 HITL 认为未提交改动也应停止, 改 precheck 一处即可.

## D-AFK-012 — 08 协调补丁 2: GET /environments 列表端点 (M10 env list 契约)

- 问题: M10 ISSUE-04 任务书列举 GET /environments 列表端点, 08 ISSUE-02 实际只交付 GET/PUT /environments/{name}; CLI env list 对真服务 404.
- 决策: 08 侧补 GET /environments → {"environments":[name,...]} (扫 environments/*.yaml, 排除 *.secrets.yaml), 补测试; 入 M10 契约协调补丁序列 (前置: e02e4bf vars).
- 理由: 与 M3 D010 资源 CRUD 惯例一致, 补丁最小; 不依赖它则 CLI env list 只能 404 兜底.
- 影响: M10 env list 对真服务可用; candidates 兜底 (difflib + inventory) 也可用真清单.
- 风险: 低.

## D-AFK-003 — Accept 头子串匹配留待 ISSUE-03 协商落地

- 问题: security.py 用 `"text/event-stream" in accept` 子串匹配决定 SSE query token 副通道是否生效.
- 决策: 当前不改; 在 ISSUE-03 (Accept 协商正式落地) 时按 media type 解析重构.
- 理由: 当前服务无 /execute 端点, 子串匹配无实际风险面; 协商逻辑属 ISSUE-03 边界.
- 影响: 无; ISSUE-03 执行者须注意.
- 风险: 低. 副通道仍需有效 token, 不构成认证绕过.

## D-AFK-011 — 08 协调补丁: execute/run 请求体 vars 覆盖层 (补记, 2026-08-27 M11 复核时用户接受)

- 问题: M10 ISSUE-04 任务书要求 execute/run 请求体可携带 vars (CLI --var 依赖, 一次性覆盖), 08 侧请求体只有 env 无 vars; 该补丁 (e02e4bf) 执行时未同步落账本, M11 复核发现缺失, 现补记.
- 决策: 08 补 execute/run 请求体 {env?, vars?}; vars 为一次性覆盖层 (D-AFK-011), 透传 build_request, 优先级最高 (高于环境 vars/secrets 合并视图与集合 vars); 与 D-AFK-012 (GET /environments) 同为 08 协调补丁序列, vars 为前置.
- 理由: CLI --var 契约依赖该层; 不补则 CLI 的 vars 覆盖对真服务失效 (只对 fake HTTP 生效).
- 影响: M10 CLI --var 对真服务可用 (M11 亲测: send smoke/vars --var api_token=demo-token → 200); 请求体形状 {env?, vars?} 成为 contract 事实.
- 风险: 低. 2026-08-27 M11 验收用户复核 12 条全部接受.
