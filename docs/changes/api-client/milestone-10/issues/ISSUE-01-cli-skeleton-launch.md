# ISSUE-01 — CLI 骨架 + launch 接入

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: `apic` 成为完整 CLI 程序 (08 已把 apic 临时指向 api_client.__main__ 的 serve/stop; 本 issue 将 [project.scripts] 的 `apic` 改指 `api_client_cli.__main__:main`, 承接全部命令面, 并保留 serve/stop 转发到 `api_client.launch` 使 `uv run apic serve` 路径不失效). 建立 `src/api_client_cli/` 骨架: argparse 命令树 (顶层 `--output` 全局选项 + `--data-dir` 全局选项 + 全部子命令占位), 用法错误统一 stderr `{"error":{code:"USAGE_ERROR",...}}` 且 exit 2 (prototype `_JSONErrorParser`, M4-D004). 服务 client 封装 (M3-D011): `client.connect(data_dir) -> (base_url, token, pid)` 调用 `api_client.launch.ensure_running` 幂等拉起 (服务在则不动作), 读 service.json 后 kill(pid,0) 存活校验 (stale 防护), 发起请求带 `X-Auth-Token`, 请求级重试一次 (D011-4). launch 接入是本 CLI 导入核心库的唯一例外 (M3-D001/D002). `service` 资源组三子命令: `status` (读 service.json + kill(pid,0) 存活判定, 输出 `{status,pid,port,version}`; version 可经 `GET /health` 获取, 不可达为 null), `stop` (委托 `launch` 停止, 接受 `--data-dir` 定位, M3-D005/D011-7), `token` (读 launch token, 输出 `{token}`, M3-D005). 数据目录默认沿用 `~/.local/share/api-client/` (M3-D011-6, 与 08 一致), `--data-dir` 覆盖. 适合 AFK: 进程模型/命令面/launch 语义已由账本钉死, 无待定产品问题 (唯一待 08 交付的 launch 已标于风险).

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-10.md`, CLI 实现 (AI 外壳骨架)
- 决策: `docs/changes/api-client/milestone-04/DECISIONS.md`, D001/D004 (命令面骨架/错误模型起点); `docs/changes/api-client/milestone-03/DECISIONS.md`, D001/D002/D005/D011/D012/D014-5

## 相关决策
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D001 (CLI 纯 API client, 不 import 核心库), D002 (launch 共享, CLI 唯一例外), D005 (token 子命令), D011 (服务发现/生命周期/请求级重试一次/stop 定位/data-dir 默认), D012 (POSIX only), D014-5 (launch/双 CLI 并发拉起矩阵)
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D001 (命令面: 资源组 service status/stop/token 属本 issue), D002 (非流式命令默认单 JSON 对象), D004 (退出码/用法错误 JSON)

## 允许范围
- 新建 `src/api_client_cli/` (入口 `__main__.py` 的 argparse 树+dispatch, `client.py` 服务 client+launch 接入, `errors.py` 错误/退出码, `output.py` 渲染原语, `contract.py` 契约常量源骨架), `tests/api_client_cli/` (fake HTTP fixture, `test_skeleton.py`, `test_service.py`, `test_launch_matrix.py`).
- 修改 `pyproject.toml`: [project.scripts] `apic` 改指 `api_client_cli.__main__:main`; hatch packages 增 `src/api_client_cli`; pytest testpaths 增 `tests/api_client_cli`.
- CLI 侧唯一 import 核心库处: `api_client.launch` (ensure_running / service.json / stop / token).

## 禁止范围
- 不实现任何业务命令执行 (send/run) 与资源查询 (collection/item/env/history/schema/guide) — 属本里程碑 ISSUE-02 起; 本 issue 命令树仅占位 + service 三子命令.
- 不 import 核心库除 launch 外的任何模块 (M3-D001); 不做变量解析/断言/执行.
- 不修改 `src/api_client/`、`tests/api_client/` (08), 不修改 `src/testbed/`、`tests/testbed/` (12), 不改任何 DECISIONS/ADR.
- 不做 Windows 支持 (M3-D012); 不做 TUI.

## 代码定位提示
- 参照: `docs/changes/api-client/prototypes/cli-shell/apic.py` (argparse 树/`_JSONErrorParser`/服务三命令/`main` 异常→退出码分派), `docs/changes/api-client/milestone-08/EXECUTION.md` 与 `issues/ISSUE-01` (launch API: `ensure_running(data_dir) -> ServiceInfo(port, token)`, service.json `{port,token,pid}`), `pyproject.toml`.
- 阅读顺序: `__main__.py` (入口/树/分派) → `client.py` (connect→ensure_running→请求+重试) → `errors.py`/`output.py` → 三个测试文件.

## TDD 切片
- TS-001 (骨架+用法错误, fake HTTP 不需要):
  接缝: `apic` 子进程; argparse 树.
  测试用例: TC-001 — 无命令/未知命令/缺必填参数 → stderr `{"error":{"code":"USAGE_ERROR",...}}`, exit 2, stdout 空; TC-002 — 顶层与各子命令 `--help` 存在且顶层 epilog 含 exit/error/event 三节机器契约 (骨架节).
  先写的失败测试: `test_no_command_exits_usage_error` — 预期失败: 无 argparse 树时行为未定义.
  最小绿色实现范围: 最小 argparse 树 (顶层 `--output`/`--data-dir` + 全部子命令占位) + JSON 用法错误 parser + dispatch 骨架 + help epilog 三节.
  不得测试: 业务命令行为 (未实现); 内部 dispatch 协作者次数.
  覆盖: M4-D001, M4-D004, M3-D001.
- TS-002 (服务 client + launch 接入 + 请求级重试, D014-4/5):
  接缝: fake HTTP 服务 (本地 socket, 回放 canned 路由) + 手写 service.json 指向 fake 服务 (pid 指向 fake 进程, 存活) + CLI subprocess 带 `--data-dir`.
  测试用例: TC-003 — connect 读到 service.json 的 port/token, 请求带 `X-Auth-Token`, 响应回显在 stdout; TC-004 — 首次请求 5xx/连接失败、重试一次后成功 (D011-4 请求级重试一次); TC-005 — 无业务命令时先 ensure_running: 服务在则不动作 (不重复拉起).
  先写的失败测试: `test_client_retries_request_once` — 预期失败: 未实现重试时首发失败即报错.
  最小绿色实现范围: `client.connect` 调 `api_client.launch.ensure_running` + 读 service.json + kill(pid,0) 存活校验 + httpx 请求带 token + 一次重试封装.
  不得测试: launch 内部并发细节 (08 已测); 业务解析.
  覆盖: M3-D001/D002/D011, D014-4.
- TS-003 (service status/stop/token, M3-D005/D011-7):
  接缝: fake service.json (+ 可选 fake /health 回 version) + CLI subprocess.
  测试用例: TC-006 — `service status` 输出 `{status,pid,port,version}` 且 status=running 当 pid 存活; TC-007 — `service token` 输出 `{token}` 与 service.json 一致; TC-008 — `service stop --data-dir <dir>` 委托 launch 停止, 输出 `{status:"stopped", pid}` 且进程结束.
  先写的失败测试: `test_service_token_matches_service_json` — 预期失败: 未接 launch 时无 token.
  最小绿色实现范围: 三个 service 命令 handler + launch 接入.
  不得测试: launch 内部停止实现.
  覆盖: M3-D005, D011-7, M4-D002.
- TS-004 (双 CLI 并发拉起矩阵, D014-5):
  接缝: 真 launch + 真服务 (08 已交付) 于临时 data-dir; 两个 `apic` 子进程并发 ensure_running/任意占位命令.
  测试用例: TC-009 — 两 CLI 并发拉起同一 data-dir → 仅一个活服务, 两进程读到一致 (port, token), service.json 完整.
  先写的失败测试: `test_two_cli_concurrent_ensure_running_single_service` — 预期失败: 无串行化时双写 service.json/起双服务.
  最小绿色实现范围: CLI 侧统一走 `api_client.launch.ensure_running` (flock/二次检查/原子写由 launch 保证), CLI 只负责每次 connect 调它.
  不得测试: launch 内部实现 (并发语义在 08 已测); 本切片验证 CLI 集成路径.
  覆盖: M3-D014-5, D011.

## 验证入口
- `uv run pytest tests/api_client_cli/test_skeleton.py tests/api_client_cli/test_service.py tests/api_client_cli/test_launch_matrix.py` — 全绿.
- `uv run apic --help` 可见完整命令面与 exit/error/event 三节契约.
- `uv run apic service token` 输出 `{"token": ...}`; `uv run apic service status` 读真实 service.json 输出 running/pid/port.
- `uv run apic service stop --data-dir <tmp>` 后对应进程退出 (launch 矩阵手工/自动冒烟).

## 风险提示
- `apic` script 归属 (08 临时指向 api_client.__main__): 改指 CLI 后必须保留 serve/stop 转发到 launch, 否则 08 的 `uv run apic serve` 冒烟失效; 冲突报父会话协调.
- launch 矩阵依赖 08 交付: 08 未交付前标 HITL/待预置, 不 mock 掉 launch (D014 不 layer).
- TestClient/本地 fake server 的 Host 头: CLI 走的 service.json port 是本机回环, 无 Host 白名单问题; 但若直接打 08 真服务需 `Host: 127.0.0.1`.

## 停止条件
- 需要改变 M3-D011 service.json schema、token 携带、stop 定位或本 issue 边界时停止.
- launch 契约 (ensure_running 返回形状/token 字段名) 与 08 不符 → 报父会话, 不擅自改 08.

## 适合 AFK 的原因
- 命令面骨架/launch 接入/服务三命令全由账本 (M3-D001/D002/D005/D011/D014-5 + M4-D001) 钉死, 进程/服务语义无待定决策; 唯一待 08 的 launch 矩阵子项已标预置.

## 验收标准
- [ ] `apic` 承载完整命令树占位 + 全局 `--output`/`--data-dir`, 用法错误 stderr JSON + exit 2; 顶层 help 含 exit/error/event 三节.
- [ ] 服务 client: ensure_running 幂等 / kill(pid,0) 存活校验 / 请求带 token / 请求级重试一次.
- [ ] `service status/stop/token` 符合 M4 原型的输出与 M3-D005/D011; stop 按 `--data-dir` 定位.
- [ ] 双 CLI 并发拉起矩阵 (D014-5): 仅一个活服务 + 一致 (port,token).

## 被阻塞于
- 无 (逻辑上待 08 交付 launch 用于 TS-004 真矩阵; skeleton/service 子项不依赖)
