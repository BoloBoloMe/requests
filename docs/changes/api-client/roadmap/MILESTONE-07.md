# 状态: 已关闭
# 类型: research
# 阻塞于: MILESTONE-01

## 问题

实时协议流式转发调研 — 仅当 MILESTONE-01 决定 v1 保留 WS/SSE 时激活:

- 经 Python 后端代理的 WS/SSE 转发方案 (httpx 流式 + websockets 库?), 取消/重连/缓冲语义.
- 前端流式渲染: fetch ReadableStream 解析 SSE, WS 连后端转发端口; 大流渲染性能.
- 若 MILESTONE-01 砍掉实时协议, 本 Milestone 关闭并转入未决迷雾 (实时协议二期).
