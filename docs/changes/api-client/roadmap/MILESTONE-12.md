# 状态: 已关闭
# 类型: task
# 阻塞于: 无

## 问题

自研测试后端服务 (决策见 [D011](../milestone-01/DECISIONS.md)). 定位 = 开发夹具而非产品功能, `uv run` 可起, 兼任 dogfooding 对象与 demo.

覆盖面 = v1 全部能力面:

- echo/CRUD 端点.
- 五种认证端点 (none/basic/bearer/apikey/digest).
- SSE 流式端点 (`text/event-stream`).
- 动态值校验端点 (验证 `{{$now}}`/`{{$uuid}}`).
- 边界场景: 错误响应, 超时, 大响应体.

技术选型 (FastAPI/Starlette/stdlib 等) 在任务内先定, 原则: 依赖最少, 与后端本体同栈.

AFK 编码任务, 调用 `tdd-as-orchestra` skill 处理.

## 结论

测试后端 `testbed` 已交付: 8 个 ISSUE 全部完成, 62 测试绿 (~1s). 技术选型: FastAPI + uvicorn (与后端本体同栈), digest 手搓最小 RFC 7616. 端点面: echo / things CRUD / auth×4 (basic/bearer/apikey header+query/digest) / sse (count/interval/event 参数) / dynamic (now±60s 严格 ISO 校验, uuid v4) / 边界 (status/delay/large). `uv run testbed` 或 `uv run python -m testbed --port 0` 可起.

产物: [EXECUTION.md](../milestone-12/EXECUTION.md) (8 ISSUE 全勾选), 代码 `src/testbed/`, 测试 `tests/testbed/`, 文档 `src/testbed/README.md`. 提交: feat: ISSUE-01..08.
