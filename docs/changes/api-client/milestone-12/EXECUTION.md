# EXECUTION.md — MILESTONE-12 自研测试后端

权威输入: [MILESTONE-12](../roadmap/MILESTONE-12.md), [M1-D011](../milestone-01/DECISIONS.md) (覆盖面), [M3-D014](../milestone-03/DECISIONS.md) (保持最小, 防膨胀; replace-don't-layer).

## 任务内技术选型 (先于 ISSUE 确定)

- 栈: FastAPI + uvicorn — 与后端本体同栈 (M3), 依赖最少原则下不再引入第三方 auth/SSE 库.
- digest 认证: 手搓最小 RFC 7616 (MD5, qop=auth), 仅供 Engine 测试.
- 项目骨架: uv 项目, `src/` 布局; 测试后端 = 独立 package `testbed` (与未来的产品包并列, 不预埋产品包名); 启动 `uv run testbed` (console script) 或 `uv run python -m testbed`.
- 测试接缝: HTTP 层 (fastapi TestClient), tests 在 `tests/testbed/`; dev 依赖 pytest + httpx.
- 固定 demo 凭证: basic `demo:demo-pass`, bearer `demo-token`, apikey `demo-key`, digest `demo:digest-pass`; 文档写死.

## ISSUE 列表

- [x] 已实现 ISSUE-01: 项目骨架 + echo 端点 — uv 骨架/pyproject/测试底座; `GET|POST /echo` 回显 method/path/query/headers/body
- [x] 已实现 ISSUE-02: CRUD `/things` — 内存集合 POST/GET/PUT/DELETE, 404 语义
- [x] 已实现 ISSUE-03: 认证端点 basic/bearer/apikey — `/auth/{basic,bearer}` 与 `/auth/apikey` (header + query 两种携带); 错误凭证 401, `WWW-Authenticate` 头正确
- [x] 已实现 ISSUE-04: digest 认证端点 `/auth/digest` — 完整质询/响应往返, 错误口令 401
- [x] 已实现 ISSUE-05: SSE 端点 `/sse` — `text/event-stream`, N 个带序号事件 + 间隔, 可控 event/data 形状
- [x] 已实现 ISSUE-06: 动态值校验端点 — `/dynamic/now` 校验 ISO 时间戳且在服务器当前 ±60s 内; `/dynamic/uuid` 校验 UUIDv4 格式; 非法输入 422 + 原因
- [x] 已实现 ISSUE-07: 边界端点 — `/status/{code}` 任意错误响应; `/delay/{seconds}` 延迟 (超时靶子); `/large?bytes=` 大响应体
- [x] 已实现 ISSUE-08: 启动入口与文档 — `uv run` 可起 (host/port 参数), README 写明端点清单/demo 凭证/dogfooding 用法

## 测试用例切片 (接缝 = HTTP 端点, 逐 ISSUE 先红后绿)

ISSUE-01:
- 当 GET /echo 带 query 与自定义 header 时, 响应 JSON 回显 method/url query/headers.
- 当 POST /echo 带 JSON body 时, 响应回显解析后的 body.
- 当 POST /echo 带原始文本 body 时, 响应回显原始文本与 content-type.

ISSUE-02:
- 当 POST /things 创建后 GET /things/{id} 时, 取回同一内容.
- 当 PUT /things/{id} 后 GET 时, 内容为更新后版本.
- 当 DELETE /things/{id} 后再 GET 时, 返回 404.
- 当 GET 不存在的 id 时, 返回 404.

ISSUE-03:
- 当 /auth/basic 带正确凭证时, 返回 200 与用户名; 带错误凭证时, 返回 401 且带 `WWW-Authenticate: Basic`.
- 当 /auth/bearer 带正确 token 时, 返回 200; 错误/缺失时 401.
- 当 /auth/apikey 经 header 携带正确 key 时, 返回 200; 经 query 携带时同样 200; 错误时 401.

ISSUE-04:
- 当无 Authorization 访问 /auth/digest 时, 返回 401 且带含 nonce/realm/qop 的 `WWW-Authenticate: Digest` 质询.
- 当按质询计算正确 digest 响应时, 返回 200.
- 当口令错误 (响应摘要错) 时, 返回 401.

ISSUE-05:
- 当 GET /sse 时, content-type 为 text/event-stream, 收到 N 个递增序号事件.
- 当指定事件数量/间隔参数时, 事件数与 data 形状随之变化.

ISSUE-06:
- 当 /dynamic/now 收到服务器当前时刻的 ISO 时间戳时, 判定合法.
- 当时间戳超出 ±60s 窗口或格式非法时, 返回 422 与原因.
- 当 /dynamic/uuid 收到合法 UUIDv4 时判定合法; 非法字符串 422.

ISSUE-07:
- 当 GET /status/503 时, 返回 503 与错误 body.
- 当 GET /delay/0.2 时, 响应耗时 ≥0.2s.
- 当 GET /large?bytes=1048576 时, 响应体大小为 1MB.

ISSUE-08:
- 当 `uv run python -m testbed --port 0` 启动时, 服务可连通 (冒烟脚本或文档验证).

## 范围外

- 产品核心库/服务/CLI 的任何代码; WebSocket/gRPC; oauth2; 持久化; 认证凭证可配置化 (写死即可).
