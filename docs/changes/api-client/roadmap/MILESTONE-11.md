# 状态: 已关闭
# 类型: task (HITL)
# 阻塞于: MILESTONE-09, MILESTONE-10

## 关闭注记 (2026-08-27)

验收四纲全部亲测通过: uv run 即起 (testbed+apic serve) / SPA 日常调试 (B 段 1~8 全过, 含 8 缺陷实修) / CLI 被 agent 真实调用 (场景 D: 全新子代理仅凭 help/schema/guide+样例自学, send/run 全过) / git 同步跑通 (bind/init+sync 双提交/secrets=0). 12 条 AFK 裁定用户逐条复核全部接受 (含 D-AFK-011 补记入账本). 缺口裁定: (a) 静态 main / (c) version=null 接受; (b) run 未解析改为跳过 (G1), 新诉求 G2~G5 (环境 UI/运行回看/动画/弹外折叠) 立为验收后回访待办, 方案与基线见 handoff 2026-08-26 文档.

## 问题

成品验收 (HITL, 须用户亲自参与):

- uv run 即起: 干净设备/目录下一条命令起服务, SPA 可用.
- SPA 日常调试: 用户用真实 API 工作流检验请求构建/发送/响应查看/集合/环境变量.
- CLI 被 agent 实际调用: 真实 agent 会话中完成一次调试与一次集合批量运行.
- git 同步跑通: 绑定远端仓库, pull/push 正常, 密钥不进 git.
- 验收通过 = 到达目的地, Roadmap 清空.
