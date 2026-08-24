# ISSUE-05: runner 内联 + git 行

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
连接既有面 (ISSUE-02 树 + ISSUE-03/04 构建与响应) 完成两个闭环:
- **runner 内联 (M5-D3 决策 3)**: 文件夹头悬停出「▶」运行 (`.f-hd .run`), 调 `POST /collections/{x}/run` (D010 RPC), 结果内联于树 — 每个请求条目三态徽标 (✓ 通过 / ✗ 失败 / · 未运行, 运行中 ◌ spinner), 文件夹头计数徽章 (通过数✓/失败数✗). 失败条目下内联红字明细 (`failnote`: 首条失败断言 target/why/实际值), 点击红字/条目跳转到该请求的「断言」tab (关联 ISSUE-03 断言展示) 并定位到失败行.
- **git 行 (M5-D2 决策 2)**: 侧栏底部单「同步」按钮 + 状态 (`⎇ main ↑N` dirty 或 ✓ 已同步 synced, 同步中 …. `), 调 `POST /git/sync` (D010 RPC); 语义为一键 pull+push 合并式, 不暴露远端细节; 同步失败 (冲突/dirty) 按 D009 冲突即停, 展示后端原样输出供手工处理.
- 适合 AFK: 交互皆由原型变体 B + D010/D009 确定; 真实 git 同步为 HITL.

## 覆盖依据
- Technical: `../milestone-05/DECISIONS.md` 决策 3 (runner 内联三态徽标/红字明细), 决策 2 (git 极简单按钮).
- Technical: `../milestone-03/DECISIONS.md` D010 (RPC `/collections/{x}/run`, `/git/sync`), D009 (冲突即停, 原样输出给用户).

## 相关决策
- `../milestone-05/DECISIONS.md`: 决策 2, 3 (runner 形态).
- `../milestone-03/DECISIONS.md`: D009 (Sync 冲突即停), D010 (RPC 端点), D007 (批量结果为事件流).
- 术语: 集合/请求条目/断言 (`../../language/UBIQUITOUS_LANGUAGE.md`).

## 允许范围
- `spa/src/components/sidebar/` 中 runner 树徽标与红字明细组件, GitRow 组件, services 适配层 run/sync 方法 + mock 事件源, 相关 store.

## 禁止范围
- 不在 SPA 内实现批量执行调度/断言求值/JUnit 报告 (属后端 Runner/Assert); SPA 只消费 `run` 的事件流并渲染.
- 不做自动合并/分支管理 UI (D009 冲突即停; 只展示后端 git 原样输出).
- 不暴露远端地址/pull/push 分离入口 (M5-D2).
- 不做多页面路由/账号/云.

## 代码定位提示
- 原型变体 B 树区 `.st`/`.count`/`.failnote`/`.run`, git 行 `.git`/`.branch`/`.up`/`.synced`/`.btn`, 及 `runFolder`/`stIcon`/红字 note 的交互 (点击跳断言) 为结构与事件目标.
- D009 冲突语义与 D010 RPC 端点定义在 `../milestone-03/DECISIONS.md`; runner 事件流沿用 D007 事件模型 (批量 run 复用之).
- 复用 ISSUE-02 树渲染与 ISSUE-03 断言 tab 定位 (跳转传选中条目 + 断言高亮).

## TDD 切片
- TS-001:
  接缝: RunnerInline 组件 (树徽标 + 红字明细), 注入 mock run 事件流.
  测试用例: TC-001 运行中条目显 ◌ spinner; 完成后通过→✓ 失败→✗; 文件夹头计数徽章正确累计.
  先写的失败测试: `文件夹运行后条目失败显示 ✗ 且计数为失败数` — 预期失败 (runner 内联未实现).
  最小绿色实现范围: 订阅 mock run 事件流 → 逐条目更新三态徽标 + 文件夹计数; 运行中态.
  不得测试: 后端批量调度细节.
  覆盖: RUN-01.
- TS-002:
  接缝: 失败明细跳转 (FailNote → 选中条目 + 断言 tab).
  测试用例: TC-002 点失败红字后, 上下文选中失败条目且断言 tab 置为高亮并显示该断言行; 红字内容含 target/why/实际值首个失败断言.
  先写的失败测试: `点击失败红字定位到该请求断言` — 预期失败 (跳转与明细未实现).
  最小绿色实现范围: 由首条失败断言生成 `✗ target why, 实际 actual` 文案 + 点击回调 (选中条目 + 断言 tab 激活).
  不得测试: 断言求值.
  覆盖: RUN-01.
- TS-003:
  接缝: GitRow 组件 + sync 适配调用.
  测试用例: TC-003 初始 dirty 显示 `⎇ main ↑N`, 点同步→同步中 (禁重复点击), 成功→`✓ 已同步`; TC-004 同步失败 (返回冲突/dirty 错误) 展示后端原样错误文案且按钮可重试.
  先写的失败测试: `同步成功态从前端状态转为已同步` — 预期失败 (git 交互未实现).
  最小绿色实现范围: 状态机 dirty/syncing/synced/failed + 调 mock sync 服务 + 错误文案展示; 提交/拉取/推送到后端.
  不得测试: 真实 git 内部.
  覆盖: RUN-02.

## 验证入口
- `cd spa && npm run test:unit -- src/components/sidebar` 通过 TS-001..003.
- 人工验证 (HITL, 依赖 MILESTONE-08 后端): 文件夹运行后真实 `/collections/{x}/run` 结果内联于树; git 行真实 `/git/sync` 后同步状态更新.
- 人工: `npm run dev` 对照原型变体 B runner 内联徽标/红字明细与 git 单行.

## 风险提示
- 运行中的并发保护: 同一文件夹重复运行应忽略或排队 (原型 `if (f.running) return`); 每条目状态更新要幂等.
- 失败跳断言需与 ISSUE-03 断言 tab 的选中/高亮协议对齐 — 定义稳定的选中条目 + 断言定位消息, 避免跨组件耦合.

## 停止条件
- 需在 SPA 内实现批量执行或自动冲突合并时停止 (违反模块边界/D009).
- 需暴露 pull/push 分离或远端地址时停止 (M5-D2).

## 适合 AFK 的原因
- runner 内联与 git 单按钮交互由原型变体 B + D009/D010 完整确定; 唯一 HITL 项为真实后端联调, 已独立标记.

## 验收标准
- [ ] 文件夹「▶」触发 run, 条目三态徽标与文件夹计数徽章随事件流更新.
- [ ] 失败条目下红字明细 (target/why/实际), 点击跳对应请求断言 tab 并定位.
- [ ] 侧栏底部单「同步」按钮 + 状态 (dirty/syncing/synced/failed), 失败展示后端原样错误.
- [ ] 视觉对齐原型变体 B 的 runner 内联与 git 单行.

## 被阻塞于
- ISSUE-04 (`issues/ISSUE-04-response-viewer-sse.md`): 依赖其 SSE 消费与响应渲染, 使文件夹 run 的结果事件可驱动树徽标与失败明细.
