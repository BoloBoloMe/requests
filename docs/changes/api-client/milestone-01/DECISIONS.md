# MILESTONE-01 决策账本 — v1 范围界定

产物归属: `docs/changes/api-client/roadmap/MILESTONE-01.md` (已关闭).
盘问方式: deliberate skill, 三轮盘问 + 反方攻击 (子代理) + 自扫, 用户逐条确认.
跨决策的长期约束另见 ADR: [0001](../../../adr/0001-refuse-node-runtime-drop-postman-js-scripts.md), [0002](../../../adr/0002-zero-importers-one-off-migration-script.md).

## 决策

### D001 — 协议面: v1 仅 HTTP/REST

- 状态: 当前有效
- 约束性: 可调整 (成品使用后回访)
- 内容: v1 只做 HTTP/REST. GraphQL 不建专门面板, 由 body 编辑器覆盖 (本质是 POST + JSON); WebSocket/gRPC 砍出 v1; SSE 不建协议面板与专门断言, 但响应查看器必须支持 `text/event-stream` 流式渲染 (引擎零改动, 渲染层一个分支).
- 理由: 自用调试 HTTP 占绝对大头; WS 双向帧/gRPC protobuf 工具链成本远超收益; SSE 实为 HTTP 流式响应, 砍的是渲染能力而非协议, 渲染成本极低且用户调试 LLM 流式接口概率高 (反方攻击 + 自扫双源确认).
- 预计影响: 请求引擎 (httpx), SPA 响应查看器, CLI 输出.
- 相关 issue: 待关联

### D002 — SSE 回访触发条件

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 迷雾区 "实时协议二期形状" 的回访触发条件写死: 首次需要调试 SSE 端点且 curl/现有能力不够用达两次以上 → 立项.
- 理由: 反方攻击指出 "留待回访" 标准模糊会导致永远不回访.
- 预计影响: ROADMAP 未决迷雾条目.
- 相关 issue: 待关联

### D003 — 认证矩阵: 五种进 v1

- 状态: 当前有效
- 约束性: 可调整
- 内容: v1 认证面板仅 none / basic / bearer / apikey / digest.
- 理由: httpx 原生或近原生支持, 成本极低, 覆盖自用主流场景.
- 预计影响: 认证模块, SPA 认证面板.
- 相关 issue: 待关联

### D004 — 砍 oauth2 交互式流程, client_credentials 走配方

- 状态: 当前有效
- 约束性: 可调整
- 内容: oauth2 授权码/设备码流程砍出 v1 (浏览器交互成本高); client_credentials 不建面板, 由标准配方覆盖: 集合内建一个 token 请求 + 业务请求用 `{{var}}` 插值取 token; 配方写入使用文档; 手动粘贴 bearer 作为最终逃生舱.
- 理由: 反方攻击 (高置信度): "砍 oauth2" 整体表述过宽, 贵的只是交互式流程; client_credentials 是纯 HTTP POST, 用 v1 已有能力免费覆盖, 可消除 token 过期的手工中断.
- 预计影响: 使用文档; 无专门代码.
- 相关 issue: 待关联

### D005 — 冷门签名认证砍掉, 逃生舱 = 手写 header

- 状态: 当前有效
- 约束性: 可调整
- 内容: ntlm / hawk / edgegrid / awsv4 / oauth1 全部不进 v1; 需要时手写 header.
- 理由: 冷门, 逐个实现成本高; 手写 header 逃生舱真实存在.
- 预计影响: 无 (不做的事).
- 相关 issue: 待关联

### D006 — 零导入 (产品内)

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 产品无任何导入器; hurl 迁移 = 一次性外挂 Python 脚本 (分析 hurl → 生成数据文件), 用完即弃. 见 [ADR 0002](../../../adr/0002-zero-importers-one-off-migration-script.md).
- 理由: 用户陈述: 曾用 Postman 现用 hurl, 集合未来从业务现场手建; 内建导入器维护成本远超一次性事件的价值.
- 依赖事实: F001
- 预计影响: 数据格式设计 (MILESTONE-02); 未来的转换脚本 (仓库内工具, 非产品).
- 相关 issue: 待关联

### D007 — 数据格式三条防腐蚀约束 (输入给 MILESTONE-02)

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: (a) 数据格式 v1 即写显式 `version` 字段; (b) 格式演进责任在读侧向后兼容, 不保证老转换脚本能再跑; (c) 转换脚本必须输出未转换条目清单, 禁止静默跳过, 转换结果人工抽查.
- 理由: 反方攻击 (高置信度): "脚本可生成" 只约束写侧, 无版本号则 v1.1 连老格式批次都识别不了, 是唯一确认有不可逆成本的点.
- 预计影响: MILESTONE-02 数据存储与集合格式.
- 相关 issue: 待关联

### D008 — 砍 Postman JS 脚本, 断言结构化, 拒绝 node

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 不兼容 Postman prerequest/test JS 脚本; 断言 = 结构化 DSL (jmespath 取值 + 比较符 + jsonschema 整体校验); 拒绝 node 子进程; 无通用可编程钩子. 见 [ADR 0001](../../../adr/0001-refuse-node-runtime-drop-postman-js-scripts.md).
- 理由: 方向侦查结论 + 反方攻击确认; JS 语义仿真是无底洞; DSL 覆盖断言约 80% 场景.
- 依赖事实: F002
- 预计影响: 断言引擎 (MILESTONE-06 原型), 请求引擎.
- 相关 issue: 待关联

### D009 — 变量系统: 插值全字段 + 两级来源

- 状态: 当前有效
- 约束性: 可调整
- 内容: `{{var}}` 字符串插值在 url / params / headers / body / auth 全字段生效; 两级来源: 集合变量, 环境变量, 环境覆盖集合; 环境可切换; 砍全局变量层 ("默认环境" 可扮演).
- 理由: 与 Postman/hurl 心智模型一致, 迁移摩擦小; 自用环境数量少, 两级够用 (反方攻击未找到强反方).
- 预计影响: 变量解析引擎, 数据模型 (MILESTONE-02), SPA 环境切换 UI.
- 相关 issue: 待关联

### D010 — 动态变量白名单: `{{$now}}` + `{{$uuid}}`

- 状态: 当前有效
- 约束性: 必须遵守 (v1 内不扩展)
- 内容: 变量系统内建两个无参动态变量: `{{$now}}` (ISO 时间戳), `{{$uuid}}`; 白名单制, 无参, 无嵌套, 无表达式; 文档写死 "v1 仅此两个, 不接受扩展". HMAC 签名等超出场景手动外部生成粘贴, 高频命中再立项.
- 理由: 反方攻击最强论点 (高置信度, 与自扫独立重合): 砍 prerequest + 砍动态变量叠加 = 请求时计算能力归零, 两决策替代方案互相击穿; 恢复成本数小时; 白名单边界防 JS 钩子借壳还魂.
- 预计影响: 变量解析引擎, 使用文档.
- 相关 issue: 待关联

### D011 — 测试后端随仓库

- 状态: 当前有效
- 约束性: 可调整
- 内容: v1 包含一个随仓库的自研测试后端服务; 定位 = 开发夹具而非产品功能, `uv run` 可起, 兼任 dogfooding 对象与 demo; 覆盖面 = v1 全部能力面: echo/CRUD, 五种认证端点, SSE 流式端点, 动态值校验端点 (验证 `{{$now}}`/`{{$uuid}}`), 错误/超时/大响应等边界场景; 技术选型留给对应 Milestone.
- 理由: 用户陈述: 无外部目标 API, 需自建测试对象; 它是断言原型, runner 与 SPA 开发的公共靶子, 无它则各下游 Milestone 各自糊测试对象.
- 依赖事实: F001
- 预计影响: 新 task Milestone (MILESTONE-12); 断言原型 (MILESTONE-06), runner, SPA 开发.
- 相关 issue: 待关联

## 事实

### F001 — 用户无外部目标 API; 曾用 Postman, 现用 hurl

- 状态: 当前有效
- 来源: 用户陈述 (MILESTONE-01 盘问第 2/4 轮)
- 内容: 用户没有要调试的既有 API 清单; 历史工作流: Postman → hurl 脚本 → 未来迁到本工具; 迁移是一次性事件. 因此 v1 需要自研测试后端作为开发与 dogfooding 对象 (见 D011), 且产品零导入器 (见 D006).

### F002 — Postman JS 脚本无法在纯 Python 执行

- 状态: 当前有效
- 来源: 方向侦查报告 `docs/changes/api-client/directions/direction-c-reuse.md`
- 内容: Postman prerequest/test 脚本为 JS, Python 侧无直接执行能力; 兼容须引入 node 子进程. 这是 D008 的核心事实依据.

### F003 — httpx 能力覆盖 v1 执行层需求

- 状态: 当前有效
- 来源: 方向侦查报告 `docs/changes/api-client/directions/direction-c-reuse.md` (httpx 0.28.1 官方文档)
- 内容: httpx 覆盖 sync+async, HTTP/2, 流式响应 (`iter_lines` 等, 支撑 D001 的 SSE 流式渲染), basic/digest 认证, SSL/mTLS, 代理, 严格 timeout. 是 D001/D003 的可行性前提.
