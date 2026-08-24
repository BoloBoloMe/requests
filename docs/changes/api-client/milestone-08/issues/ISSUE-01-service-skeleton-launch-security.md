# ISSUE-01 — 服务骨架 + launch 幂等拉起 + 安全五件套

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: `uv run apic` 以随机端口 (bind(0), M3 D011-2) 前台起服务, 默认绑 `127.0.0.1` (D004-1, `--host` 显式才监听其他, 语义仅本机回环变体); 启动时在数据仓库 `.local/service.json` 原子写 (tmp+rename) `{port, token, pid}` (D011-1), 日志落 `.local/service.log`; `GET /health` 需 `X-Auth-Token` 头 (缺失/错误 401). launch 模块 (CLI 与服务共用, D002) 提供 `ensure_running(data_dir)`: flock 串行化 + 锁内二次检查 + service.json 校验 + pid 存活 (kill(pid,0)) + stale 防护 + 有限重试 (3 次) + ready 判定 = TCP 连通 + token 校验通过 (D011-4/5). 安全中间件 (D004): Host 头精确白名单 (localhost / 127.0.0.1 / [::1], 拒绝多 Host 头与 endswith 可绕过的伪造), 全 API 仅认 header token (SSE 握手额外接受 `?token=`), 不配置 CORS (无任何 `Access-Control-Allow-*` 放行头), 访问日志对 token 脱敏, 对 text/html 响应注入 CSP `script-src 'self'` (D004-6). `stop` 子命令按 `--data-dir` 定位停止 (D011-7). 数据目录默认 `~/.local/share/api-client/`, `--data-dir` 覆盖; launch 侧仅确保 `data-dir/.local/` 存在, 完整布局属 ISSUE-02. 适合 AFK: 进程模型/安全语义/测试矩阵全由账本钉死, 无待定产品问题.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (服务层可被双外壳真实调用)
- 决策: `docs/changes/api-client/milestone-03/DECISIONS.md`, D002/D004/D005/D011/D012/D014-5/D014-6

## 相关决策
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D001 (CLI 瘦客户端, launch 为唯一例外), D002, D004, D005, D011, D012, D014-5, D014-6

## 允许范围
- 新建 `src/api_client/` (含 `launch.py`, `__main__.py`, `web/` 骨架: app/安全中间件/health 路由), `tests/api_client/test_launch.py`, `tests/api_client/test_security.py`.
- 修改 `pyproject.toml`: [project.scripts] 增 `apic = "api_client.__main__:main"`; hatch packages 增 `src/api_client`; pytest testpaths 增 `tests/api_client`. 本 issue 不新增依赖.
- 数据仓库骨架: 仅 `data-dir/.local/` 目录创建与 service.json/service.log 写入.

## 禁止范围
- 不实现任何业务 API (CRUD/execute/run/sync 属 ISSUE-02 起); 不实现 CLI 命令面 (MILESTONE-10); 不实现 Windows 支持 (D012, flock/fcntl 按 POSIX).
- 不改 `src/testbed/` 与 `tests/testbed/`; 不改任何 DECISIONS/ADR.

## 代码定位提示
- 参照: `src/testbed/__main__.py` (getaddrinfo/bind(0)/uvicorn 起服样板), `pyproject.toml` ([project.scripts] 惯例), `docs/changes/api-client/milestone-03/DECISIONS.md` D011 (service.json schema/ready 判定/重试), `docs/changes/api-client/milestone-03/RESEARCH-local-security.md` 第 3 节 (Host 白名单语义与绕过形态).
- 阅读顺序: launch.py → web 中间件 → __main__ → 两个测试文件.

## TDD 切片
- TS-001 (launch 并发矩阵, D014-5):
  接缝: `launch.ensure_running(data_dir) -> ServiceInfo(port, token)` 公开 API, 用两个子进程并发调用同一 data-dir.
  测试用例: TC-001 — 两进程同时 ensure_running, 最终恰好一个活服务, 两次返回 (port, token) 一致, service.json 完整可读.
  先写的失败测试: `test_concurrent_ensure_running_yields_single_service` — 预期失败: 无 flock 串行化时双进程竞态写 service.json/起双服务.
  最小绿色实现范围: flock 锁文件 + 锁内二次检查 + 子进程 detach 拉起 (bind(0) 随机端口, 消除探测-绑定 TOCTOU) + service.json tmp+rename 原子写 + ready 判定 (TCP 连通 + token 校验) + 失败重试 3 次.
  不得测试: 锁的内部实现细节/协作者调用次数; 业务 API 行为.
  覆盖: D002, D011, D014-5.
- TS-002 (stale/失败路径, D011-4/5):
  接缝: 同上.
  测试用例: TC-002 — service.json 指向死 pid → 重新拉起; TC-003 — 端口被占或拉起连续失败 3 次 → 明确报错且给出原因.
  先写的失败测试: `test_stale_service_json_restarts` — 预期失败: 无 pid 存活校验时直接复用旧 service.json 指向已死进程.
  最小绿色实现范围: kill(pid,0) 存活校验 + 异常路径错误信息含原因.
  不得测试: 服务内部业务.
  覆盖: D011, D014-5.
- TS-003 (安全中间件参数化, D014-6):
  接缝: 中间件/依赖函数级参数化单测 + TestClient 薄测 (显式传 `Host: localhost` 头).
  测试用例: TC-004 — Host 白名单变体: 127.0.0.1 / localhost / [::1] 放行, `localhost.evil.com` 拒绝, 多 Host 头拒绝; TC-005 — header token 正确 200 / 缺失 401 / 错误 401, 非 SSE 端点 query token 一律 401, SSE 握手 `?token=` 放行; TC-006 — 所有响应无 CORS 放行头; TC-007 — 访问日志输出不含 token 明文.
  先写的失败测试: `test_host_allowlist_rejects_spoofed_host` — 预期失败: 无白名单时 `localhost.evil.com` 被放行.
  最小绿色实现范围: Host 精确匹配白名单 (拒绝重复 Host 头) + token 依赖校验 (header 主通道, SSE query 副通道) + 不配置 CORS 中间件 + 访问日志脱敏 (URL query token 与 header token 均不出现在日志) + HTML 响应 CSP `script-src 'self'`.
  不得测试: 业务路由行为; 未确认的 Host 变体.
  覆盖: D004, D005, D014-6.
- TS-004 (服务骨架冒烟):
  接缝: TestClient + 真进程 (`uv run apic serve --data-dir <tmp>`).
  测试用例: TC-008 — /health 带 token 200, 无 token 401; TC-009 — 真起服务后 curl /health 200.
  先写的失败测试: `test_health_requires_token` — 预期失败: 无 token 校验时匿名 200.
  最小绿色实现范围: FastAPI 壳 + health 路由 + token 依赖接入 + 服务入口 (serve/stop 子命令, `--host`/`--data-dir` 参数).
  不得测试: 业务逻辑.
  覆盖: D001, D004, D005, D011.
- TS-005 (service.json token 强度):
  接缝: launch 单测.
  测试用例: TC-010 — service.json 中 token 长度满足 ≥128 bit (secrets.token_urlsafe(32) = 256 bit).
  先写的失败测试: `test_service_json_token_entropy` — 预期失败: 短随机串不足 128 bit.
  最小绿色实现范围: 用 `secrets.token_urlsafe(32)` 生成.
  不得测试: 随机性分布.
  覆盖: D004-4, D011-1.

## 验证入口
- `uv run pytest tests/api_client/test_launch.py tests/api_client/test_security.py` — 全绿.
- `uv run apic serve --data-dir /tmp/apic-smoke &`; 读 `/tmp/apic-smoke/.local/service.json` 取 port/token; `curl -H "X-Auth-Token: $TOKEN" http://127.0.0.1:$PORT/health` 期望 200, 不带头期望 401.
- `uv run apic stop --data-dir /tmp/apic-smoke` 后进程退出, service.json 指向的 pid 不再存活.

## 风险提示
- 拉起竞态是 CLI 侧唯一真实复杂度 (D014-5 点名), 矩阵必须覆盖并发/stale/失败三路, 缺一路即裸奔.
- 日志脱敏若只滤 header 漏 query, 冒烟 curl 即可复现泄露; 脱敏须覆盖访问日志 URL 中的 token 参数.
- TestClient 默认 host=testserver 会触发 Host 白名单拒绝, 薄测必须显式传 `Host: localhost`.

## 停止条件
- 需要改变 D011 的 service.json schema、token 携带方式或本 issue 边界 (例如 stop 归属他处) 时停止.

## 适合 AFK 的原因
- 账本已钉死进程模型/安全语义与测试矩阵, 无待定产品/API/架构决策.

## 验收标准
- [ ] `uv run apic` 可前台起服务, service.json 含 {port, token, pid} 且 token ≥128 bit.
- [ ] 双进程并发 ensure_running 同一 data-dir 仅一个活服务且返回一致.
- [ ] stale service.json / 端口占用 / 拉起失败三路径行为符合 D011.
- [ ] Host 白名单 / token 校验 / SSE query 握手 / CORS 不放行 / 日志脱敏 / CSP 参数化单测全绿.
- [ ] `uv run apic stop --data-dir` 可停止指定数据仓库的服务.

## 被阻塞于
- 无
