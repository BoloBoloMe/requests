# DOGFOOD: schema+guide 自学报告

角色: 从未见过 apic 的 AI agent, 仅通过 `schema`/`guide` 子命令自学. 全过程中未读源码/README/--help.

## 一. 任务记录

### 1. 搞清楚工具能干什么
- 命令: `apic.py` (无参数) -> 失败, exit 2, stderr 报 `USAGE_ERROR no command provided`.
- 命令: `apic.py schema` -> 成功(第2次尝试即成功). 一次拿全: 命令面, 全局 --output, 事件类型(meta/chunk/done/summary), 退出码(0-4), 错误格式.
- 命令: `apic.py guide` -> 成功. 给出快速示例/命令面/输出模式/退出码/item-ref 规则/已知局限.
- 结论: 工具是**执行 API 请求的机器友好 CLI**: 执行类(send/run), 清单类(collection/item/env/history), 服务类(status/stop/token), 元类(schema/guide). 一次成功.
- 感受: schema 信息密度很高, 足以建立完整心智模型; guide 是 schema 的子集, 主要价值是快速示例与 `{{var}}` 占位符暗示.

### 2. 列出集合与 demo 条目
- 命令: `apic.py collection list` -> 成功. 唯一集合 `demo` (item_count=3).
- 命令: `apic.py item list demo` -> 成功. 3 个条目: get-json(GET /json), sse-stream(GET /stream), failing-check(GET /fail).
- 备注: 尝试 `item list` 无参数会报 USAGE_ERROR(未正式验证, 从 schema 的 path 约束推断). 一次成功.

### 3. 查看 demo/get-json 定义
- 命令: `apic.py item show demo/get-json` -> 一次成功. 返回 method/url/status/headers/body/assertions(2条: status=200, body_field hello=world).
- 旁证: `collection show demo` 内联了全部条目定义(含 sse-stream 的 stream:true/chunks/sleep), 比 item show 更全.

### 4. prod 环境执行 demo/get-json, 拿响应体
- 前置: `apic.py env list` -> dev(localhost:3000) / prod(api.example.com).
- 命令: `apic.py send demo/get-json --env prod` -> 一次成功, 默认 ndjson 3 行事件相.
  - meta: resolved_url=http://api.example.com/json, env=prod
  - chunk[0].data = {"hello":"world","list":[1,2,3]}  <- 响应体
  - done: status=200, duration_ms=10, 2 条断言全 passed, exit 0.
- 无 --env 对照: resolved_url 保持 `{{host}}` 未替换, env=null, exit 0, 无任何告警. 陷阱见文末.

### 5. 执行 demo/sse-stream, 理解流式
- 命令: `apic.py send demo/sse-stream --env prod` -> 一次成功, 按 ndjson 逐事件吐出: meta -> chunk[0]=alpha -> chunk[1]=beta -> chunk[2]=gamma -> done(150ms, 暗示流内延时).
- 对照 --output json: 全部事件打包成单个 JSON 数组一次性输出(流被缓冲, 且内层字段缩进成多行, 反而不利于流式); exit 0.
- 对照 --output pretty: 人类可读 [META]/[CHUNK] 块, 适合调试.
- 关键差异: 同一条目在 `run` 批量模式里**不发 chunk**, 只发 meta+done, 流的实际内容在批量模式下不可见.

### 6. 批量运行 demo, 找断言失败项
- 命令: `apic.py run demo --env prod` -> 一次成功. 事件序: 每个条目 meta+done, 最后 summary.
  - summary: total=3, passed=2, failed=1.
  - 失败项: demo/failing-check, 断言 body.ok expected=true actual=false passed=false.
  - exit=1 (ASSERTION_FAILED), 与 schema 一致.
- 单条验证: `send demo/failing-check --env prod` 同样 exit 1, done.assertions 里 visible false 项.

### 7. 找出服务 token
- 命令: `apic.py service token` -> 一次成功. `{"token":"stub-token-do-not-use-in-production"}`.
- 旁证: `service status` -> running/pid/port/uptime/version; `service stop` -> {"status":"stopped"}, 均为 stub.

### 8. 故意执行不存在的条目, 观察错误与纠正可能性
- 命令: `apic.py send demo/nope` -> exit 4, stderr 单行 JSON `{"error":{"code":"NOT_FOUND","message":"item not found: demo/nope"}}`, stdout 空.
- 对照: `item show ghost/nope` / `run ghost` -> 同格式, code=NOT_FOUND, message="collection not found: ghost", exit 4.
- 解析性: 错误是合法 JSON 且固定在 stderr, 退出码 4 唯一对应 NOT_FOUND, **可自动判定**.
- 自动纠错可行性: **仅凭本次错误响应无法纠错** - 无 details 字段, 无候选建议, 无 did-you-mean. 需额外查询 `collection list` + `item list demo` 才能重建合法 ref 空间. 即 1 次检测 + 2 次清单查询 + 1 次重试可自动恢复, 属于可行的两阶段方案.

## 二. schema+guide 自学充分性评分: 3/5

优点: schema 一次给出完整命令面/事件契约/退出码/错误格式, 足以无源码上手 8 个任务全部一次成功.
缺口(扣 2 分):
1. **变量替换语义未文档化**: guide 示例给了 `--var host=...`, 但未说 "不传 --env 且无 --var 时占位符原样输出且 exit 0", 这是最大陷阱, 我靠试错才确认.
2. **run 模式事件契约与 send 不一致**: schema 里 event_stream 注释用了省略号(meta/done/.../summary), 但未明示 "run 不发 chunk", 导致批量时流内容凭空消失.
3. **item-ref 合法性规则太简**: 只给了 `<collection>/<item-slug>` 格式, 没有 ref 校验器/建议; NOT_FOUND 的 details 字段始终缺席.
4. 小: schema 是自描述 JSON 但无版本号/无字段 enum(如 done 里 assertions 的 name 格式 "body.hello" 是拼出来的, 未定义).

## 三. 摩擦点清单

- `send` 无参数: exit 2, 仅 message "no command provided"(USAGE_ERROR 信息没提示可用子命令). 对照其自家 guide 有完整列表.
- 缺环境时 `send demo/get-json`: meta.resolved_url 输出 `http://{{host}}/json` 原样占位符, env=null, exit 0, 无 warning. **最危险**.
- `--output json` 对 send(流式): 输出变成单 JSON 数组且多行缩进, 流式语义完全丧失; 对 run(3 条目)同理, 需全部完成才见结果.
- `run` 批量模式吞掉 chunk: 同一条目 send 有 chunk 内容, run 只有 meta+done.
- done.assertions 的断言名格式: 状态断言叫 "status", body 断言叫 "body.hello"(点分), 但 schema 未给出命名规则, 只能观察归纳.
- 错误 JSON 固定有 message 但 details 从不出现; message 里的 ref 是拼接字符串("demo/nope"), 无结构化字段便于程序拆解.
- 无 --env / --var / 重复 --var 的合并与优先级规则未说明(--var 与 --env 同时给时谁优先, 未测出, 标未知).
- `history` 数据是静态 fixture(时间戳 2024年 与本次运行无关), 与 "stub 不持久化" 的说法一致, 但 guide 未提示 history 不可信.

## 四. 作为 AI 最希望改掉的 3 件事

1. **缺变量默认值直接失败或告警**: 占位符未解析时就应当在 stderr 出 WARNING(或直接 exit 2 + 列出缺失的 key), 而不是静默 exit 0 给 `{{host}}` 假 URL. 这是唯一会让我误以为执行成功的问题.
2. **统一 run/send 的事件契约并去掉省略号**: schema 的 event_stream 用 `"..."` 占位, 各模式行为不一致(send 有 chunk, run 没有). 要么 run 也透传 chunk, 要么 schema 明确标注 "run 模式下 stream 条目不输出 chunk", 并给一个完全重放选项(如 `run --with-chunks`)。
3. **NOT_FOUND 响应携带结构化纠错信息**: 在 error.details 里带上候选 ref(基于已知集合/条目列表, 如 `["demo/get-json","demo/sse-stream","demo/failing-check"]` 或 prefix 匹配), 让我一次调用即可自动纠正, 不必先做两轮清单查询.

## 附: 后续行动者入口

- 先读 `schema` 输出(命令/事件/退出码全契约), 再对照本报告第三/四节的摩擦点做工具设计修订; guide 只作快速示例, 不足以支撑深度使用.
- 若需修工具行为, 涉及文件为同目录 apic.py(本次未读, 属被探查对象, 禁止修改).