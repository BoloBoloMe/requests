---
Status: accepted
---

# 拒绝 Node 运行时, 砍 Postman JS 脚本兼容

产品的运行时底线是纯 Python, 任何有 uv 的设备 `uv run` 即起. Postman 的 prerequest/test JS 脚本无法在纯 Python 中执行, 唯一兼容路径是引入 node 子进程 — 这会击穿运行时底线, 且 JS 脚本语义仿真是无底洞. 决策: v1 砍掉 JS 脚本兼容, 断言改用结构化 DSL (jmespath 取值 + 比较符 + jsonschema 整体校验), prerequest 的动态值需求由变量系统的白名单动态变量 (`{{$now}}`/`{{$uuid}}`) 吸收最小子集, 不提供通用可编程钩子.

## 备选方案

- 接 node 子进程执行 JS 脚本 — 拒绝: 引入第二个运行时, 违背 `uv run` 即起; 兼容 Postman 脚本语义无终点.
- 通用 Python 钩子 — 拒绝: 可编程钩子同样是无底洞, 自用场景由白名单动态变量 + 手动外部生成 (逃生舱) 覆盖.

## 后果

请求时计算能力被刻意限制为白名单两函数; HMAC 签名等场景 v1 内需手动外部生成粘贴. 此缺口经反方攻击确认, 接受为已识别风险, 高频命中时再立项.
