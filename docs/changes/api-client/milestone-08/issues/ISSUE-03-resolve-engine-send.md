# ISSUE-03 — Resolve + Engine + send (POST /execute)

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: Resolve 把请求条目 + 环境 → 可执行请求: 变量两级 + secrets 优先级 (集合 vars < 环境 vars < 环境 secrets, M2 D012), 集合级默认继承 (headers 按名合并请求覆盖同名, auth 整体覆盖, M2 D010), 动态变量白名单 `{{$now}}`/`{{$uuid}}` (M1 D010), 插值在 url/params/headers/body/auth 全字段生效 (M1 D009), 未解析残留 `{{var}}` → 硬失败 UNRESOLVED_VARIABLES (M4 D006). Engine (M3 D006): 运行于服务进程内, async httpx, 五种认证 none/basic/bearer/apikey/digest (M1 D003), multipart 内联文本 + 文件引用 (相对/绝对路径, M2 D009), 超时/响应大小上限为内置常量 (M3 D013), 事件经 asyncio.Queue 出流 (meta/chunk/done, M4 D003), SSE 断连不取消执行. `POST /execute` 按 Accept 协商 `text/event-stream` vs `application/x-ndjson` (M3 D007). 历史落盘 (M2 D011): 文本请求+响应 (状态行/头/体/耗时) 全保留 append 落盘 `.local/history/<集合>/<slug>/<时间戳>.yaml`, 非文本只落元信息 (content-type/大小), multipart 落文件引用不内联, SSE 连接关闭后聚合已收事件落盘, 不脱敏 secrets (M5 决策 5). `GET /history/{c}/{slug}` 只读端点. 适合 AFK: 执行/事件/历史语义全由账本钉死, 测试靶子现成.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (执行引擎/历史)
- 决策: `docs/changes/api-client/milestone-03/DECISIONS.md`, D006/D007/D008/D013; `docs/changes/api-client/milestone-02/DECISIONS.md`, D008-D012; `docs/changes/api-client/milestone-01/DECISIONS.md`, D003/D009/D010; `docs/changes/api-client/milestone-04/DECISIONS.md`, D003/D006; `docs/changes/api-client/milestone-05/DECISIONS.md`, 决策 5

## 相关决策
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D006 (Engine 内嵌服务进程, async httpx, asyncio.Queue, 断连不取消), D007 (SSE+JSONL 单一事件模型按 Accept 协商), D008 (Resolve/Engine/Store 职责与依赖方向), D013 (超时/大小内置常量)
- `docs/changes/api-client/milestone-02/DECISIONS.md`: D008 (字段形状), D009 (multipart 相对/绝对路径), D010 (集合默认继承), D011 (历史落盘规则), D012 (变量优先级)
- `docs/changes/api-client/milestone-01/DECISIONS.md`: D003 (五种认证), D009 (插值全字段+两级来源), D010 ($now/$uuid 白名单)
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D003 (meta/chunk/done 事件契约), D006 (未解析变量硬失败)
- `docs/changes/api-client/milestone-05/DECISIONS.md`: 决策 5 (历史落盘不脱敏 secrets)

## 允许范围
- 新建 `src/api_client/resolve.py`, `src/api_client/engine.py`, `src/api_client/web/execute.py` (路由+协商), 历史读写落 Store 但写入口归 Engine 调用, `tests/api_client/test_resolve.py`, `tests/api_client/test_engine.py`, `tests/api_client/test_execute_api.py`, `tests/api_client/test_history.py`.
- 测试 fixture: 子进程拉起 `uv run testbed --port 0` 真 HTTP (D014-2).

## 禁止范围
- 不实现断言求值 (ISSUE-04); 不实现批量 runner (ISSUE-05); 不实现 oauth2 交互流程 (M1 D004); 不做 WS/gRPC (M1 D001).
- 不 mock httpx (D014-2); 不改 `src/testbed/`; 不脱敏历史 (M5 决策 5); 不做历史自动清理 (M2 D011).

## 代码定位提示
- 参照: `src/testbed/README.md` (端点清单与 demo 凭证: basic `demo:demo-pass`, bearer `demo-token`, apikey `demo-key`, digest `demo:digest-pass`; `/echo`, `/auth/*`, `/sse?count=5`, `/dynamic/now|uuid`, `/status/{code}`, `/delay/{s}`, `/large?bytes=`), `docs/changes/api-client/milestone-02/DECISIONS.md` D011/D012, `docs/changes/api-client/milestone-04/DECISIONS.md` D003 (事件字段).
- 阅读顺序: resolve.py → engine.py → execute 路由 → 四个测试文件; 历史测试用 testbed `/echo` (回显 header 验证不脱敏).

## TDD 切片
- TS-001 (Resolve 纯单测, D014-1):
  接缝: `resolve.build_request(item, env, now_fn/uuid_fn 注入)` 纯函数.
  测试用例: TC-001 — 优先级: 集合 vars < 环境 vars < secrets, 同名高优先覆盖; TC-002 — 集合默认 headers 按名合并请求覆盖同名, auth 请求定义则整体覆盖; TC-003 — `{{$now}}` 求值为 ISO 时间戳、`{{$uuid}}` 为 UUIDv4, 其余 `$` 前缀变量不被识别; TC-004 — 解析后仍残留 `{{var}}` → 抛 UNRESOLVED_VARIABLES 并列出缺失变量.
  先写的失败测试: `test_resolve_secrets_override_env` — 预期失败: 未实现 secrets 优先级时 secrets 值不生效.
  最小绿色实现范围: 两级+secrets 合并 + 插值全字段 + 动态变量白名单求值 + 残留检测硬失败.
  不得测试: 网络/httpx (Engine 职责); 动态变量之外的求值扩展.
  覆盖: M2 D012, M1 D009/D010, M4 D006.
- TS-002 (Engine 打 testbed 真 HTTP, D014-2):
  接缝: `engine.execute(request) -> AsyncIterator[Event]` 或队列消费, fixture 起 testbed.
  测试用例: TC-005 — 五种认证真实往返 (basic/bearer/apikey header 与 query/digest 质询, demo 凭证); TC-006 — POST /echo 回显 method/url/query/headers/body; TC-007 — multipart 文件引用 (相对路径) 上传, testbed 回显 content-type 含 multipart boundary; TC-008 — /sse?count=5 → 收到 5 个 chunk 事件; TC-009 — /delay/5 超时 (内置超时常量) → 超时事件且不悬挂; TC-010 — /large?bytes= 超上限 → 大小上限事件.
  先写的失败测试: `test_engine_digest_auth_roundtrip` — 预期失败: 无 digest 实现时 401 且无质询往返.
  最小绿色实现范围: async httpx 请求构造 (五种认证/multipart) + 流式读取 → meta/chunk/done 事件 + 超时/大小常量检查.
  不得测试: 变量解析 (Resolve 已测); 不 mock httpx.
  覆盖: M1 D003, M2 D008/D009, M3 D006/D013.
- TS-003 (/execute 协商 + 断连, D014-3):
  接缝: TestClient 薄测 + 真进程可选.
  测试用例: TC-011 — Accept `text/event-stream` → SSE 帧 (event/data), Accept `application/x-ndjson` → 逐行 JSON; TC-012 — done 事件含 status/duration_ms/item; TC-013 — 客户端断连后执行继续完成, 历史仍落盘.
  先写的失败测试: `test_execute_negotiates_ndjson_by_accept` — 预期失败: 无协商时两种 Accept 输出相同.
  最小绿色实现范围: Accept 协商 + 事件编码器 (SSE/NDJSON 同一事件模型, M3 D007) + 断连不取消执行 (task 继续, 聚合事件落盘).
  不得测试: 业务断言 (ISSUE-04).
  覆盖: M3 D007, M4 D003.
- TS-004 (历史落盘, M2 D011 + M5 决策 5):
  接缝: Store 历史写 API + 文件内容断言.
  测试用例: TC-014 — 文本传输: 请求+响应 (状态行/头/体/耗时) 全保留 append 落盘; TC-015 — 非文本/超大 body 只落元信息 (content-type/大小); TC-016 — multipart 落文件引用路径+大小, 不内联文件内容; TC-017 — 不脱敏: 环境 secrets 值经 `{{var}}` 解析后出现在请求头, 历史文件中该值明文可读; TC-018 — SSE 连接关闭后已收事件聚合为一个文本体落盘, 未关闭不落.
  先写的失败测试: `test_history_keeps_secret_plaintext` — 预期失败: 若实现方主动脱敏则 secret 被掩码.
  最小绿色实现范围: 发送即记录 (Engine 副作用经 Store 写), 文本/非文本分路, SSE 聚合, 明文保留 (明确不做脱敏).
  不得测试: 自动清理 (v1 不做).
  覆盖: M2 D011, M5 决策 5.

## 验证入口
- `uv run pytest tests/api_client/test_resolve.py tests/api_client/test_engine.py tests/api_client/test_execute_api.py tests/api_client/test_history.py` — 全绿 (engine 测试 fixture 自动起 testbed).
- 真服务冒烟: `uv run apic serve --data-dir /tmp/apic-send &`; 建条目指向 `http://127.0.0.1:9000/auth/bearer` (testbed `uv run testbed --port 9000 &`); `curl -N -H "Accept: text/event-stream" -H "X-Auth-Token: $TOKEN" -X POST -H "Content-Type: application/json" -d '{"collection":"demo","item":"auth-bearer"}' http://127.0.0.1:$PORT/execute` 观察 meta/chunk/done 事件流; 检查 `.local/history/demo/auth-bearer/` 下文件含 bearer token 明文.

## 风险提示
- 同步阻塞 httpx 会卡死事件循环上全部 API (M3 D006 点名), 必须 async httpx.
- digest 认证是 testbed 手搓 RFC 7616, 与 httpx digest 交互以真实往返为准; 失败不得降级为 mock.
- 断连不取消执行 (M3 D006) 与历史聚合是易漏点, TC-013/TC-018 钉死.
- 未解析变量静默成功会让下游误判 (M4 D006 教训), TC-004 必须硬失败.

## 停止条件
- 需要改变事件模型字段、变量优先级、历史落盘规则或五种认证集合时停止.

## 适合 AFK 的原因
- 执行/事件/历史语义全部已由账本 (M1/M2/M3/M4/M5) 钉死, testbed 靶子现成, 无待定决策.

## 验收标准
- [ ] Resolve: 两级+secrets 优先级, 动态变量白名单, 未解析硬失败 UNRESOLVED_VARIABLES.
- [ ] Engine: 五种认证/multipart/SSE 流式/超时/大小上限经 testbed 真实往返.
- [ ] POST /execute 按 Accept 协商 SSE/NDJSON, meta/chunk/done 事件, 断连不取消.
- [ ] 历史: 文本全保留 append / 非文本元信息 / multipart 文件引用 / SSE 聚合, 不脱敏.

## 被阻塞于
- ISSUE-02 (Store/领域对象/数据仓库布局)
