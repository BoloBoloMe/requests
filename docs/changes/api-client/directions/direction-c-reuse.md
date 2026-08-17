# Research: 最大化复用组装路线 — Postman 替代品 (Python 后端 + Web UI)

## Summary
路线可行, 后端复用度高 (~60-70%: httpx + jsonschema + jmespath + OpenAPI 全家桶 + pytest 都能直接当库用), 前端复用度低 (~20-30%, 只有通用组件, 请求构建器/集合树/响应查看器无现成可嵌入物). 真实剩余自研 ≈ 一个集合执行引擎 (变量解析/认证/断言 DSL/批量 runner) + 一个 Web 壳 (请求编辑器 UI). 最大语义缺口是 Postman 的 JS 脚本 (prerequest/test), Python 侧无法直接执行, 建议 v1 砍掉, 用结构化断言 + 简单钩子替代.

## Findings

1. **HTTP 执行层: httpx 一选, 无短板** — httpx 0.28.1 覆盖本场景全部需求: sync+async 双 API, HTTP/1.1+HTTP/2, 流式响应 (`iter_bytes/iter_text/iter_lines/iter_raw`), 严格 timeout 可细调, `verify=False/SSLContext` + 客户端证书 `load_cert_chain` (mTLS), HTTP/SOCKS 代理 (`Client(proxy=...)` 或 mounts 路由), cookie/重定向/基本+摘要认证, WSGI/ASGI transport, `Request` 对象可构建任意原始请求, event hooks. 与 requests API 兼容, 迁移成本低. [httpx features](https://www.python-httpx.org/) [httpx streaming/timeout/auth](https://www.python-httpx.org/quickstart/) [httpx ssl/cert](https://www.python-httpx.org/advanced/ssl/) [httpx proxies](https://www.python-httpx.org/advanced/proxies/)
   - requests 2.34.2: 功能够但无 HTTP/2/async, 流式与请求控制较弱, 社区维护模式 — 不选. [requests](https://pypi.org/project/requests/)
   - aiohttp 3.14.3: 纯 async (整个后端要泡在 asyncio 里, headless 批量运行是负担), 唯一差异化能力 = 内建客户端 WebSocket. 若需要 WebSocket 调试则补位, 否则不用. [aiohttp](https://docs.aiohttp.org/en/stable/)

2. **API 测试引擎: pytest 可嵌入, tavern/schemathesis 是配角** —
   - pytest: 官方支持 `pytest.main([...], plugins=[...])` 从 Python 调用, 返回 exit code; 注意同进程多次调用因 import 缓存不推荐 (文档明确), headless CI 应用 subprocess 跑 pytest 并输出 JUnit XML. [pytest usage](https://docs.pytest.org/en/stable/how-to/usage.html)
   - tavern 3.6.1: 是 pytest 插件 + CLI + "Python library", 但公开库入口 `tavern.core.run()` 内部就是 `pytest.main()`; 底层 `tavern._core.run.run_test()` 是私有 API (模块带下划线, 不稳定). 嵌入 = 把集合转成 .tavern.yaml 再喂 pytest, 多做一层格式转换, 且 YAML 断言 DSL 与集合语义有差异 — 收益有限, 不建议作为主引擎. [tavern docs](https://tavern.readthedocs.io/en/latest/) [tavern core.py 源码](https://github.com/taverntesting/tavern/blob/master/tavern/core.py) [tavern _core/run.py](https://github.com/taverntesting/tavern/blob/master/tavern/_core/run.py)
   - schemathesis 4.24.3: 是 OpenAPI/GraphQL 驱动的 property-based 测试 (hypothesis 生成边界用例), 有完整 Python API: `schemathesis.openapi.from_dict/from_path/from_url` 加载 schema + `schemathesis.engine.from_schema(schema)` 返回 Engine (asyncio 事件流). 它解决的是"导入 OpenAPI 后自动测试", 不能替代集合 runner, 但可作为 OpenAPI 导入后的免费加分项 (自动 fuzz + 断言). 嵌入成本中等 (事件流 API 需适配). [schemathesis docs](https://schemathesis.readthedocs.io/en/stable/) [Python API](https://schemathesis.readthedocs.io/en/stable/reference/python/) [engine 源码](https://github.com/schemathesis/schemathesis/tree/master/src/schemathesis/engine)
   - 结论: 集合批量 runner = 自研薄层; pytest 仅作 CI 宿主/报告 (subprocess + JUnit).

3. **集合/环境格式: Postman v2.1 为主格式, 其余是可选导入** —
   - Postman v2.1: 纯 JSON, 官方 JSON Schema 权威 (`schema.getpostman.com`, draft-07, 52KB, 23 个 definition: item 递归/item-group, request, url, auth 12 种类型 (noauth/apikey/awsv4/basic/bearer/digest/edgegrid/hawk/ntlm/oauth1/oauth2), event+script (exec 为 JS 字符串数组), variable (key/value/type/system/disabled)). 解析本身零成本 (JSON + schema 校验), 成本在执行语义: 变量替换 {{var}} 简单, 12 种认证要逐个实现 (basic/bearer/apikey 简单; oauth2/oauth1/awsv4 有现成库 requests-oauthlib/awssigv4; ntlm/hawk/edgegrid 冷门), JS 脚本无法在 Python 执行. [v2.1 JSON Schema](https://schema.getpostman.com/collection/json/v2.1.0/draft-07/collection.json) [postmanlabs/schemas](https://github.com/postmanlabs/schemas)
   - OpenAPI 导入: Python 侧成熟 — `openapi-spec-validator` (校验), `prance` (解析+外部引用解析), schemathesis (消费). OpenAPI→collection 转换无主流 Python 库 (Python 的 postman2openapi 是反方向且已停更/仅基础字段), JS 侧 `postmanlabs/openapi-to-postman` (1058 stars, 活跃) 可作参考实现, 或自写 (OpenAPI path/param/body 结构规整, 1-2 天). [prance](https://pypi.org/project/prance/) [openapi-to-postman](https://github.com/postmanlabs/openapi-to-postman)
   - Bruno .bru: 文本 DSL, 每请求一个文件 (`meta{name,type,seq}` + `get{url,body,auth}` 等块), 文件夹/集合各一个 .bru, 环境是 `vars{...}` + `vars:secret[...]` 块 (支持 @number/@boolean/@object 类型注解). 无 Python 解析库 (只有 Go/TS 小项目, stars ≤8), 但格式简单, parser 1 天内可写. 生态绑定 JS, 作为导入格式价值有限. [.bru 样例](https://github.com/usebruno/bruno/tree/main/packages/bruno-cli/tests/runner/fixtures) [环境 .bru 样例](https://github.com/usebruno/bruno/blob/main/packages/bruno-tests/collection/environments/Local.bru)
   - Hoppscotch: 版本化 JSON 格式 (verzod/zod, 当前 v12, 含 preRequestScript/testScript 字符串, folders 递归), 无 Python 库, 格式无独立标准化价值 — 仅作可选导入 (1-2 天). [hoppscotch collection schema](https://github.com/hoppscotch/hoppscotch/blob/main/packages/hoppscotch-data/src/collection/v/12.ts)
   - Postman environment 格式: 简单 JSON (name + values[{key,value,type,enabled}]), 与 collection 同源.

4. **断言/校验组件: jsonschema + jmespath 够用, assertpy 不必** —
   - jsonschema: 支持 Draft 2020-12/2019-09/7/6/4/3, `iter_errors` 懒验证可收集全部错误 — 直接做"响应体整体校验". [jsonschema](https://python-jsonschema.readthedocs.io/en/stable/)
   - jmespath 1.1.0: JSON 查询语言, 有规范+跨语言一致性测试; 与 Postman 断言的路径式取值心智模型一致, 适合作为断言表达式语言的取值层. [jmespath](https://jmespath.org/)
   - assertpy 1.1: fluent 断言好用, 但 (a) 更新缓慢 (Travis 时代基建, 528 stars), (b) 断言要序列化存储/传输 (集合里存断言), fluent Python 对象无法序列化 — 结论: 断言引擎自研结构化 DSL (jmespath 路径 + 比较符 + jsonschema 引用), assertpy 顶多内部辅助, 不作为 DSL. [assertpy](https://github.com/assertpy/assertpy)

5. **前端可复用: 只有通用组件, 无 API 客户端专用件** —
   - Swagger UI (29k stars, Apache-2.0, React): 只读文档渲染 + "Try it out" 发请求, 是 OpenAPI 驱动的展示层, 不能做自由请求构建/集合管理/环境切换 — 最多作为"OpenAPI 预览"标签页嵌入, 不是请求构建器. [swagger-ui](https://github.com/swagger-api/swagger-ui)
   - 开源 API 客户端 (Bruno 46k stars React/Electron; Hoppscotch Vue3+PWA; Insomnia 已改限制性许可证) 都是完整应用, 无独立可嵌入组件 — 可参考交互设计, 无法复用代码. [bruno](https://github.com/usebruno/bruno) [hoppscotch](https://github.com/hoppscotch/hoppscotch)
   - 可复用通用件: CodeMirror 6/Monaco (body 编辑+高亮), react-json-tree (998 stars) / react-json-view (410 stars) (响应 JSON 树查看), 树/拖拽/UI 基件 (Shadcn/Radix 等). 请求构建器 (URL/params/headers/body key-value 编辑器 + 认证面板 + 集合树 + 运行结果面板) 全部自研. [react-json-tree](https://github.com/alexkuz/react-json-tree)

6. **结论: 剩余自研工作量** —
   - 省不掉的: (a) 集合/环境数据模型 + 变量解析引擎 ({{var}} 替换, 环境优先级) — 小, 但必须自写; (b) 请求执行胶水 (collection request → httpx request, 12 种认证映射) — 中, 大头在 oauth2 授权码流程需浏览器交互; (c) 结构化断言 DSL 解释器 + 批量 runner + 报告 — 中; (d) 整个前端 Web 壳 — 大, 无现成物; (e) headless CI 打包 (subprocess pytest + JUnit) — 小.
   - 可省/可砍: JS 脚本 (Postman prerequest/test) — 要么接 node 子进程 (引入 Node 运行时依赖, 违背纯 Python), 要么 v1 砍掉改用结构化断言+可选 Python 钩子 — 建议砍, 这是与 Postman 全兼容的最大成本点.
   - 成本量级 (单人对本项目): 后端执行引擎 ≈ 1-2 周 (含认证/断言/runner), 前端 ≈ 2-4 周 (编辑器/树/查看器/运行面板), 格式导入 (bru/hoppscotch) 各 1-3 天, OpenAPI 导入+自动测试 (schemathesis) ≈ 2-3 天. 相比全自研 (含 HTTP 层/断言库/测试框架), 本路线省下 ≈ 2-3 个月 (HTTP 客户端、JSON Schema、JMESPath、pytest 生态、OpenAPI 工具链).
   - 风险: (1) JS 脚本语义缺口 → 砍功能或引入 Node; (2) Postman 认证 OAuth2/签名认证边缘行为多, 需对照 postman-runtime/newman (JS, Apache-2.0, 可读源码对齐语义); (3) pytest 同进程多次调用限制 → CI 用 subprocess; (4) 无 Python 生态的 collection 执行引擎 → 执行语义只能参考 JS 实现逆向; (5) postman2openapi (Python) 与 joolfe/postman-to-openapi 均已停更/归档, 转换类库勿依赖, 自写为准. [postman-runtime](https://github.com/postmanlabs/postman-runtime) [newman](https://github.com/postmanlabs/newman) [joolfe/postman-to-openapi 归档说明](https://github.com/joolfe/postman-to-openapi)

## Sources
- Kept:
  - HTTPX 官方 (features/quickstart/ssl/proxies/api) (https://www.python-httpx.org/) — 首选执行层的全特性一手证据
  - pytest How to invoke (https://docs.pytest.org/en/stable/how-to/usage.html) — pytest.main 嵌入与同进程限制的官方证据
  - tavern 文档 + core.py/_core/run.py 源码 (https://tavern.readthedocs.io/en/latest/ , https://github.com/taverntesting/tavern) — 库嵌入方式与私有 API 判定
  - schemathesis 文档 + Python API + engine 源码 (https://schemathesis.readthedocs.io/en/stable/) — Python API/事件流嵌入判定
  - Postman v2.1 Collection JSON Schema (https://schema.getpostman.com/collection/json/v2.1.0/draft-07/collection.json) — 格式结构与 auth/script/event 定义的一手来源
  - postmanlabs/schemas (https://github.com/postmanlabs/schemas) — Postman 官方格式 schema 仓库
  - Bruno 仓库 .bru/环境样例 (https://github.com/usebruno/bruno) — 文本 DSL 格式一手样例
  - Hoppscotch verzod 集合 schema v12 (https://github.com/hoppscotch/hoppscotch/blob/main/packages/hoppscotch-data/src/collection/v/12.ts) — 版本化 JSON 格式判定
  - jsonschema (https://python-jsonschema.readthedocs.io/en/stable/) / jmespath (https://jmespath.org/) / assertpy (https://github.com/assertpy/assertpy) — 断言组件评估依据
  - swagger-ui (https://github.com/swagger-api/swagger-ui) / postmanlabs/openapi-to-postman (https://github.com/postmanlabs/openapi-to-postman) / newman / postman-runtime — 前端与参考实现
- Dropped:
  - joolfe/postman-to-openapi (https://github.com/joolfe/postman-to-openapi) — 已归档 (repo README 明确), 不可依赖
  - oxylabs/decodo/proxywing 等 "httpx vs requests" 对比博客 — SEO 汇总文, 官方文档已覆盖, 冗余
  - PyPI postman2openapi (https://pypi.org/project/postman2openapi/) — 仅基础字段, 不足以做导入引擎, 仅记录存在
  - appknox/postmanparser 等 Python Postman parser (17 stars 级) — 太小且不活跃, 无采用价值

## Gaps
- Postman 12 种认证模式的执行细节 (oauth2 授权码/刷新、awsv4/edgegrid/hawk 签名) 未逐一实测, 需对照 postman-runtime 源码逐项实现, 是执行引擎的主要风险点.
- JS 脚本 (prerequest/test) 的替代方案 (结构化断言 DSL 设计) 未调研具体 DSL 设计, 建议立项后单独设计.
- 前端请求构建器组件市场未做穷尽搜索 (GitHub 搜索第一轮返回空), 但主流开源客户端均为完整应用已足够支撑"无现成组件"结论; 若有疑问可再搜 "request builder web component".
- Hoppscotch 自托管后端 (hoppscotch-backend) 数据格式未深挖, 若需要从 Hoppscotch 实例迁移数据需补调研.