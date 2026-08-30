# api-client

本地优先的 Postman 替代品: Python (FastAPI) 后端 + Vue3 SPA 供人操作 + CLI 供 AI/agent 调用.
数据落本地 YAML 子集, 可 git 管理同步, 不依赖任何云端账户.

- SPA: 集合树/请求构建器/响应面板/环境管理/批量运行.
- CLI (`apic`): 瘦客户端, 本地服务幂等拉起, stdout 只出数据, stderr 出机器可读错误.
- 数据形态: 每个集合是 `collections/<集合>/` 下的 YAML 文件; 环境是 `environments/<环境>.yaml`, secrets 单独放到 `.secrets.yaml`.
- 自研最小测试后端 `testbed` 供本地接口联调.

详细设计见 `docs/changes/api-client/`.

## 快速开始

要求: Python >=3.12 (见 `pyproject.toml`), 以及 [uv](https://docs.astral.sh/uv).

```bash
git clone <repo-url> requests
cd requests
uv run apic serve
```

- 服务默认监听 127.0.0.1, 端口由内核随机分配 (`src/api_client/__main__.py`).
- 默认数据目录: `~/.local/share/api-client/`, 可用 `--data-dir PATH` 改.
- 第一次访问会自动拉起数据目录结构.

查端口与状态:

```bash
uv run apic service status
```

取当前 token (服务运行时才有值):

```bash
uv run apic service token
```

打开浏览器访问 `http://127.0.0.1:<port>` 即可; 服务启动时会自动把 token 注入 `index.html`, SPA 可直接使用. 手动调用 API 时在请求头带 `X-Auth-Token: <token>`; SSE 由于浏览器限制, 也支持 `?token=<token>` 查询参数.

停止服务:

```bash
uv run apic stop
# 或
uv run apic service stop
```

起个本地测试后端:

```bash
uv run testbed --port 9000
```

## CLI 教程

`apic` 所有命令支持 `--data-dir PATH` 与 `--output json|ndjson|pretty`.

### 常用命令

```bash
# 元命令: 完整机读契约与文读手册
uv run apic schema
uv run apic guide

# 执行单个请求条目 (send) 与批量运行集合 (run)
uv run apic send <collection>/<slug> [--env NAME] [--var KEY=VALUE]...
uv run apic run <collection> [--env NAME] [--var KEY=VALUE]...

# 资源查询
uv run apic collection list
uv run apic collection show <collection>
uv run apic item list <collection>
uv run apic item show <collection>/<slug>
uv run apic env list
uv run apic env show <name>
uv run apic history list
uv run apic history show <id>

# 服务生命周期
uv run apic service status
uv run apic service token
uv run apic service stop
```

### 示例

```bash
# 用 dev 环境, 并临时覆盖 host 变量 (假设集合/条目名为 my-api/get-json)
uv run apic send my-api/get-json --env dev --var host=127.0.0.1:9000

# 批量跑 my-api 集合
uv run apic run my-api --env dev

# 以 pretty 形式列出集合
uv run apic collection list --output pretty
```

### 事件流 (send/run)

`send` 与 `run` 输出 NDJSON 事件流, 默认 `--output ndjson`:

- `meta(type,timestamp,item_ref,item,method,resolved_url,env)`
- `chunk(type,timestamp,item,index,data)`
- `done(type,timestamp,item,status,duration_ms,assertions)`
- `summary(type,timestamp,total,passed,failed,items)` (仅 `run` 末尾)
- `run` 末尾还附 `report` 事件, `format=junit`.

### 退出码

| code | 含义 |
| ---- | ---- |
| 0 | OK: 成功, 全部断言通过 |
| 1 | ASSERTION_FAILED: 领域失败, 数据正常产出但至少一条断言未通过 |
| 2 | USAGE_ERROR: CLI 调用非法, 未解析变量或参数错误 |
| 3 | SERVICE_ERROR: 服务/操作失败 |
| 4 | NOT_FOUND: 集合, 请求条目或环境不存在 |

### send 与 run 的差异, 以及未解析变量

`--var KEY=VALUE` 可重复, 优先级高于环境变量. 动态变量 `{{$now}}` / `{{$uuid}}` 由引擎在运行时求值, 不视为未解析.

若变量替换后 URL/headers/body 仍残留 `{{NAME}}` 占位符:

- `send` 单条会硬失败, exit 2, 错误码 `UNRESOLVED_VARIABLES`.
- `run` 批量会跳过该条目 (不发 HTTP), 合成 `done` 事件带 `error.code=UNRESOLVED_VARIABLES`, status 为 null, 计入 `summary.failed` 与 JUnit errors, 其余条目照常运行, 整批最终 exit 1.

错误输出统一为单行 JSON: `{"error":{"code","message","details"}}`, stdout 保持干净.

## SPA 使用

界面分三栏: 左侧集合树/环境, 右上请求构建器, 右下响应面板.

### 集合树

- 顶部集合下拉可切换/新建集合, 新建即自动写 `_collection.yaml`.
- 请求条目按 `seq` 排序, 拖拽抓手 `⠿` 可同文件夹内重排.
- 文件夹可折叠/展开; 条目显示方法徽章 (GET/POST/...) 与删除按钮.
- 批量运行后条目旁会出现状态徽标: 运行中 `◌`, 通过 `✓`, 失败 `✗`; 失败条目下方显示红字断言明细, 点击可跳到对应断言.

### 环境管理

点击顶部环境胶囊 -> 下拉尾部 "管理环境" 打开环境管理弹层:

- 列表/新建/改名/删除环境.
- 编辑区分 "变量" (写 `environments/<name>.yaml`) 与 "Secrets" (写 `environments/<name>.secrets.yaml`) 两栏.
- 可一键 "设为激活"; 激活环境会写入 `.local/state.yaml`, 变量视图在合并 secrets 后生效.

### 变量编辑

点击侧栏 `⚙` 打开 "集合变量" 弹层, 编辑当前集合的 `vars`, 保存到 `_collection.yaml`.

### 发送与运行

- 选中条目后可在构建器编辑 method/url/params/headers/body/auth/assertions, 点 "发送" 运行单条.
- 侧栏 `▶` 运行整个集合 (顺序执行全部条目).
- 运行完成后点击树中条目, 右下响应面板会显示该次运行的响应/断言明细, 顶部有 `⏱ 运行回看` 提示条.

### 交互与动画

- 弹层/下拉显隐, 树折叠展开, tab 切换, 状态徽标过渡均带动画.
- 系统开启 `prefers-reduced-motion` 时动画自动降级.
- 弹层/下拉 (CollectionMenu/EnvMenu/VarEditor/EnvEditor) 点击外部自动收起.

## 数据与 git 同步

数据目录结构 (默认 `~/.local/share/api-client/`):

```
<data-dir>/
  collections/
    <集合>/
      _collection.yaml          # 集合变量与默认 headers/auth
      <slug>.yaml               # 请求条目
      <文件夹>/
        <slug>.yaml
  environments/
    <env>.yaml                  # 普通变量
    <env>.secrets.yaml          # secrets, 合并优先级最高
  files/                        # 文件引用 (multipart 等)
  .local/                        # 本地运行态 (gitignored)
    state.yaml                  # 激活环境
    service.json                # 端口/token/pid
    service.log
    history/                   # 运行历史
```

- secrets 文件与 `.local/` 不应入 git. 通过 SPA 的 git 同步按钮首次绑定时, 后端会自动在数据目录追加 `.gitignore` 规则 `.local/` 与 `*.secrets.yaml`. 若你手动建仓库, 请自行加上这两条.
- 数据是 YAML 子集, 禁用锚点/别名; `vars`/`params`/`headers`/`secrets` 的值一律按字符串解析, 避免 YAML 1.1 的 `on/off/yes/no` 布尔陷阱.

## 开发

后端测试:

```bash
cd requests   # 仓库根目录
uv run python -m pytest
```

前端 (已入库的 `spa/dist` 由后端托管):

```bash
cd requests/spa
npm install
npm run test
npm run typecheck
npm run build
```

构建后请确认 `spa/dist/` 产物已提交, 否则服务启动时会报 "SPA 产物漂移" 警告. 运行产物中的 token 占位符 `__APIC_TOKEN_VALUE__` 只在内存中替换, 永不写入磁盘.

## 安全说明

- 服务默认绑定回环地址 (`127.0.0.1`), Host 白名单限制为 `localhost` / `127.0.0.1` / `::1`, 不响应其它来源.
- 未安装 CORS 中间件, 默认不放行跨站 origin.
- 每次启动生成 256 bit 随机 token, 通过 HTTP header `X-Auth-Token` 或 SSE 查询参数校验.
- text/html 响应注入 CSP `script-src 'self'`.
- 访问日志只记 method/脱敏 URL/状态码, 不记请求头.
