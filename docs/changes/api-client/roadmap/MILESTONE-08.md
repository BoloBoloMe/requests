# 状态: 待处理
# 类型: task
# 阻塞于: MILESTONE-03, MILESTONE-06

## 问题

后端核心实现 (AFK 编码任务, 走 tdd-as-orchestra):

- 按 MILESTONE-03 架构决策实现核心库: 集合/环境/执行引擎 (httpx)/断言解释器 (MILESTONE-06 的 DSL)/runner/git 同步.
- FastAPI 服务层: 供 SPA (和可能的 client 模式 CLI) 使用的 API.
- 若 MILESTONE-07 激活, 流式转发也在本 Milestone 内实现.
- 完成标准: 核心能力可被 CLI 和 SPA 双外壳真实调用.
