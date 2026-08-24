# ISSUE-06 — Sync git 同步

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: Sync 模块封装 git 绑定/提交/推拉 (M3 D008: 只碰数据仓库文件路径, 不进核心库依赖链): 绑定 = 数据仓库 `git init` + 自动写入 .gitignore (忽略 `.local/` 与 `*.secrets.yaml`; `files/` 进不进 git 用户自决, 不自动忽略; M2 D004/D006) + 初始 commit + `remote add origin`; 同步 = `add -A` + `commit` + `pull --rebase` + `push` (M3 D009); 遇冲突/dirty 异常即停, 把 git 原样输出抛给用户手工处理, 绝不自动合并 (D009). RPC 端点 (M3 D010): `POST /git/bind` {remote_url}, `POST /git/sync`; 未绑定时明确报错. 环境文件必须 tracked (M2 D005), secrets 永不进 git (M2 D006, 靠 .gitignore), 历史在 `.local/` 不进 git (M2 D011). 适合 AFK: git 操作语义与冲突策略已由账本钉死.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (git 同步)
- 决策: `docs/changes/api-client/milestone-03/DECISIONS.md`, D008/D009/D010; `docs/changes/api-client/milestone-02/DECISIONS.md`, D004-D007/D011

## 相关决策
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D008 (Sync 职责: 只碰数据仓库文件路径), D009 (冲突即停: add/commit/push/pull --rebase, 绝不自动合并, 原样抛 git 输出), D010 (POST /git/sync RPC 形态)
- `docs/changes/api-client/milestone-02/DECISIONS.md`: D004 (数据目录即独立 git 仓库), D005 (环境文件必须 tracked), D006 (secrets gitignored, 绑定仓库时自动写 .gitignore 规则), D007 (.local gitignored), D011 (历史 gitignored)

## 允许范围
- 新建 `src/api_client/sync.py`, `src/api_client/web/git.py` (RPC 路由), `tests/api_client/test_sync.py`.
- 测试用临时目录创建真实 git 仓库 + 本地 bare remote (POSIX, git 可用为前提).

## 禁止范围
- 不自动合并冲突 (D009); 不修改 .gitignore 之外的用户文件; 不做 fetch/merge/rebase 以外的 git 语义扩展.
- 不改 `src/testbed/`; 不实现 CLI git 入口 (CLI 不接管 git, 既定约束); 不改任何 DECISIONS/ADR.

## 代码定位提示
- 参照: `docs/changes/api-client/milestone-02/DECISIONS.md` D004 (目录布局: .local/ 与 secrets 须忽略, environments/ 须 tracked), D006 (绑定仓库时自动写 .gitignore), `docs/changes/api-client/milestone-03/DECISIONS.md` D009 (冲突即停语义).
- 阅读顺序: sync.py (bind → sync 两步) → git 路由 → test_sync.py.

## TDD 切片
- TS-001 (绑定与同步, M2 D004/D005/D006):
  接缝: `sync.bind(data_dir, remote_url)` / `sync.sync(data_dir)`, 用 tmp 数据仓库 + 本地 bare remote (真实 git, 非 mock).
  测试用例: TC-001 — bind 后数据仓库是 git 仓库, .gitignore 含 `.local/` 与 `*.secrets.yaml`, 初始 commit 存在; TC-002 — 环境文件被 tracked, secrets 文件被忽略 (git status 不出现); TC-003 — 修改条目 + 同步 → bare remote 出现对应提交; TC-004 — 未绑定调用 sync → 明确错误.
  先写的失败测试: `test_bind_writes_gitignore_and_tracks_env` — 预期失败: 无自动 .gitignore 时 secrets 文件被 tracked.
  最小绿色实现范围: git init/remote add/初始 commit/.gitignore 自动写入/add/commit/push/pull --rebase 封装.
  不得测试: 远端网络 (本地 bare repo 即真远端); git 内部实现.
  覆盖: M2 D004/D005/D006, M3 D008.
- TS-002 (冲突即停, M3 D009):
  接缝: 同上, 构造冲突场景.
  测试用例: TC-005 — 远端与本地同一条目文件分别修改 → pull --rebase 冲突 → sync 停止, 抛 git 原样输出 (含冲突文件与冲突标记信息), 不自动解决; TC-006 — 工作区 dirty (未提交改动) → 同步停止并报错.
  先写的失败测试: `test_sync_conflict_stops_with_git_output` — 预期失败: 若实现自动合并或吞掉 git 输出则测试挂.
  最小绿色实现范围: 任何非零退出/冲突检测 → 停止并原样透传 git 输出.
  不得测试: 合并策略 (不存在).
  覆盖: M3 D009.
- TS-003 (RPC 壳薄测, D014-3):
  接缝: TestClient.
  测试用例: TC-007 — POST /git/bind 合法 remote 200, 非法 URL 明确错误; POST /git/sync 未绑定 → 明确错误; 绑定后 200; TC-008 — 无 token 401.
  先写的失败测试: `test_git_sync_unbound_errors` — 预期失败: 未绑定无明确错误.
  最小绿色实现范围: 路由薄壳 + 错误透传.
  不得测试: git 语义 (Sync 已测).
  覆盖: M3 D010.

## 验证入口
- `uv run pytest tests/api_client/test_sync.py` — 全绿 (前提: POSIX + git 可用).
- 真服务冒烟: `uv run apic serve --data-dir /tmp/apic-git &`; 带 token `curl -X POST -H "Content-Type: application/json" -H "X-Auth-Token: $TOKEN" -d '{"remote_url":"/tmp/remote.git"}' http://127.0.0.1:$PORT/git/bind` 后 `curl -X POST -H "X-Auth-Token: $TOKEN" http://127.0.0.1:$PORT/git/sync`; 检查 `/tmp/remote.git` 出现提交且 secrets 不在其中.

## 风险提示
- 自动合并是 D009 明确禁止 (反方攻击 D5-A 裁决), 任何"智能"处理都是回归.
- .gitignore 若漏 `.local/`, 历史 (含响应敏感数据) 会被提交, 违反 M2 D011; TC-002 钉死.
- git 输出原样透传是 D009 承诺, 不得清洗/摘要化.

## 停止条件
- 需要改变冲突策略、同步顺序 (add/commit/pull --rebase/push) 或 .gitignore 规则时停止.

## 适合 AFK 的原因
- git 操作面与冲突策略已由账本钉死, 本地 bare repo 可完全离线验证.

## 验收标准
- [ ] bind: git init + 自动 .gitignore (.local/ 与 *.secrets.yaml) + 初始 commit + remote add.
- [ ] sync: add/commit/pull --rebase/push; 环境 tracked, secrets 与历史永不进 git.
- [ ] 冲突/dirty 即停, 原样抛 git 输出, 不自动合并.
- [ ] POST /git/bind 与 POST /git/sync RPC 语义与 401 正确.

## 被阻塞于
- ISSUE-02 (Store/数据仓库布局/领域对象)
