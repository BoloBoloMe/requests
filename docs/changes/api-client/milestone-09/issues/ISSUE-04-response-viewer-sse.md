# ISSUE-04: 响应查看器 + SSE 流式消费

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
右主区下半响应查看器 (变体 B), 数据源为 `POST /execute` 的 SSE 流 (M3-D007/D006):
- SSE 消费: 用 fetch (非 EventSource, 因 /execute 是 POST) 发 `Accept: text/event-stream` 请求, token 走 header (D004), 解析 ReadableStream 为 meta/chunk/done 事件流 (direction-a Q1.6 SSE 自研点). 「发送」/运行按钮触发的执行进度在头行显示 (发送中 spiner → 就绪).
- 头行 (`.r-hd`): 状态徽章 (ok/warn/err 按状态码), 元信息 (时延 ms / 大小 KB / 时刻), 断言计数胶囊 (`.asserts`).
- 三 tab (`.r-tabs`): Body / Headers / 日志.
- Body: JSON 树折叠 + 行号 + 语法着色 (vue-json-pretty 或等值实现, 原型 `.json`/`.fold`/`.ln`), 非 JSON 体裸文本降级.
- Headers: 响应头 kv 列表 (原型 `.json .k: value`).
- 日志`: 一次请求完整收发转录 — 连接元信息 (TLS/计时分解), `→` 请求行+头+体, `←` 响应行+头+原始体, 变量按当前环境解析后显示; 不脱敏 secrets (M5-D5).
- 适合 AFK: 渲染与解析逻辑由原型 + D007 事件模型确定; 真实 SSE 端到端为 HITL.

## 覆盖依据
- Technical: `../milestone-05/DECISIONS.md` 决策 3 (响应头行/三 tab/日志), 决策 5 (日志不脱敏).
- Technical: `../milestone-03/DECISIONS.md` D007 (SSE+单一 meta/chunk/done 事件模型, Accept 协商), D006 (SSE 断连不取消执行).

## 相关决策
- `../milestone-05/DECISIONS.md`: 决策 3 (响应查看器), 决策 5 (日志/历史不脱敏).
- `../milestone-03/DECISIONS.md`: D006 (执行不取消), D007 (SSE 事件模型), D004 (token 经 header 与 `?token=`).
- 术语: 执行事件流, 历史 (`../../language/UBIQUITOUS_LANGUAGE.md`).

## 允许范围
- `spa/src/components/response/` (ResponseHeader, JsonTree, HeadersView, LogView, SseParser, ResponsePane), 以及 `spa/src/api/sse.ts` (fetch 流解析), services 适配层 execute 方法 + mock 事件源.

## 禁止范围
- 不实现 runner 批量内联与 git 行 (ISSUE-05).
- 不用 EventSource (POST 不可用) 或 WebSocket (D007 排除); 不实现请求执行本身 (属后端 Engine).
- 日志/历史不脱敏 — 不引入任何脱敏逻辑 (M5-D5 明示).
- 不引入路由/账号/云; 不用 react-json-view/Shoelace (JSON 树用 Vue 生态成熟库).

## 代码定位提示
- 原型变体 B `r-hd`/`status`/`meta`/`asserts`/`r-tabs`/`json`/`fold`/`ln`/`log-out`/`log-in`/`log-meta` 为结构目标.
- JSON 树选型 `../directions/direction-a-spa.md` Q1-2 (vue-json-pretty 属 Vue 生态成熟库); SSE 消费见 Q1-6 (fetch ReadableStream 分块解析, 自研点).
- D007 事件模型 (meta/chunk/done) 定义在 `../milestone-03/DECISIONS.md`; 解析器按此形状与换行/事件边界实现.

## TDD 切片
- TS-001:
  接缝: `src/api/sse.ts` 的流解析器 (输入: 可分块的文本字节可读流 / 事件行序列; 输出: 结构化事件).
  测试用例: TC-001 把 `data:` 行序列解析为 meta/chunk/done 事件序列; TC-002 事件跨块分片 (分块边界落在行中) 仍合并为完整事件; TC-003 提取事件类型 (event:/data:).
  先写的失败测试: `SSE 解析器跨块边界合并事件` — 预期失败 (解析器未实现).
  最小绿色实现范围: 按行缓冲 + event/data 字段解析 → 事件对象队列; 输入可为字符串行数组便于单测.
  不得测试: 具体 fetch 传输 (另注入 mock).
  覆盖: RES-05.
- TS-002:
  接缝: JsonTree 组件 (折叠树渲染).
  测试用例: TC-004 渲染嵌套 JSON 并带行号; TC-005 点折叠记号收起/展开子树, 状态用路径键记录.
  先写的失败测试: `JsonTree 折叠节点后子树收起` — 预期失败 (树未实现).
  最小绿色实现范围: JSON → 带路径的节点树渲染 + 折叠状态切换 + 行号列 + 键/字符串/数字/布尔着色类.
  不得测试: 语法高亮库内部.
  覆盖: RES-02.
- TS-003:
  接缝: LogView 行构建器 (纯函数, 输入请求定义+响应+环境解析→转录行).
  测试用例: TC-006 转录含连接元信息行 + `→` 请求行/头/体 + `←` 响应行/头/体, 变量按当前环境替换; TC-007 保留 Authorization 等原值 (不脱敏).
  先写的失败测试: `日志转录保留 Authorization 原值且变量已解析` — 预期失败 (行构建器未实现).
  最小绿色实现范围: 行生成纯函数, 变量替换用 ISSUE-03 解析器, 无任何脱敏分支.
  不得测试: 后端实际时序数据.
  覆盖: RES-04 (并入 RES-05 的事件组装).
- TS-004:
  接缝: ResponseHeader 组件.
  测试用例: TC-008 状态码 <300→ok 类, 300-499→warn, >=500→err; TC-009 显示 ms/KB/时刻与断言计数胶囊.
  先写的失败测试: `500 状态渲染 err 徽章` — 预期失败 (头行未实现).
  最小绿色实现范围: 状态码→类映射 + 元信息格式化 + 断言计数随事件更新.
  不得测试: 断言结果计算 (由后端).
  覆盖: RES-01.

## 验证入口
- `cd spa && npm run test:unit -- src/components/response src/api` 通过 TS-001..004.
- 人工验证 (HITL, 依赖 MILESTONE-08 后端): 点发送后自真实 `/execute` SSE 流式渲染 Body/Headers/日志; 响应头行实时更新, 断连后执行不中断 (D006).
- 人工: `npm run dev` 用注入 mock 事件源对照原型变体 B 响应区 (Body 树折叠/行号/着色, 日志三色).

## 风险提示
- SSE 分块边界解析是主要自研点 (direction-a Q1-6) — 用行缓冲合并, 单测覆盖跨块/半行; 这是本 ISSUE 必测接缝.
- 大响应/大 JSON 渲染性能 — 折叠默认收起深层, 行号按需渲染; 不作为本 issue 性能目标, 留打磨.
- 日志不脱敏与 M5-D5 一致, 勿因"安全直觉"擅自加脱敏.

## 停止条件
- 后端 `/execute` 事件形状偏离 D007 (meta/chunk/done) 时停止并与父会话核对.
- 需引入 WebSocket 或真实执行逻辑时停止 (D007 已排除 / 属后端).

## 适合 AFK 的原因
- 渲染结构由原型 + D007 事件模型定死; 唯一自研点 (SSE 分块解析) 有明确可单测接缝. 真实后端联调独立标记 HITL.

## 验收标准
- [ ] 经 fetch 流消费 `/execute` 的 SSE, 解析为 meta/chunk/done 并提供给响应面板.
- [ ] Body 支持 JSON 树折叠/行号/着色, 非 JSON 降级裸文本.
- [ ] Headers 列表 + 头行状态徽章/元信息/断言计数达成.
- [ ] 日志 tab 呈现完整收发转录且不脱敏 secrets; 视觉对齐原型.

## 被阻塞于
- ISSUE-03 (`issues/ISSUE-03-request-builder.md`): 依赖其构造出可执行的请求定义 (方法/URL/头/体/认证/断言) 供发送与转录.
