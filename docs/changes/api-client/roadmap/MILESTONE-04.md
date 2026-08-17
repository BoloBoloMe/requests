# 状态: 待处理
# 类型: prototype
# 阻塞于: MILESTONE-03

## 问题

AI CLI 外壳原型. CLI 的用户是 AI agent, 设计目标与人类 CLI 不同:

- 命令面: send/run/集合管理/环境管理等命令的组织与命名.
- 结构化输出: 默认 JSON? NDJSON 流式? --pretty 供人调试?
- 退出码与错误模型: agent 可依赖的机器可读失败语义.
- 可发现性: agent 如何自学会这个 CLI (--help 形状, schema 自描述, llms.txt?).
- 产物: stub 核心的粗糙可跑原型, 验证 agent 实际调用的顺手程度.
