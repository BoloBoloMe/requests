# Dogfood 报告: 仅靠 --help 自学 apic 原型

角色: 从未见过 apic 的 AI agent, 只通过 CLI --help 自学 (未读源码/README, 未用 schema/guide 子命令).
运行环境: `uv run python docs/changes/api-client/prototypes/cli-shell/apic.py`.

## 逐任务记录

### 任务 1: 搞清楚工具能干什么
命令: `apic --help`, 以及 7 个子命令各自 `--help`.
一次成功. 顶层帮助给出 9 个子命令 (send/run/collection/item/env/history/service/schema/guide) 和用法示例, 已可推断: 这是个 API 客户端, 用集合/条目组织请求, 支持环境变量, 每个条目带断言, 输出多种格式, 带历史与(桩)服务管理. schema 和 guide 因任务限制未触碰.
卡点: 无.

### 任务 2: 列出集合并查看 demo 条目
命令: `collection list`; `item list demo`.
一次成功.
- 集合仅 1 个: `demo` (Demo Collection, item_count=3).
- 条目 3 个: demo/get-json (GET http://{{host}}/json), demo/sse-stream (GET http://{{host}}/stream), demo/failing-check (GET http://{{host}}/fail).
- `env list` 顺带发现: dev=localhost:3000, prod=api.example.com.
卡点: 无.

### 任务 3: 查看 demo/get-json 定义
命令: `item show demo/get-json`.
一次成功. 输出完整定义: method/url/status/headers/body 以及两条断言 (status=200, body_field hello=world). 注意到 body 在定义里是"期望响应样例"的语义.

### 任务 4: 用 prod 执行 demo/get-json 并取响应体
命令: `send demo/get-json --env prod` (默认 ndjson 输出).
一次成功. 3 行 ndjson:
- meta: 含 resolved_url (http://api.example.com/json) 与 env.
- chunk(index=0): data 为完整 JSON 对象 {hello:world, list:[1,2,3]} — 响应体在此.
- done: status/duration_ms/assertions 明细.
退出码 0.

### 任务 5: 执行 demo/sse-stream 理解流式
命令: `send demo/sse-stream --env prod`.
一次成功. 每个 SSE 事件对应一行 chunk 记录 (index 0/1/2, data=alpha/beta/gamma), 后接 done 收尾. 流式即按事件逐条吐 ndjson, 无需 --stream 之类开关, 默认即流式. duration_ms=150 表明是真逐条间隔而非事后一次性输出.
卡点: 无.

### 任务 6: 批量运行 demo 集合, 判断断言失败
命令: `run demo --env prod`.
一次成功. 每个条目只吐 meta + done (无 chunk, 批量时省略响应体), 末行 summary: total=3, passed=2, failed=1.
失败项: demo/failing-check 的断言 body.ok 期望 true 实得 false (its 定义中 body 即 {ok:false}).
退出码 1.

### 任务 7: 找出服务 token
命令: `service token` (顺带 `service status`).
一次成功. 返回 `{"token": "stub-token-do-not-use-in-production"}` — 桩数据, 非真 token. `service status` 返回 running/pid 4242/port 8080/version 0.0.0-stub, 同样为桩. 报告结论: 无真实 token, 拿到的是明确标注的占位值.

### 任务 8: 执行不存在的条目, 观察错误与退出码
命令: `send demo/nonexistent --env prod`, 另测 `send demo` (缺斜杠)、`send bogus/env`、`send demo/get-json --env bogus`.
一次成功 (指能触发并观察).
失败所有情况均输出单行 JSON `{"error":{"code":"NOT_FOUND","message":"..."}}`, 退出码一律 4. 消息能区分原因:
- 无此条目: "item not found: demo/nonexistent"
- 无此集合: "collection not found: nonexistent-collection"
- 无此环境: "environment not found: bogus"
- 引用格式错: "item-ref must be <collection>/<item-slug>, got: 'demo'"
错误码只有 NOT_FOUND 一种, 但 message 足以区分. 自动纠错的可行性: 可以靠 jq 解析该 JSON 提取 code/message; 但"纠错"仅能靠 message 差异, 且 code 分类太粗, 无法区分"该重试/该查列表/该换环境"的语义类别.

## 其他实测补充 (探查顺利时顺带观察)
- `send demo/failing-check --env prod`: 断言失败时 also 退出码 1 (失败即非零).
- `--output pretty`: 人类可读, 但 chunk data 用 Python repr 打印 (`{'ok': False}`), 不是合法 JSON.
- `history list/show h-001`: 可用, 但 h-001 是 2024 年的伪造旧记录 (started_at 2024-01-15), 与本次运行时间 2026-08 无任何对应, 即历史并未记录刚才的执行.
- `service stop`: 返回 stopped + 原 pid, 桩行为.

## --help 自学充分性评分: 4/5
优点: 顶层帮助 + 每子命令帮助均带示例 (Example 行对 AI 极友好); 参数/默认值/可选值标注明确 (如 --output 枚举, --env 说明); 无隐藏命令, 子命令树从 help 一眼可穷举.
缺口 (扣 1 分):
- 输出 schema 不完整: help 只说 json/ndjson/pretty, 没说明 ndjson 的事件类型 (meta/chunk/done/summary) 及各字段, 需要实际跑一次才能学懂 — 这恰好是 schema/guide 子命令存在的理由, 但任务禁止.
- 没有说明退出码约定 (0/1/4 的含义分散在行为中, help 只字未提, 不试不知道).
- 没有说明"body 字段在定义中表示期望响应"这一语义, 初次看到会误以为是当前响应.

## 摩擦点清单
1. 退出码无文档: 成功=0, 断言失败=1, 错误=4 — help 完全未提, 只能实跑试探.
2. 错误 JSON 的 code 只有 NOT_FOUND 一种: 分不清是条目/集合/环境/格式问题, 逼着 AI 去 diff message 文案.
3. --output pretty 的 chunk data 用 Python repr (单引号 dict), 不是 JSON, 解析器会踩坑.
4. 子命令名为名词 (collection/item/env/history/service) + 二级动词 (list/show/...), 但 send/run 又是动词打头, 命名不对称, 猜测层级要试错.
5. run 批量时静默省略每个条目的 chunk (响应体), 只留 meta/done — 想同时拿响应体和断言得逐条 send, 对批量+审计场景是坑.
6. 环境名没有默认概念: 不传 --env 会怎样? (未测成功路径的默认值, 但 help 未声明 default)
7. history 不回写刚执行的操作: 名字叫 history 却不记录, 容易误导自动化判断.
8. 时间戳是真实执行时间, 而 history 记录是伪造的 2024 年 — 数据真伪混杂无标注.

## 作为 AI 最希望改掉的 3 件事
1. 在 help 里写明退出码约定与错误 JSON 的错误码分类 (把 NOT_FOUND 拆成 item_not_found/collection_not_found/env_not_found/format_error), 这样我不用靠实跑推测, 出错也能直接分支处理.
2. 提供事件流的完整字段字典 (可挂在 --help 尾部或让 schema 产物成为 --help 的可见部分), 让首次使用即可离线构建解析器, 不必"跑一次才懂".
3. run 批量模式增加 --with-body 之类开关来保留每个条目的响应体, 或在 summary 里直接列出失败断言明细 — 减少"批量跑完还得逐个重放定位"的来回成本.

## 后续行动者应先看的入口
- `apic.py --help` 与各子命令 --help (自有文档的唯一来源, 本报告一切结论的起点).
- `item show demo/failing-check` vs `send demo/failing-check --env prod` 对照: 理解"定义即期望"语义与断言失败输出形态, 是本工具核心心智模型.
- 每次使用前先 `env list` 确认环境名 — 环境不在 help 里, 只在运行时可发现.