---
Status: accepted
---

# 自定义 YAML 每请求一文件格式

数据格式选择: 每请求一个 YAML 文件 (集合树映射文件树), 自定义 schema 带显式 `version` 字段, 不兼容 Postman v2.1, 不用自定义文本 DSL (hurl/bru 风格), 不用 JSON. 数据一旦落盘并被 git 管理, 格式演进成本随数据量增长, 这是项目最难逆转的决策之一.

## 备选方案

- Postman v2.1 兼容优先 — 拒绝: 产品零导入器 (ADR 0002), 兼容无收益; v2.1 的 url 拆分等结构对人和 AI 都是噪音.
- 自定义文本 DSL (hurl/bru 风格) — 拒绝: 手写体验最好但需自写 parser 与序列化器双向维护; SPA 是主编辑器, 手写是次要通道, 不为次要通道买持续语法设计成本.
- JSON — 拒绝: 人手写体验差; 用户来自 hurl, 文本手编习惯真实存在.

## 后果

- YAML 子集约定: 禁锚点/别名, 所有 kv 值 (vars/params/headers/secrets) 一律按字符串解析 (YAML 1.1 布尔陷阱).
- 格式演进责任在读侧向后兼容 (ADR 0002), `version` 字段 v1 即写入.
