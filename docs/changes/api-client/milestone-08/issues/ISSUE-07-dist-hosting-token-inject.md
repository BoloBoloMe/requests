# ISSUE-07 — dist 托管 + token 注入

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: `spa/dist/` tracked (M3 D003, ADR 0005) 含占位 `index.html` (内嵌 token 占位符如 `__APIC_TOKEN__`); FastAPI 静态托管 `spa/dist/`; 启动时内存内 token 替换: index.html 响应时把占位符替换为当前 token 再 serve (D004-4, 运行时动作而非写文件), 该响应 `Cache-Control: no-store` (防旧 token 页面缓存后 401); 启动时比较 SPA 源码目录 (约定 `spa/src/` (MILESTONE-09 同此约定), 本里程碑为占位) 与 `dist/` 时间戳, dist 旧于源码则警告 (D003/F005, 防产物漂移), 源码目录不存在则跳过. HTML 响应的 CSP `script-src 'self'` 头由 ISSUE-01 中间件注入, 此处验证页面携带 (D004-6). 适合 AFK: 托管/注入/缓存语义已由账本与 ADR 钉死.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (SPA 托管面)
- 决策: `docs/changes/api-client/milestone-03/DECISIONS.md`, D003/D004-4/D004-6/F005; `docs/adr/0005-commit-spa-dist.md`

## 相关决策
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D003 (dist commit 进源码仓库, FastAPI 静态托管, 启动时间戳警告), D004-4 (token 注入托管页, index.html no-store), D004-6 (CSP `script-src 'self'`), F005 (dist 产物漂移风险)
- `docs/adr/0005-commit-spa-dist.md`: 后果节 (内存内占位符替换 serve/no-store/时间戳警告)

## 允许范围
- 新建`spa/dist/index.html` 占位 (含占位符) 与 `spa/src/` 源码占位目录 (SPA 源码约定位置, 本里程碑仅用于时间戳比较), `src/api_client/web/static.py` (静态托管+注入), `tests/api_client/test_dist.py`.
- 提交 dist 占位文件使其 tracked (git add).

## 禁止范围
- 不自动构建 SPA (需 node, 违反硬约束, ADR 0005 排除); 不把 token 写进磁盘文件 (仅内存替换); 不做 dist 之外的静态目录托管.
- 不改 `src/testbed/`; 不实现 SPA 本身 (MILESTONE-09); 不改任何 DECISIONS/ADR.

## 代码定位提示
- 参照: `docs/adr/0005-commit-spa-dist.md` (内存内占位符替换 serve / no-store / 时间戳警告 / 独立提交隔离 diff 噪音), `docs/changes/api-client/milestone-03/DECISIONS.md` D003/D004-4/F005, ISSUE-01 的 token 生成与 CSP 中间件 (本 issue 消费).
- 阅读顺序: static.py (时间戳检查 → 托管 → 注入 → no-store) → test_dist.py.

## TDD 切片
- TS-001 (托管+注入, D004-4):
  接缝: TestClient GET / (首页).
  测试用例: TC-001 — 响应 HTML 含当前 token 值且不含占位符; TC-002 — 响应头 `Cache-Control: no-store`; TC-003 — 响应头含 CSP `script-src 'self'` (ISSUE-01 中间件); TC-004 — 换一个 token 再 GET, HTML 注入新 token (证明内存替换非写盘).
  先写的失败测试: `test_index_injects_current_token_no_placeholder` — 预期失败: 占位符原样返回或注入旧 token.
  最小绿色实现范围: 静态托管 dist + index.html 占位符替换 + no-store + 复用 CSP 中间件.
  不得测试: token 生成 (ISSUE-01); SPA 内容.
  覆盖: M3 D003/D004-4/D004-6.
- TS-002 (时间戳警告, D003/F005):
  接缝: `static.check_dist_staleness(web_dir, dist_dir) -> bool` 纯函数 + 启动日志断言.
  测试用例: TC-005 — spa/dist 最新 mtime 旧于 spa/src 最新 mtime → 返回 True 且启动日志含警告 (含 dist 与源码路径提示); TC-006 — spa/dist 新于 spa/src → 无警告; TC-007 — spa/src 目录不存在 → 跳过不警告.
  先写的失败测试: `test_stale_dist_warns` — 预期失败: 未实现时间戳比较.
  最小绿色实现范围: mtime 比较 + 启动警告输出.
  不得测试: 构建流程 (不存在).
  覆盖: M3 D003, F005.
- TS-003 (占位产物 tracked):
  接缝: git 状态断言.
  测试用例: TC-008 — `spa/dist/index.html` 与 `spa/src/` 占位文件存在于仓库且 tracked (`git ls-files` 包含).
  先写的失败测试: `test_dist_placeholder_is_tracked` — 预期失败: 未提交或路径缺失.
  最小绿色实现范围: 占位文件创建与 git add 提交 (独立提交, 如 `build: 占位 dist` 隔离噪音, ADR 0005).
  不得测试: 构建产物内容.
  覆盖: M3 D003.

## 验证入口
- `uv run pytest tests/api_client/test_dist.py` — 全绿.
- 真服务冒烟: `uv run apic serve --data-dir /tmp/apic-dist &`; `curl -i http://127.0.0.1:$PORT/` 观察: HTML 含实际 token 且无占位符, `Cache-Control: no-store`, `Content-Security-Policy: script-src 'self'`.
- `git ls-files spa/` 非空 (占位已提交).
- 手工: `touch spa/src/placeholder` 后重启服务, 启动日志出现 dist 时间戳警告.

## 风险提示
- token 若写入磁盘文件再 serve, 违背 "内存内替换" 且污染仓库; TS-004 证明换 token 后页面随之变化.
- 漏 no-store 时浏览器缓存旧 token 页面 → 页面内 token 失效 401 (D004-4 防的正是此态), TC-002 钉死.
- 时间戳比较粒度 (目录 mtime vs 最新文件 mtime) 不一致会误报/漏报, 以 "最新 mtime" 口径并在 TC-005/006 钉死.

## 停止条件
- 需要运行时构建 SPA、把 token 写盘或改变 spa/dist 目录约定时停止.

## 适合 AFK 的原因
- 托管/注入/缓存/警告语义已由账本与 ADR 0005 钉死, 占位产物无产品内容依赖.

## 验收标准
- [ ] dist/ 占位 tracked 进仓库; 首页经内存内 token 替换 serve, 无占位符残留.
- [ ] index.html 响应 `Cache-Control: no-store` + CSP `script-src 'self'`.
- [ ] 换 token 后页面注入新 token (证明非写盘).
- [ ] spa/dist 旧于 spa/src 时启动警告, spa/src 缺失时跳过.

## 被阻塞于
- ISSUE-01 (服务骨架/token 生成/CSP 中间件)
