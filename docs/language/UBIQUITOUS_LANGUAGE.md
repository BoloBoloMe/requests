# API 客户端

自用, 本地优先的 API 调试与自动化测试工具 (Postman 替代品). Python 后端是产品本体, SPA 与 CLI 是两个外壳; 数据为本地文件, git 管理.

## 语言

**集合** (Collection):
请求条目的命名分组, 支持文件夹层级, 是数据文件的基本组织单位.
_避免_: 项目, 分组, workspace

**请求条目** (Item):
**集合** 内的一次 HTTP 请求定义: 方法, URL, 参数, 头, 体, 认证与断言.
_避免_: 接口, API

**环境** (Environment):
一组具名变量值; 切换环境即切换同一批变量的取值. **环境变量** 覆盖同名 **集合变量**.
_避免_: 配置, profile

**集合变量** (Collection Variable):
挂在 **集合** 上的静态变量, 被该集合内所有请求条目共享.

**动态变量** (Dynamic Variable):
插值时由引擎现场求值的内建变量, 写作 `{{$now}}` / `{{$uuid}}`; v1 白名单仅此两个, 无参无嵌套.
_避免_: 函数, 表达式, 钩子

**断言** (Assertion):
挂在 **请求条目** 上的校验条目, 两种形态: 结构化断言 (jmespath 取值 + 比较符, 或 jsonschema 整体校验) 为主; Python 断言为逃生舱 (exec 注入 response 视图, 无沙箱, 见 ADR 0006). 能结构化就结构化.
_避免_: 测试脚本, test script

**外壳** (Shell):
产品的交互界面, 共两个: SPA 供人, CLI 供 AI. 外壳不含核心逻辑, 全部能力在 **核心库**; CLI 是瘦客户端, 必须连 **服务** 才能工作.
_避免_: 前端, 客户端 (指整体产品时)

**核心库** (Core Library):
产品逻辑本体的 Python 库: Store/Resolve/Engine/Assert/Runner/Sync 六个模块; 唯一消费者是 **服务** (CLI 不 import, 唯一例外是共享的 launch 拉起模块).
_避免_: 后端 (指代码实体时), 业务层

**服务** (Service):
常驻的本地 FastAPI 进程, **核心库** 的运行宿主与唯一安全边界: 默认绑 127.0.0.1, 启动随机 token 护全部 API; SPA 由其托管, CLI 幂等拉起它 (在则不动作, 不在则拉起).
_避免_: 服务器 (指远端机器时), 后端进程

**执行事件流** (Execution Event Stream):
一次请求执行的输出形态: meta/chunk/done 事件序列; SPA 经 SSE 消费, CLI 经 JSONL 消费, 同一事件模型两种编码.
_避免_: 日志流, 消息

**测试后端** (Test Backend):
随仓库的自研 HTTP 服务, 开发夹具兼 dogfooding 对象; 覆盖产品全部能力面 (认证, SSE, 动态值校验, 边界响应), 不是产品功能.
_避免_: mock server, demo 服务 (作为术语时)

**一次性转换脚本** (Migration Script):
hurl 脚本到本项目数据文件的一次性外挂转换器, 用完即弃; 不属于产品, 但必须输出未转换条目清单.
_避免_: 导入器, importer

**数据仓库** (Data Repository):
数据目录本身即独立 git 仓库: `collections/` (每请求一 YAML 文件, 集合树映射文件树), `environments/`, `files/`, gitignored 的 `.local/`; 可绑定远端, SPA 提供同步入口.
_避免_: 工作区, workspace

**集合级默认** (Collection Defaults):
`_collection.yaml` 中的默认 auth 与 headers, **集合** 内请求条目继承; 仅集合一级: headers 按名合并 (请求覆盖同名), auth 整体覆盖.
_避免_: 继承链, 文件夹级继承

**历史** (History):
文本传输的请求+响应 append 落盘记录, 存于 `.local/history/`, gitignored 派生数据; 非文本只落元信息, SSE 在连接关闭后聚合落盘.
_避免_: 日志, log

**secrets 文件** (Secrets File):
环境的 gitignored 配套文件 `<env>.secrets.yaml`, 与环境同 schema, 变量解析优先级最高; 引用侧照常 `{{var}}`.
_避免_: 密钥库, keyring

## 示例对话

开发者: 这个请求条目放哪个集合?
领域专家: 放 "billing" 集合, 它的集合变量里有 `host`, 但我在 "prod" 环境里把 `host` 覆盖成生产地址 — 切环境就换地址, 条目本身不动.
开发者: 条目里签名参数要请求时算 HMAC, 写个动态变量?
领域专家: 不行, 动态变量只有 `{{$now}}` 和 `{{$uuid}}`, 不扩展; HMAC 场景先手动外部生成粘贴, 真高频再立项.
开发者: 断言能写脚本吗?
领域专家: 优先不写 — 默认是结构化的, jmespath 取值比较或 jsonschema 校验; 真表达不了 (数组长度, 浮点容差之类) 再用 Python 断言逃生舱.
开发者: 这套断言对哪个服务验证?
领域专家: 对测试后端, 它有对应的校验端点; 老 hurl 脚本则用一次性转换脚本迁过来, 转不了的条目它会列清单.
开发者: 响应里的 token 会被记下来吗?
领域专家: 会, 文本传输的请求和响应都进历史, 但历史在 .local/ 里不进 git; token 这类真秘密放 secrets 文件, 同样不进 git.
开发者: 这个集合的请求都要带同一个 bearer, 每个文件都写一遍?
领域专家: 引用写一遍, 值不重复 — 集合级默认里定义 `Bearer {{token}}`, 各条目继承; 哪个条目要特殊认证就自己写 auth 整体覆盖.
