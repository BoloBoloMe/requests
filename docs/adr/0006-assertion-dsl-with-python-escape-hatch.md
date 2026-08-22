# 断言双形态: 结构化 DSL 为主 + Python 逃生舱

断言采用两种并存形态: 默认结构化 DSL (target + op + expect / jsonschema), 表达不了时可用 `python` 键写任意 Python 断言语句 (exec 注入 response 视图, 无沙箱). ADR 0001 砍掉的是 JS 脚本 (无 node 运行时); 对原生 Python 该理由不成立, 而 "远端 pull 集合即 RCE" 的理由在自用场景 (无他人仓库) 权重不足, 故放开逃生舱. 结构化形态仍为主: SPA 表单可编辑, runner 报告统一, AI 纠错友好.

## 后果

- 集合文件中的 `python` 断言即代码 — 若未来跨人共享仓库, 须重新评估执行边界.
- 领域语言 "断言" 条目的 "不可编程" 表述已随本 ADR 修订.
