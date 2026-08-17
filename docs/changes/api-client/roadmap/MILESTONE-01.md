# 状态: 已关闭
# 类型: deliberate
# 阻塞于: 无

## 问题

v1 范围界定. 裁剪面最大, 是路线第一步:

- 协议面: REST 先行? GraphQL (仅 body 内容?) / WebSocket / SSE 砍或留.
- 认证矩阵: Postman 12 种认证中哪些进 v1 (basic/bearer/apikey/digest 低成本; oauth2 授权码流程需浏览器交互, 成本高; ntlm/hawk/edgegrid 冷门).
- 导入: Postman collection v2.1 导入要不要? OpenAPI 导入要不要?
- 确认砍掉 Postman JS 脚本 (prerequest/test) 兼容 — 侦查建议砍, 用结构化断言替代, 需用户拍板.
- 变量系统范围: {{var}} 替换, 环境优先级, 动态变量 ($random 类) 要不要.
