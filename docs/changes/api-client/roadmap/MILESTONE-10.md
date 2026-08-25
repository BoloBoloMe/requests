# 状态: 已关闭
# 类型: task
# 阻塞于: MILESTONE-04, MILESTONE-08

## 问题

CLI 实现 (AFK 编码任务, 走 tdd-as-orchestra):

- AI 外壳全量实现, 按 MILESTONE-04 原型定稿的命令面/输出/错误模型.
- 内嵌核心库独立运行还是纯 API client, 按 MILESTONE-03 决策形态落地.
- 验收含真实 agent 调用场景.

## 关闭记录

- 关闭日期: 2026-08-25 (AFK 执行段).
- 执行: `docs/changes/api-client/milestone-10/EXECUTION.md` 任务书, 4 issues 链式 (骨架+launch → send → run+history → 资源命令+schema/guide), 每 issue TDD 切片红→绿, 假服务 (D014-4) + 真服务双面测试.
- 产物: `src/api_client_cli/` (12 模块) + `tests/api_client_cli/` (12 文件, 55 测试); pyproject scripts 将 apic 指 CLI, serve/stop 转发保留.
- 提交: 5b0e7a9 (I-01) / 81eb3ae (I-02) / 109b885 (I-03) / 29cecfb (I-04) / 8bc318f (build: pytest importlib).
- 协调补丁 (08 侧, 契约出口): e02e4bf (execute/run 请求体 vars 覆盖层), de7654d (GET /environments 列表端点).
- 全量 pytest 251 绿 (testbed 62 + api_client 136 + cli 55, 含补丁增量); 端到端冒烟全过: send 三形态/--var 生效/断言失败 exit 1/未解析变量 exit 2 无事件流/run summary+report/不吞 chunk/schema guide 契约一致/token 子命令/stop 转发.
- AFK 裁定落盘: `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` (D-AFK-001~012 关联项), M11 复核.
- 已知边界 (记录不阻塞): run 遇未解析变量整批硬失败 (M4-D006 一致); service status 的 version 对真服务 null (/health 无 version 字段); agent 场景 (dogfood 对标) 属 M11 人工验收.
- 命令行面: send/run/collection|item|env|history|service 资源组/schema/guide/serve|stop 转发; 全局 --output (json/ndjson/pretty) + --data-dir; 退出码 0-4, 错误 stderr {"error":{code,message,details}}.