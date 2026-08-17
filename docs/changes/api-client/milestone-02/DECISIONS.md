# MILESTONE-02 决策账本 — 数据存储与集合格式

产物归属: `docs/changes/api-client/roadmap/MILESTONE-02.md` (已关闭).
盘问方式: deliberate skill, 五轮盘问 + 纯自扫 (用户拒绝反方攻击), 用户逐条确认.
输入约束: [MILESTONE-01 账本](../milestone-01/DECISIONS.md) 的 D007 (version 字段/读侧兼容), D009/D010 (变量两级来源/动态变量), D011 (测试后端); [ADR 0002](../../../adr/0002-zero-importers-one-off-migration-script.md) (脚本可生成).
上游账本决策记作 "M1-D007" 等.

## 决策

### D001 — 文件粒度: 每请求一文件

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 一个请求条目 = 一个 YAML 文件; 集合树直接映射文件树 (集合 = 目录, 文件夹 = 子目录).
- 理由: git diff 最小; AI 读写单文件最简单; 用户 hurl 习惯 (每请求一文件); 自用 + 人/AI 并写下, 每集合一大文件的 diff 噪音与冲突不可接受.
- 预计影响: 数据模型与存储层 (MILESTONE-03 起).
- 相关 issue: 待关联

### D002 — 格式语法: 自定义 YAML, 不用 DSL 不用 JSON

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 自定义 schema 的 YAML (不兼容 Postman v2.1); 每个文件带显式 `version` 字段 (M1-D007), v1 = `version: 1`; YAML 子集约定: 禁用锚点/别名, 所有 kv 值 (vars/params/headers/secrets) 一律按字符串解析 (防 YAML 1.1 `on/off/yes/no` 布尔陷阱), AI 生成建议标量加引号. 格式演进责任在读侧向后兼容. 见 [ADR 0003](../../../adr/0003-yaml-per-request-format.md).
- 理由: 手写友好 + 库成熟 + 嵌套自由 + AI 生成可靠; 自定义文本 DSL (hurl/bru 风格) 的持续语法设计与双向序列化成本不为次要编辑通道买单; JSON 人手写体验差.
- 依赖事实: F002
- 预计影响: 数据模型与存储层, 转换脚本, SPA/CLI 读写, 测试后端夹具.
- 相关 issue: 待关联

### D003 — 集合内排序: frontmatter seq

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 请求文件内 `seq` 整数表达目录内顺序, 平局按文件名 tiebreak; 文件名保持 slug 不含序号.
- 理由: 拖拽重排不改文件名, git 历史干净; AI 改序不动文件名不易错; 文件树顺序不可见由 SPA 集合树吸收.
- 预计影响: 数据模型, SPA 集合树拖拽, CLI 列表输出.
- 相关 issue: 待关联

### D004 — 目录布局: 数据目录即独立 git 仓库

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 布局如下; 数据目录本身是一个独立 git 仓库 (可绑定远端, SPA 提供入口).
```text
collections/<集合>/<文件夹>/<slug>.yaml
collections/<集合>/_collection.yaml
environments/<env>.yaml              # 进 git
environments/<env>.secrets.yaml      # gitignored
files/                               # 上传文件, 进不进 git 用户自决
.local/                              # gitignored: 本地状态与历史
```
- 理由: 既定约束 (数据 = 本地文件 + git 管理); 多集合并列, 布局即心智模型.
- 预计影响: 存储层, SPA git 入口, .gitignore 自动写入.
- 相关 issue: 待关联

### D005 — 环境文件: 必须进 git

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: `environments/<env>.yaml` schema = `version` + `vars` (扁平 key-value, 值一律字符串); 必须 tracked 进 git (用户明确, 非可选).
- 理由: 换机即恢复环境定义; 值不含密钥 (密钥走 secrets 文件).
- 预计影响: 存储层, SPA 环境管理.
- 相关 issue: 待关联

### D006 — 密钥: gitignored secrets 文件

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 每环境可有配套 `<env>.secrets.yaml`, 与环境文件同 schema, gitignored, 合并时优先级最高; 引用侧无特殊语法, 照常 `{{var}}`; 绑定仓库时工具自动写入 .gitignore 规则防误提交.
- 理由: 文件模型统一无新语法, SPA/CLI 同等可读; 进程环境变量对 SPA/AI 代理不友好; keyring 过度工程.
- 预计影响: 存储层, 变量解析引擎, SPA git 绑定流程.
- 相关 issue: 待关联

### D007 — 激活环境指针: 仓库内 gitignored 状态文件

- 状态: 当前有效
- 约束性: 可调整
- 内容: 当前激活环境存 `.local/state.yaml`, 每 clone 独立, 不进 git.
- 理由: 激活状态是本地偏好, 多机/多 clone 不同步才正确.
- 预计影响: 存储层, SPA 环境切换.
- 相关 issue: 待关联

### D008 — 请求字段形状

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: `url` = 单字符串 (含 `{{var}}` 插值, 不拆 host/path); `params`/`headers` = 有序 key-value 列表, 每项可 `disabled`, params 允许重复键; `body.type` = `none | json | text | form-urlencoded | multipart`; `method`/`name`/`seq`/`version`/`auth`/`assert` 见样例 (MILESTONE-02 盘问第 5 轮样例为准; assert 形状以 MILESTONE-06 原型为准).
- 理由: Postman 的 url 拆分结构对人和 AI 都是噪音; 有序可禁用 kv 列表与 hurl/Postman 心智一致.
- 依赖事实: F001
- 预计影响: 数据模型, SPA 请求构建器, CLI.
- 相关 issue: 待关联

### D009 — multipart 文件引用: 相对 + 绝对路径皆可

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: part 两种形态: 内联文本 (`value`) 或文件引用 (`file` + 可选 `contentType`); `file` 支持仓库相对路径 (推荐) 与绝对路径 (原样存储, SPA 提示 "不可移植, 搬机即断"); 文件本身是否进 git 用户自决.
- 理由: 用户明确要求绝对路径可用 (临时文件摩擦不可接受); 自用工具移植性风险自担.
- 依赖事实: F001
- 预计影响: 数据模型, 请求引擎 (multipart 构造), SPA 提示.
- 相关 issue: 待关联

### D010 — 集合级默认继承

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: `_collection.yaml` 含 `vars` (集合变量) + `defaults` (集合级默认 auth 与 headers); 仅集合一级继承 (文件夹级不做); headers 按名合并, 请求同名覆盖; auth 整体覆盖 — 请求定义了 auth 则全用请求的, 不合并.
- 理由: 用户明确保留继承 (接受批量改文件的代价换集中定义); 限定集合一级使规则三句话可讲完, 避开 Postman 文件夹级继承的绕晕部分.
- 预计影响: 变量/继承解析引擎, 数据模型, SPA 集合设置面板.
- 相关 issue: 待关联

### D011 — 历史落盘: 文本请求/响应 append 全保留, gitignored

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 每次发送, 请求/响应体为文本则请求+响应 (状态行/头/体/耗时) 全保留 append 落盘到 `.local/history/<集合路径>/<条目slug>/<时间戳>.yaml`; 非文本或超大 body 只落元信息 (content-type/大小); SSE 流式响应在连接关闭后把已收事件聚合为一个文本体落盘, 未关闭不落; multipart 请求体落文件引用路径+大小, 不内联文件内容; v1 不做自动清理 (手动删); 历史 gitignored (派生数据可再生成, 响应可能含敏感数据); runner 的 CI 报告 (JUnit XML) 是输出物, 不属于数据仓库.
- 理由: 用户明确要求 "只要是文本的传输, 请求和响应都要落盘" (推翻盘问第 2 轮的 "历史不落盘" 初步建议); gitignored 防仓库膨胀与敏感数据入史.
- 预计影响: 请求引擎 (发送即记录), 存储层, SPA 历史面板 (若有).
- 相关 issue: 待关联

### D012 — 变量解析优先级

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 集合 vars < 环境 vars < 环境 secrets, 高优先级覆盖同名; `{{$now}}`/`{{$uuid}}` 独占 `$` 前缀命名空间, 不参与覆盖, 静态变量禁止以 `$` 开头.
- 理由: M1-D009/D010 的落地; secrets 是环境层的 gitignored 面, 与环境文件同属环境层, 两级域模型 (集合/环境) 不变; `$` 保留防动态变量与静态变量撞名.
- 预计影响: 变量解析引擎, 数据模型校验.
- 相关 issue: 待关联

## 事实

### F001 — 用户有文件上传场景

- 状态: 当前有效
- 来源: 用户陈述 (MILESTONE-02 盘问第 2 轮)
- 内容: multipart/form-data 必须进 v1 (推翻初议的砍掉建议); 配套产生文件引用决策 D009.

### F002 — YAML 1.1 布尔陷阱与锚点风险

- 状态: 当前有效
- 来源: YAML 1.1 规范常识 (多数 YAML 库默认 1.1 行为: `yes/no/on/off` 等未加引号标量解析为布尔)
- 内容: `vars: {debug: on}` 会被解析为布尔 true; 锚点/别名 (`&`/`*`) 对 AI 生成与人手编辑构成惊喜. D002 的 YAML 子集约定由此而来.
