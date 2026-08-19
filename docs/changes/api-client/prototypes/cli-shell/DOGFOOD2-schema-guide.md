# DOGFOOD2: 仅凭 schema + guide 自学 apic 的报告

角色: 未见源代码的 AI agent, 只通过 CLI 的 `schema` / `guide` 子命令自学, 全程未读源码/README/其他 DOGFOOD 文档, 未使用 --help.

## 任务1: 工具能力 + send 事件流解析计划(离线写, 再实跑验证)

### 工具能力总览
表单目: 执行类 (`send <item-ref> [--env] [--var]`, `run <collection-ref> [--env]`), 清单类 (`collection list/show`, `item list/show`, `env list/show`, `history list/show`), 服务类 (`service status/stop/token`), 元命令 (`schema`, `guide`). 默认输出: send/run 为 `ndjson` 流, 其余为 `json`. 有全局 `--output` (json/ndjson/pretty) 可覆盖. 5 档退出码 (0/1/2/3/4), 出错时 stderr 输出 `{"error":{code,message,details}}`.

### 离线解析计划 (仅基于 schema)
send 事件流 = 顺序三事件:
1. `meta` (恰 1 个): type="meta", timestamp=ISO-8601 UTC, item_ref 与 item 均为 `<collection>/<item-slug>`, method=HTTP 方法, resolved_url=变量替换后的 URL, env=环境名或 null.
2. `chunk` (≥1 个, 流式条目多个): type="chunk", timestamp, item, index=自 0 起的块序号, data=任意载荷(串或对象, 即响应体).
3. `done` (恰 1 个): type="done", timestamp, item, status=HTTP 状态码(整数), duration_ms=整数, assertions=list of {name, expected, actual, passed}.
退出码语义: 0=全过, 1=断言失败但数据正常产出, 2=用法错误/unresolved, 3=服务错误, 4=资源不存在. 解析者按行拆 ndjson; 出现断言失败仍能拿到完整数据.

### 验证结果: 计划准确
实测 `send demo/get-json --env dev` 输出 3 行事件: meta(6 字段全命中) -> chunk(index=0, data 为 JSON 对象 {"hello":"world","list":[1,2,3]}) -> done(status=200, duration_ms=10, assertions 2 条全 passed). run 中 sse-stream 出 3 个 chunk (index 0/1/2), 验证 "一个或多个 chunk/流式多个" 的假设. 计划与实际零偏差.

## 任务2: 集合与条目清单
命令: `collection list` / `item list demo` / `env list`
- 集合: 1 个, `demo` (name "Demo Collection", item_count 3).
- 条目: `demo/get-json` (GET http://{{host}}/json), `demo/sse-stream` (GET {{host}}/stream), `demo/failing-check` (GET {{host}}/fail).
- 环境: `dev` (host=localhost:3000), `prod` (host=api.example.com).

## 任务3: 无环境执行 demo/get-json 并修正
命令: `send demo/get-json` -> 无事件流, stderr 输出 `{"error":{"code":"UNRESOLVED_VARIABLES","message":"unresolved variables: host","details":{"missing":["host"]}}}`, 退出码 2. 与 guide 预言完全一致 (URL 残留 `{{host}}` -> 退出 2, 无正常事件流; stdout 为空已验证).
修正: `send demo/get-json --env dev` -> exit 0, 事件流正常 (meta 中 resolved_url 已替换为 http://localhost:3000/json, env="dev").

## 任务4: 批量运行找出失败断言 + 从 run 输出取响应体
命令: `run demo --env dev` -> exit 1. 事件流 = 每个条目依次 meta/chunk/done, 末尾 summary(total=3, passed=2, failed=1, items 列表).
- 失败者: `demo/failing-check`, done.assertions 中 `body.ok` 断言 failed (expected true, actual false).
- 响应体 (未重放 send, 仅从 run 该条目的 chunk 事件取得): `{"ok": false}`. chunk.index=0 单块, 与 got-json 同构.

## 任务5: 拼写错误 send 一次性猜出正确 ref
命令: `send dem/get-jsn` -> stderr `COLLECTION_NOT_FOUND` (exit 4), details.candidates=["demo"].
按候选改集合后尝试 `send demo/get-jsn` -> `ITEM_NOT_FOUND` (exit 4), 但 details.candidates 为 **空** (尽管真实条目 demo/get-json 与此仅差一个字符).
结论: 条目级候选在此输入下未触发; 利用任务2 已知库存 + 首条错误的集合候选, 一次猜出 `send demo/get-json --env dev` -> exit 0, 成功.

## 任务6: 服务 token
命令: `service token` -> `{"token": "stub-token-do-not-use-in-production"}`, exit 0 (stub, 与 schema/guide 标注一致).

## 任务7: schema 契约 vs 实际行为核对表
| 项目 | schema 声明 | 实测 | 一致性 |
|---|---|---|---|
| send/run 默认输出 ndjson | 是 | 是 | 一致 |
| 其他命令默认 json | 是 | 是 | 一致 |
| 出错走 stderr, 无事件流 | 是 | stdout 为空, stderr 有 error 对象 | 一致 |
| 退出码 0/1/2/4 | 是 | 全部复现 (0 成功, 1 run 断言失败, 2 UNRESOLVED_VARIABLES/USAGE_ERROR, 4 三种 NOT_FOUND) | 一致 |
| 退出码 3 SERVICE_ERROR | 是 | 未触发, 无引发手段 | 未验证 |
| meta 字段集 | 6 项 | 全部出现, item_ref==item | 一致 |
| chunk index 从 0 起 | 是 | sse-stream 为 0,1,2 | 一致 |
| done.assertions 元素结构 | {name,expected,actual,passed} | 一致 | 一致 |
| summary 结构 | {total,passed,failed,items} | 一致 | 一致 |
| --output json | "Single JSON object" | send/run 输出**事件数组**, 列单类命令经 --output ndjson 仍输出普通 JSON 数组 (非 ndjson) | **差异(措辞)** |
| --output pretty | 人可读调试文本 | send 输出了 [META]/[CHUNK]/[DONE] 分节文本, 无 type 字段名(用节名代替) | 一致(未机器安全, 符合描述) |
| --var 单独使用 | 允许 | `--var host=127.0.0.1:9999` 生效, env=null | 一致 |
| 错误 candidates 提示 | 尽量给出相近 ref | 集合级/部分条目级给了; `get-jsn` 对 `get-json` 未给候选, 而 `json` 对 `get-json` 给了; 算法非编辑距离 | **差异(能力不匀)** |
| history | 记录近期执行 | 固定假数据 h-001/h-002, 与本次运行无关 | 一致 (guide 明言不持久化, 可视为 stub 语义) |
| service status/stop/token | stub | 均返回并 exit 0 | 一致 |

主要差异归纳:
1. "--output json" 对 send/run 产出事件**数组**而非单个对象; "--output ndjson" 对列单/展示命令被静默接受但无效 (仍输出普通 JSON 数组). 该类静默忽略易误导脚本.
2. 错误候选建议算法只对部分输入生效: 编辑距离为 1 的 `get-jsn` 候选为空, 而 `json` 却能命中; 对任务5 场景, 纯靠错误输出无法固定到正确条目, 需要额外库存信息.

## 自学充分性评分
- 总评: **4/5**. schema+guide 足够支撑全部 6 项任务完成: 事件结构, 退出码, 错误格式, 变量/环境机制, 命令面 全部可离线推导并验证准确; 指引中的 caveat (stub, UNRESOLVED_VARIABLES 行为, run 的 chunk 契约) 与实测逐项吻合.
- 剩余缺口: (a) 错误候选算法的适用边界未文档化, 导致无法预判 candidates 何时为空; (b) --output 对非流式命令的"静默无效"未注明; (c) 无明确方法触发 SERVICE_ERROR (exit 3) 做端到端验证; (d) history 为假数据这点仅能从 "no state is persisted" 推断, 字段结构未进 schema.

## 残留摩擦点
1. 条目级错拼时 candidates 空, 逼用户依赖清单命令兜底, 有违 "错误输出自足" 的设计意图 (建议对编辑距离≤2 的条目补候选).
2. --output 对不适用命令静默接受, 应拒绝或明确报错以免脚本误判 (本次实测 collection list --output ndjson 返回普通 JSON, 与模式名不符).
3. meta 中 item_ref 与 item 完全重复, 字段冗余; pretty 模式为省字符省略 type 字段, 若有人把 pretty 当半结构化解析会踩坑.

## 建议后续阅读入口
先看 `docs/changes/api-client/prototypes/cli-shell/` 下的原型源码与设计文档 (若要做行为级修复) 或另一份 DOGFOOD 报告做交叉验证; 若只改契约, 优先改 schema 中 output_modes 描述与 candidates 语义段落. CLI 本身功能面已全部探明 (10 命令, 3 输出模式, 5 退出码, 2 环境), 无需复跑本流程.