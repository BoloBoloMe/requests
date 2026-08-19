# 状态: 已关闭
# 类型: prototype
# 阻塞于: MILESTONE-03

## 问题

AI CLI 外壳原型. CLI 的用户是 AI agent, 设计目标与人类 CLI 不同:

- 命令面: send/run/集合管理/环境管理等命令的组织与命名.
- 结构化输出: 默认 JSON? NDJSON 流式? --pretty 供人调试?
- 退出码与错误模型: agent 可依赖的机器可读失败语义.
- 可发现性: agent 如何自学会这个 CLI (--help 形状, schema 自描述, llms.txt?).
- 产物: stub 核心的粗糙可跑原型, 验证 agent 实际调用的顺手程度.

## 结论

原型经三轮 AI 实弹试用 (dogfood) 收敛, 两条自学路径 (--help-only / schema+guide) 充分性均 4/5. 设计决策已固化: 命令面 (动作动词+资源名词组+元命令), 输出契约 (流式 NDJSON/非流式 JSON/pretty), send/run 同构事件流, 退出码 0-4 + 细分错误码带 candidates, 双通道可发现性, 未解析变量硬失败.

产物: [决策账本](../milestone-04/DECISIONS.md); 原型归档 [prototypes/cli-shell/](../prototypes/cli-shell/) (一次性代码, 实现 MILESTONE-10 时参照重写).
