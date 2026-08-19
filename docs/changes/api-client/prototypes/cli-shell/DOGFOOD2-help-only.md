# DOGFOOD2-help-only 报告

角色: 从未见过 apic 的 AI agent, 仅靠 `--help` 自学, 不读源码/README/任何 DOGFOOD*.md, 不用 schema/guide, 不访问外部信息源.

## 1. 工具能力与契约 (task 1)

命令轨迹 (全部一次成功):
- `apic --help` -> 顶栏明示 9 个子命令 `{send,run,collection,item,env,history,service,schema,guide}` 及退出码/错误码/事件流契约 (见下).
- 对 send/run/collection/item/env/history/service 逐一 `--help`, 对 11 个叶子子命令再 `--help`, 全部一次拿到.

能力拼图:
- send: 单条目执行, 支持 `--output {json,ndjson,pretty}`(默认 ndjson), `--env`, 可重复 `--var KEY=VALUE`.
- run: 整集合执行, 同样三项 output + `--env`.
- collection: list / show(ref); item: list(collection-ref) / show(item-ref); env: list / show(name); history: list / show(id); service: status / stop / token(stub).
- 所有子命令统一支持 `--output`, 默认值: send/run 为 ndjson, 其他无默认并落为 json 数组/对象.

契约 (仅 help 明文, 无歧义):
- 退出码: 0 OK / 1 assertion failed / 2 usage / 3 service / 4 not found, 实测与文档一致.
- 错误码: USAGE_ERROR, UNRESOLVED_VARIABLES, COLLECTION_NOT_FOUND, ITEM_NOT_FOUND, ENV_NOT_FOUND, SERVICE_ERROR; 错误输出为单行 `{"error":{code,message,details}}`, 部分带 `details.candidates`.
- 事件流 (ndjson 默认): `meta(item-ref,item,method,url,env)` -> `chunk(item,index,data)` xN -> `done(status,duration_ms,assertions)`, run 尾部追加 `summary(total,passed,failed,items)`. 输出里实测 meta 字段名实际为 `resolved_url` 而非 help 写的 `url`(兼容理解, 无碍).
- 事件均含 `timestamp`, 便于流式消费判断时序.

## 2. 列出集合与 demo 条目 (task 2)

- `collection list` -> 1 个集合 `demo`(Demo Collection, item_count 3).
- `item list demo` -> 3 条目: `demo/get-json`(GET http://{{host}}/json), `demo/sse-stream`(GET http://{{host}}/stream), `demo/failing-check`(GET http://{{host}}/fail).
- 均一次成功; URL 中暴露变量 `{{host}}` 说明依赖 env.

## 3. demo/get-json 无环境执行与自修复 (task 3)

- 第一次 `send demo/get-json` 不带 env -> `{"error":{"code":"UNRESOLVED_VARIABLES","message":"unresolved variables: host","details":{"missing":["host"]}}}`, rc=2. 未一次成功.
- 自修复: `env list` 发现两个环境 `dev(localhost:3000)` / `prod(api.example.com)`, `env show dev` 确认键为 `host`.
- 再次执行 `send demo/get-json --env dev` -> rc=0, 三分事件完整: meta+1 chunk+done,status 200, 断言 status/body.hello 全过.

## 4. demo/sse-stream 流式理解 (task 4)

- `send demo/sse-stream --env dev` 一次成功, rc=0.
- 观察: 3 个 chunk(index 0/1/2, 数据 alpha/beta/gamma) 逐条带不同时间戳(间隔约 1s, 总 duration 150ms 为累计), 非一次性灌出; 事件流模型为"元数据 + 增量块 + 收尾断言".
- 结论: 流式事件序列即可正确消费; help 未解释 chunk 的 index 语义与时间间隔, 需靠观察补足.

## 5. 批量运行定位失败项 (task 5)

- `run demo --env dev` 一次成功, rc=1 (断言失败退出码 1 与 help 契约吻合).
- 失败项定位: summary 中 `failed:1, items 含 demo/failing-check passed:false`, 且其 done 事件 assertions 显示 `body.ok expected:true actual:false passed:false`(status 断言 200 是通过的).
- 响应体获取 (未重放 send): 该条目 run 输出中的 chunk( index 0 ) 即完整响应体 `{"ok": false}`. 直接复用即可, 无需回放.

## 6. 拼写纠错 (task 6)

- `send dem/get-jsn --env dev` -> `COLLECTION_NOT_FOUND`, rc=4, 但 `details.candidates:["demo"]` 给出集合侧正确值.
- 修正集合后 `send demo/get-jsn` -> `ITEM_NOT_FOUND`, rc=4, 但 `details.candidates:[]` 为空; 结合 task-2 的 item list 已知条目名, 猜出 `get-json`.
- `send demo/get-json --env dev` -> rc=0 成功.
- 结论: dem->demo 靠错误候选一次可对; get-jsn->get-json 候选为空, 仅靠该条错误输出不足以唯一推得, 实际借助了 task-2 列表知识 + 贴近拼写直觉. 不符合"只靠错误输出一次猜中"的理想路径, 记为摩擦点.

## 7. service token (task 7)

- `service token` -> `{"token":"stub-token-do-not-use-in-production"}`, rc=0, 一次成功; help 标注为 stub.
- 顺带 `service status` 正常(有 token/pid 状态), 说明本地 stub 服务在跑.

## --help 自学充分性评分

**评分: 4/5**

充分处:
- 顶层 help 独一份地写全退出码/错误码/事件流契约, 是本次任务达成的主干; 子命令树与参数/默认值/示例均清晰, 层级完整可滚动自发现.
- 格式选项三态、repeatable --var、默认输出格式等细节都明示.

缺口 (剩余需探索/猜测):
- 事件 meta 字段实际叫 `resolved_url` 而非 help 所述 `url`; 字段名偏差在严格按契约解析时有 5 分钟级返工.
- chunk 的 index 递增与 SSE 分块时序语义 help 未提, 需实跑观察.
- env 选型依据 (键 `host` 必须存在) 与 `--var` 可覆盖 env 变量, help 只在 --var 行提了"Extra variable", 未说明其优先级与用途示例.
- 错误候选 (candidates) 的给出规则不稳定: 集合侧有, 条目侧空缺; 意味着字符串纠错不能指望工具兜底.
- 子命令默认输出 对非 send/run 其实是 json, 但 help 文本只写 "default for send/run", 其余默认值读者要试.

## 残留摩擦点清单

1. meta 事件键名与 help 描述不符 (`resolved_url` vs `url`), 契约消费者需容忍别名.
2. ITEM_NOT_FOUND 的 candidates 常为空, 拼写纠错提示只覆盖 collection 层.
3. 无环境报 UNRESOLVED_VARIABLES 只给缺失变量名, 不提示可用 env 清单/如何注入, 首次遇错需自行探索 env list.
4. SSE chunk 时间戳可跨秒, 机器消费若假设同批到达易踩 (index 字段已备好, 但未文档化).
5. 输出事件格式有 ndjson(逐行) 与 pretty([META]/[CHUNK]/[DONE] 标签) 两套, 切格式时要重建解析器, help 未给 pretty 示例.
6. `service stop` 标注 stub, 对真实服务生命周期管理语焉不详.

## 给后续行动者的入口建议

- 先跑 `apic --help` 拿到契约段 (退出码/错误码/事件流), 再按任务 2-7 顺序铺开, 与本文档结论可互相印证.
- 如需扩展解析器/断言逻辑, 入口看顶层 help 的 "Agent examples" 行与 send/run 的 --output 三态; 契约解析建议以实验输出为准源, 不要把 help 字段名当真理.