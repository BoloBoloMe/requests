# MILESTONE-04 决策账本 — AI CLI 外壳原型

产物归属: `docs/changes/api-client/roadmap/MILESTONE-04.md` (已关闭).
验证方式: 三轮 AI 实弹试用 (dogfood) — 每轮两名全新上下文子代理扮演 AI 用户, 分别仅经 `--help` 与仅经 `schema`+`guide` 自学, 完成 8 项任务; 摩擦点逐轮修复.
原型归档: `docs/changes/api-client/prototypes/cli-shell/` (apic.py + README.md + 四份 dogfood 报告). 一次性代码, 正式实现时参照重写, 不直接复用.

## 决策

### D001 — 命令面: 动作动词 + 资源名词组 + 元命令

- 状态: 当前有效 (原型验证)
- 内容: 动作 = `send <collection>/<slug>` / `run <collection>`; 资源管理 = `collection|item|env|history|service` 名词组下挂动词; 元命令 = `schema` (机读自描述) / `guide` (llms.txt 式文读手册). 名词/动词不对称是刻意的, 与 D010 (M3) REST+RPC 混合同构.
- 依据: 两轮 dogfood 中 9 子命令树被 agent 一次穷举, 无命名误解报告.

### D002 — 输出契约: 流式 NDJSON / 非流式 JSON / pretty 供人

- 状态: 当前有效 (原型验证)
- 内容: send/run 默认 NDJSON 逐行事件; 其余命令默认单 JSON 对象 (stdout); `--output json|ndjson|pretty`; 流式命令 json = 事件数组; 非流式 ndjson 等同 json; pretty 每行以事件 type 开头, 值用 JSON 渲染 (禁 repr). 错误永远走 stderr `{"error":{"code","message","details"}}`, stdout 保持干净.
- 依据: dogfood 中 agent 零解析错误; pretty 用 repr 曾被判摩擦, 第三轮修正.

### D003 — 事件契约: send/run 同构

- 状态: 当前有效 (原型验证)
- 内容: meta(type,timestamp,item_ref,item,method,resolved_url,env) / chunk(type,timestamp,item,index,data) / done(type,timestamp,item,status,duration_ms,assertions) / summary(type,timestamp,total,passed,failed,items). run 对每 item 发完整 meta/chunk/done, 不吞 chunk — agent 须能从 run 输出直接定位失败条目的响应体, 禁止要求重放 send.
- 依据: 首轮 dogfood 双方共指 run 吞 chunk 是最大不一致; 修正后复测确认 "只从 run 输出拿失败响应体" 任务一次成功.

### D004 — 退出码与错误模型

- 状态: 当前有效 (原型验证)
- 内容: 退出码小表 = 0 成功 / 1 断言失败 / 2 用法错误 / 3 服务故障 / 4 未找到; 机器语义在 `error.code`: USAGE_ERROR / UNRESOLVED_VARIABLES / COLLECTION_NOT_FOUND / ITEM_NOT_FOUND / ENV_NOT_FOUND / SERVICE_ERROR. NOT_FOUND 类 `details.candidates` 给候选 ref (difflib + 子串并集), 支持 agent 一次调用自动纠错.
- 依据: dogfood 任务 "拼错 ref 后只凭错误输出一次猜对" 在第三轮修正后通过.

### D005 — 可发现性: 双通道自学

- 状态: 当前有效 (原型验证)
- 内容: 通道一 `--help` 每层带示例, 顶层 epilog 含三节机器契约 (退出码表/错误码表/事件流字段列表, 与实现逐字一致); 通道二 `schema` (完整机读契约) + `guide` (文读手册). 两通道冗余是刻意的: agent 入口习惯不同.
- 依据: 复测两条路径自学充分性均 4/5; 契约与实现不一致 (help 字段名, schema 省略号) 曾是主要扣分项, 修正后核对零偏差.

### D006 — 未解析变量即硬失败

- 状态: 当前有效 (原型验证)
- 内容: send/run 解析后 URL/headers/body 残留 `{{var}}` → UNRESOLVED_VARIABLES, exit 2, details.missing 列出缺失变量, 不产生事件流; `{{$now}}`/`{{$uuid}}` 由引擎求值, 不在检查范围; `--var k=v` 覆盖环境变量.
- 依据: 首轮 dogfood 最严重发现 — 静默成功会让 agent 误判执行结果.

## 已知残留 (stub 假象, 非设计问题)

- 非流式命令 pretty 回退 JSON (未渲染表格) — 原型简化, 实现时定.
- exit 3 在 stub 中无法触发; history 为假数据 — stub 边界.
- 正式实现 backlog: candidates 匹配算法边界文档化.

## dogfood 报告索引

- 第一轮: [DOGFOOD-help-only.md](../prototypes/cli-shell/DOGFOOD-help-only.md) (4/5), [DOGFOOD-schema-guide.md](../prototypes/cli-shell/DOGFOOD-schema-guide.md) (3/5)
- 第二轮 (复测): [DOGFOOD2-help-only.md](../prototypes/cli-shell/DOGFOOD2-help-only.md) (4/5), [DOGFOOD2-schema-guide.md](../prototypes/cli-shell/DOGFOOD2-schema-guide.md) (4/5)
- 修正史: [README.md](../prototypes/cli-shell/README.md) 第二/三轮修正节
