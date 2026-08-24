# 后端核心实现 (MILESTONE-08) Execution Spec

## 权威输入
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md` (后端核心实现, AFK 编码任务, 走 tdd-as-orchestra)
- Decisions (核心架构): `docs/changes/api-client/milestone-03/DECISIONS.md` (D001-D014, F001-F005)
- Decisions (数据/存储): `docs/changes/api-client/milestone-02/DECISIONS.md` (D001-D012, F001-F002)
- Decisions (v1 范围): `docs/changes/api-client/milestone-01/DECISIONS.md` (D001-D011, F001-F003)
- Decisions (断言 DSL): `docs/changes/api-client/milestone-06/DECISIONS.md` (决策 1-3)
- Decisions (CLI 事件契约): `docs/changes/api-client/milestone-04/DECISIONS.md` (D001-D006)
- Decisions (SPA/历史): `docs/changes/api-client/milestone-05/DECISIONS.md` (决策 5)
- 断言参考实现: `docs/changes/api-client/prototypes/assertion-dsl/dsl.py` (一次性原型, 重写不直接复用)
- 测试靶子: `src/testbed/` + `tests/testbed/` (MILESTONE-12, 只读不改)

## 任务内技术选型 (先于 ISSUE 确定, 不新增决策)
- 产品包: `src/api_client/`; 核心库六模块 `store.py` / `resolve.py` / `engine.py` / `assertions.py` / `runner.py` / `sync.py` + `launch.py` (D002 唯一共享例外) + 服务壳 `web/` (FastAPI app/中间件/路由/静态托管), 入口 `__main__.py`.
- console script (按 pyproject 现有 [project.scripts] 惯例 `testbed = "testbed.__main__:main"` 推断): `apic = "api_client.__main__:main"`; 服务入口 `uv run apic` (默认 serve 子命令, 参数 `--host`/`--data-dir`), 停止入口 `uv run apic stop --data-dir <dir>`. CLI 其余命令面属 MILESTONE-10, 本里程碑不实现.
- 新增依赖: 仅 PyYAML (MILESTONE-02 D002 正式实现); JUnit 报告手写最小 XML (xml.etree), 不新增依赖; 复用现有 fastapi/uvicorn/httpx/jmespath/jsonschema/pytest.
- token: `secrets.token_urlsafe(32)` (≥128 bit); 请求头 `X-Auth-Token`; SSE 握手额外接受 `?token=` (M3 F002).
- 事件模型字段按 MILESTONE-04 D003: meta(type,timestamp,item_ref,item,method,resolved_url,env) / chunk(type,timestamp,item,index,data) / done(type,timestamp,item,status,duration_ms,assertions) / summary(type,timestamp,total,passed,failed,items); run 对每条目发完整 meta/chunk/done, 不吞 chunk (禁止要求重放 send); 未解析变量硬失败 UNRESOLVED_VARIABLES (M4 D006).
- API 形状 (D010 REST+RPC 混合, 具体路径为执行细节): 资源 CRUD `/collections/...` `/environments/...` `/history/...` `/state`; 动作 RPC `POST /execute` (ISSUE-03), `POST /collections/{c}/run` (ISSUE-05), `POST /git/sync` `/git/bind` (ISSUE-06); 健康检查 `GET /health`.
- 测试布局: `tests/api_client/`, pytest testpaths 增补; Store 用 pytest tmp_path 数据目录 (D014-1 的 "无 I/O" 指无网络/服务 I/O, 文件系统 I/O 用 tmp_path 隔离); Engine/Runner 测试用 fixture 子进程拉起 `uv run testbed --port 0` 真 HTTP.

## 全局允许范围
- 新建 `src/api_client/`, `tests/api_client/`.
- 修改 `pyproject.toml` (dependencies 增 PyYAML; [project.scripts] 增 apic; hatch packages 增 src/api_client; pytest testpaths 增 tests/api_client), `.gitignore` (产品侧), 仓库根新增 `dist/` 占位与 SPA 源码占位目录 (ISSUE-07).
- 参照 `src/testbed/` 端点清单 (README) 与 `prototypes/assertion-dsl/dsl.py` 求值语义.

## 全局禁止范围
- 不实现 WS/gRPC 协议面板与代理 (M1 D001; SSE 仅作 HTTP 流式响应转发, 断连不取消执行).
- 不做 oauth2 授权码/设备码交互流程 (M1 D004; client_credentials 由 "集合内 token 请求 + `{{var}}` 插值" 配方覆盖, 无专门代码).
- 不做 JS 脚本断言与通用可编程钩子 (M1 D008; 断言仅结构化 DSL + Python 逃生舱, M6 决策 1).
- 历史与访问日志落盘不脱敏 secrets (M5 决策 5; 历史 gitignored, M2 D011).
- Windows 不支持 (M3 D012; flock/fork/pid 语义按 POSIX).
- 不改动 `src/testbed/` 与 `tests/testbed/` (MILESTONE-12 产物, 只作测试靶子).
- 不实现 CLI 命令面 (MILESTONE-10) 与导入器/转换脚本 (M1 D006); 不做历史自动清理 (M2 D011) 与闲置自动回收 (M3 D011-7); API 不版本化 (M3 D013).
- 不改动任何 DECISIONS/ADR 内容; 不扩大任一 issue 边界.

## 完成定义
- `uv run pytest` 全绿: 存量 `tests/testbed` (62 测试) + 新增 `tests/api_client`; 每个 issue 验收标准逐条可观察.
- `uv run apic serve --data-dir <tmp>` 可起, `/health` 带 token 返回 200; 双进程并发拉起矩阵通过.
- 端到端冒烟 (testbed 作靶子): 建集合/条目/环境 → send 打 echo/认证 x5/SSE → 断言结果进 done → run 批量 → JUnit 报告可解析.
- dist 托管冒烟: `curl` 首页返回注入当前 token 的 HTML 且带 `Cache-Control: no-store`; dist 时间戳警告可观察 (人工).

## 测试策略
按 MILESTONE-03 D014:
1. Store/Resolve/Assert 纯单测: 不起服务, 不打网络; Store 文件级 I/O 用 pytest tmp_path 数据目录隔离.
2. Engine/Runner 打 testbed 真实 HTTP (replace-don't-layer, 不 mock httpx; 价值恰在真实传输: SSE/认证/multipart).
3. FastAPI 壳用 TestClient 薄测 API 形状与 token 校验; 业务断言下沉核心库测试.
4. launch 专项矩阵: 双进程并发拉起/端口占用/stale service.json/拉起失败路径.
5. 安全中间件函数级参数化单测: Host 白名单变体 (IPv6/重复头/伪造)/header vs query token/SSE 握手/日志脱敏.
6. Sync 用临时目录真实 git 仓库 (本地 bare remote) 测试, POSIX 前提.

## 任务图
- ISSUE-01: `issues/ISSUE-01-service-skeleton-launch-security.md`; 覆盖: M3 D001/D002/D004/D005/D011/D012, D014-5/6; 依赖: 无.
- ISSUE-02: `issues/ISSUE-02-store-resource-crud.md`; 覆盖: M2 D001-D008/D010, M3 D008/D010, D014-1; 依赖: ISSUE-01.
- ISSUE-03: `issues/ISSUE-03-resolve-engine-send.md`; 覆盖: M1 D003/D009/D010, M2 D008-D012, M3 D006/D007/D008/D013, M4 D003/D006, M5 决策 5; 依赖: ISSUE-02.
- ISSUE-04: `issues/ISSUE-04-assert-interpreter.md`; 覆盖: M1 D008, M6 决策 1/2/3, M3 D008, D014-1, M4 D003; 依赖: ISSUE-03.
- ISSUE-05: `issues/ISSUE-05-runner-batch-run.md`; 覆盖: M3 D008/D013, M4 D003, M2 D011, D014-2; 依赖: ISSUE-04.
- ISSUE-06: `issues/ISSUE-06-sync-git.md`; 覆盖: M2 D004-D007/D011, M3 D008/D009/D010; 依赖: ISSUE-02.
- ISSUE-07: `issues/ISSUE-07-dist-hosting-token-inject.md`; 覆盖: M3 D003, D004-4/D004-6, F005; 依赖: ISSUE-01.

## 覆盖矩阵
- M3 D001 (CLI 瘦客户端, launch 唯一例外) -> ISSUE-01 -> TS-001/TS-004 -> `uv run pytest tests/api_client/test_launch.py`
- M3 D002 (launch 共享) -> ISSUE-01 -> TS-001/TS-002 -> 同上
- M3 D004 (安全五件套) -> ISSUE-01 -> TS-003 -> `uv run pytest tests/api_client/test_security.py`
- M3 D005 (`--host` 语义/token 子命令) -> ISSUE-01 -> TS-003/TS-004 -> curl 冒烟
- M3 D011 (服务发现/生命周期) -> ISSUE-01 -> TS-001/TS-002/TS-004 -> 同上
- M3 D012 (POSIX only) -> ISSUE-01 -> 测试前提 (fcntl/flock) -> 无
- M3 D014-5/6 (launch 矩阵/安全参数化) -> ISSUE-01 -> TS-001/TS-003 -> 同上
- M2 D001-D004 (每请求一文件/YAML 子集/seq/布局) -> ISSUE-02 -> TS-001 -> `uv run pytest tests/api_client/test_store.py`
- M2 D005-D007 (环境/secret/激活状态) -> ISSUE-02 -> TS-002 -> 同上
- M2 D008/D010 (字段形状/集合默认) -> ISSUE-02 -> TS-001 -> 同上
- M3 D010 (REST CRUD) -> ISSUE-02 -> TS-003 -> `uv run pytest tests/api_client/test_crud_api.py`
- M1 D003/D009/D010 (五种认证/两级变量/动态变量) -> ISSUE-03 -> TS-001/TS-002 -> `uv run pytest tests/api_client/test_resolve.py tests/api_client/test_engine.py`
- M2 D011 (历史落盘) -> ISSUE-03 -> TS-003 -> `uv run pytest tests/api_client/test_history.py`
- M2 D012 (变量优先级) -> ISSUE-03 -> TS-001 -> 同上
- M3 D006/D007 (Engine 内嵌/SSE+JSONL 协商) -> ISSUE-03 -> TS-002/TS-003 -> `uv run pytest tests/api_client/test_execute_api.py`
- M3 D008 (Store/Engine 职责) -> ISSUE-03 -> TS-002/TS-003 -> 同上
- M3 D013 (内置常量) -> ISSUE-03 -> TS-002 (超时/大小上限) -> 同上
- M4 D003/D006 (事件契约/硬失败) -> ISSUE-03 -> TS-001/TS-003 -> 同上
- M5 决策 5 (历史不脱敏) -> ISSUE-03 -> TS-003 -> `uv run pytest tests/api_client/test_history.py`
- M1 D008 + M6 决策 1/2/3 (断言双形态/序列化/降级) -> ISSUE-04 -> TS-001/TS-002 -> `uv run pytest tests/api_client/test_assert.py`
- M4 D003 (done.assertions) -> ISSUE-04 -> TS-003 -> 同上
- M3 D008/D013 + M4 D003 (Runner 顺序/完整事件) -> ISSUE-05 -> TS-001 -> `uv run pytest tests/api_client/test_runner.py`
- M2 D011 (JUnit 输出物) -> ISSUE-05 -> TS-002 -> 同上
- M3 D009 (冲突即停) -> ISSUE-06 -> TS-002 -> `uv run pytest tests/api_client/test_sync.py`
- M2 D004-D007/D011 (git 仓库/.gitignore) -> ISSUE-06 -> TS-001/TS-003 -> 同上
- M3 D003/D004-4/D004-6/F005 (dist 托管/token 注入/no-store/CSP/漂移警告) -> ISSUE-07 -> TS-001/TS-002/TS-003 -> `uv run pytest tests/api_client/test_dist.py`

## 全局风险和停止条件
- 需要改变任一 DECISIONS/ADR/任务定义, 或扩大允许范围/触碰禁止范围时停止并回报.
- 代码事实与决策冲突时停止: 例如 testbed 端点不满足 Engine 测试面 → 属 MILESTONE-12 变更, 需 HITL, 不擅自改 testbed.
- JUnit 与 pytest --junitxml 兼容性: 以 xml.etree 解析 + 标签结构断言验证, 不依赖外部解析器.
- digest 认证 (testbed 手搓 RFC 7616) 与 httpx digest 交互以真实往返测试为准, 失败不降级为 mock.
- `uv run pytest` 全绿是每个 issue 提交前提; 中间态只允许本 issue 相关测试红.
