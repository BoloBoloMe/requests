# 状态: 已关闭
# 类型: task
# 阻塞于: MILESTONE-03, MILESTONE-06

## 问题

后端核心实现 (AFK 编码任务, 走 tdd-as-orchestra):

- 按 MILESTONE-03 架构决策实现核心库: 集合/环境/执行引擎 (httpx)/断言解释器 (MILESTONE-06 的 DSL)/runner/git 同步.
- FastAPI 服务层: 供 SPA (和可能的 client 模式 CLI) 使用的 API.
- 若 MILESTONE-07 激活, 流式转发也在本 Milestone 内实现.
- 完成标准: 核心能力可被 CLI 和 SPA 双外壳真实调用.

## 关闭记录

- 关闭日期: 2026-08-25 (AFK 执行段).
- 执行: `docs/changes/api-client/milestone-08/EXECUTION.md` 任务书, 7 issues 链式完成, 每个 issue 独立 TDD 切片 + code-review 闭环.
- 产物: `src/api_client/` (launch/store/resolve/engine/assertions/runner/sync + web/ 路由壳) + `tests/api_client/` (127 测试) + `spa/` 占位; 全量 `uv run pytest` 189 passed (testbed 62 + api_client 127).
- 提交: 34506c9 (I-01) / afdf242+8c626e9 (I-02) / 52a038c+4613733 (I-03) / 0b5601d+fe8fa87 (I-04) / d3dc78d+0a6a9d3 (I-05) / aec3c9c+d62418d (I-06) / dd02c19+798c9a0+541a5c1+7e5b404 (I-07).
- AFK 裁定: `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` D-AFK-001~010 (含 done.error 授权/三态 status/summary 口径/单条异常隔离/bind 幂等等), M11 验收时逐条复核.
- 完成标准达成: `uv run apic serve --data-dir <tmp>` 起服 + /health 带 token 200; 双进程并发拉起矩阵通过; 端到端冒烟 (集合/环境 → send → run → JUnit 可解析) 通过; dist 托管冒烟 (注入 token + no-store + 时间戳警告) 通过.
- 遗留 (M11 或后续): CLI `token` 子命令归 M10; wheel 打包时 spa/ 定位适配; Accept q 值解析简化语义已注释钉死.