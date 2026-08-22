# MILESTONE-06 决策账本 — 断言 DSL 原型

## 决策 1: 断言双形态 — 结构化 DSL 为主 + Python 逃生舱

背景: 原型评审中用户质疑 "何必自定义 DSL, 直接 Python 断言不好吗". MILESTONE-01 砍脚本的理由是无 node 运行时, 对原生 Python 不成立; 但 "远端 pull 集合即 RCE" 是保留 DSL 的最强理由. 用户拍板: 自用软件, 无他人仓库, RCE 权重不成立 → **双形态并存**.

- **结构化断言** (默认, SPA 表单可编辑, runner 报告统一): `target + op + expect` 三元组, 或 `target + schema` (jsonschema 整体校验).
  - target 集: `status` / `elapsed_ms` / `header.<名>` (大小写不敏感) / `body` / `body.<jmespath>`
  - op 集: `eq ne lt lte gt gte contains not_contains matches exists` (exists 无 expect)
- **Python 断言** (逃生舱): `{"python": "<代码>"}`, exec 注入 `response` 视图 (`.status` `.headers` `.body` `.text` `.elapsed_ms`), 全量 Python 无沙箱 (自用); AssertionError = 断言失败 (取其消息), 其他异常 = 错误 (类型+消息).
- 分工原则: 能结构化就结构化; 数组长度, 浮点容差, 跨字段逻辑等 DSL 表达不了的走逃生舱, DSL 不再为此扩展 op.

## 决策 2: 序列化形态 — YAML, Python 代码用块标量

断言列表存于请求条目 YAML 的 `assert:` 键下; 多行 Python 代码用 `|` 块标量, 人和 AI 都可写. 原型内的极简 YAML 发射器仅演示形态, 正式实现用 PyYAML.

## 决策 3: 非 JSON 体降级 — 裸 body 文本比较, 不引入其他路径语言

非 JSON 响应体的 `body.<路径>` 一律解析失败; 降级手段为裸 `body` (= 原始文本) + `contains`/`not_contains`/`matches`/`eq`. 用户确认够用; XML/HTML 不引入路径语言.
实现注意 (留给 MILESTONE-08): "体非 JSON" 与 "路径不存在" 应区分报错文案, 原型中二者混为一句.

## 表达力验证结论

4 个测试后端真实样例 (201 创建/404/422/延迟端点) 全过; 已知缺口 (数组长度, 浮点容差, 非 JSON 结构化取值) 均由逃生舱覆盖, 无需扩展 DSL.

## 产物

- 原型: `../prototypes/assertion-dsl/` — `dsl.py` 为求值器参考实现 (供 MILESTONE-08 参照重写), `web.py`/`tui.py`/`fixtures.py` 为一次性外壳, 合并主干前由人清理.
- ADR: [0006](../../../adr/0006-assertion-dsl-with-python-escape-hatch.md)
