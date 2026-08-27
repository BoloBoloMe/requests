# 交接 — MILESTONE-11 成品验收 (HITL) 接手

日期: 2026-08-25 · 项目根: `/var/mnt/DATA/Workspace/requests` · 上一会话角色: AFK 执行 + 验收引导

## 下一会话用途

用户已另开会话开始 MILESTONE-11 成品验收 (HITL). 新会话承接: 引导用户走完验收剩余步骤 (SPA/CLI/agent/git), 收尾复核 AFK 裁定, 关闭 M11, 更新 Roadmap (验收通过 = 到达目的地, Roadmap 清空).

## 现状

- Roadmap: MILESTONE-01~10, 12 全关闭; 前沿 = MILESTONE-11 (`docs/changes/api-client/roadmap/MILESTONE-11.md`, 状态待处理/类型 task/HITL; 验收四纲: uv run 即起, SPA 日常调试, CLI 被 agent 调用, git 同步跑通).
- 代码与测试全绿: 后端 `src/api_client/` + CLI `src/api_client_cli/` + SPA `spa/` (dist 入库); pytest 253 全绿, vitest 68 全绿, npm run build 过; 工作区干净; 最新提交 `8a5d467` (路线图收口), 未推送.
- **验收现场 (用户 session 正在跑)**: 终端 A `uv run testbed --port 9000` 运行中; 终端 B `uv run apic serve --data-dir /tmp/apic-acc` 运行中 (端口/token 在 `/tmp/apic-acc/.local/service.json`); 数据目录 `/tmp/apic-acc` 已建; SPA/CLI 步骤尚未走.
- **上一会话已纠正一处验收指引笔误 (勿再犯)**: status/token 不是顶层命令. 顶层命令面 = send/run/collection/item/env/history/service/schema/guide + serve/stop 转发; 正确形态 `apic service status` / `apic service token` (见 `src/api_client_cli/__main__.py` 枚举).

## 验收流程 (已给用户的步骤, 新会话沿用复核)

A. 服务发现: `apic service status --data-dir /tmp/apic-acc`; `apic service token`; `cat .local/service.json` 三字段 {port, token, pid}.
B. SPA: 浏览器 `http://127.0.0.1:<port>/` → 双栏界面非占位页; 建集合 smoke + 条目 `GET http://127.0.0.1:9000/echo?a=1` → send → Body/Headers/日志三 tab 完整; `/auth/bearer` bearer=demo-token → 200; 断言 status eq 200 ✓ → eq 500 ✗ 明细; 环境胶囊 env(host=127.0.0.1:9000) + URL `{{host}}` 解析预览; `/sse?count=5` 流式 5 帧; 集合级 ▶ 运行三态徽标 + 失败红字 + 跳断言 tab; `apic history list` 见记录.
C. CLI: help/schema/guide; `collection list`; `send smoke/<slug> --output pretty` exit 0; 断言失败 exit 1; 不存在条目 exit 4 + stderr candidates; URL 含 `{{missing}}` → exit 2 UNRESOLVED_VARIABLES 且 stdout 空; `run smoke` → summary; **`--var api_token=demo-token` → /auth/bearer 200 (vars 契约补丁验收点)**.
D. agent 调 CLI (标 HITL): 起全新上下文子代理, 仅经 --help 或 schema+guide 自学, 完成建集合/条目 → send → run, 汇报退出码.
E. git: `git init --bare /tmp/apic-remote.git` → `curl -H "X-Auth-Token: $TOKEN" -X POST -d '{"remote_url":"/tmp/apic-remote.git"}' http://127.0.0.1:<port>/git/bind` → SPA「同步」按钮 → `git -C /tmp/apic-remote.git log` 有 init+sync 提交, `ls-tree -r main | grep -c secrets` = 0; 改条目再同步有新提交.
F. 收尾: `apic stop --data-dir /tmp/apic-acc` → service status 转 stopped.

## 必读推荐

1. `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` — AFK 执行段 12 条自主裁定 (D-AFK-001~012), **M11 关闭前提 = 用户逐条复核认可**; 重点: D-AFK-005/007 (done.error 字段, done.status 三态 int/null+error/"assert_failed"), D-AFK-011/012 (execute/run 请求体 vars 覆盖层, GET /environments 补丁), D-AFK-009 (单条目异常不中断整批), D-AFK-010 (git bind 幂等/dirty 语义). 若用户否决任一, 需给出改动点.
2. `docs/changes/api-client/roadmap/ROADMAP.md` + `MILESTONE-11.md` — 验收目的地/前沿/未决迷雾 (实时协议二期与 AI 高阶两项按回访条件不动; AI 高阶回访触发点 = M10 关闭后, 现已触发但属规划外, 需用户裁定是否立项).
3. 三份 EXECUTION.md 完成定义节 (`milestone-08|09|10/EXECUTION.md`) — 验收判据原文 (uv run 即起 / dist 托管冒烟 / CLI 命令面与退出码 / agent 场景).
4. 代码事实 (只读): `src/api_client_cli/__main__.py` (命令面枚举与 --output/--data-dir 全局参), `src/api_client/launch.py` (ensure_running/stop/token 公开 API), `src/api_client/web/*.py` (路由与请求/响应形状), `spa/src/` (页面结构, 便于引导用户在 UI 上找入口).
5. 三个已知小缺口 (验收时向用户确认接受与否): (a) SPA git 行 branch 静态 "main"、无 ahead 数 (后端无 git 状态端点, 仅显示 ↑); (b) run 集合含未解析变量条目 → 整批硬失败 exit 2 (M4-D006 语义, 非跳过); (c) CLI `service status` 的 version 字段为 null (接口 /health 无 version 字段).

## 路线图

1. 起点: 空仓库. 目的地: 自用本地优先 Postman 替代品 — Python 后端本体 + SPA 供人 + CLI 供 AI, 数据本地文件 git 管理, 任何有 uv 设备 `uv run` 即起.
2. 决策/原型链 (前段已关闭): M1 范围 → M2 数据格式 → M3 后端架构 (六模块+安全五件套+launch) → M4 CLI 命令面原型 (dogfood 三轮) → M6 断言 DSL (双形态) → M5 SPA 原型 (双栏纵向流变体 B) → M12 测试后端 (62 测).
3. 执行段 (上一会话 AFK 完成): M08 后端核心 7 issues → M09 SPA 5 issues → M10 CLI 4 issues; 契约协调补丁 2 个 (e02e4bf vars 覆盖, de7654d GET /environments); 全程 12 轮 TDD + 8 轮 code-review.
4. 当前位置: **验收 (M11) 进行中** — 靶子/服务已起, SPA 与 CLI 步骤未走; 剩: 走完 B~F → 复核 12 条裁定 → 关闭 M11 → Roadmap 清空 = 到达目的地.
5. 未决迷雾 (不动): 实时协议二期 (WS/SSE 转发, 回访条件: 调试 SSE 端点且 curl 不够用两次以上); AI 高阶能力 (OpenAPI 转集合等, 回访触发点已到, 需用户决定).

## 其他 (执行段经验, 涉及时有用)

- 子代理选型先例: 执行者 kimi-coding/k3 (thinking high), 审核者 opencode-go/kimi-k2.7-code (thinking high), 对抗对须异模型; 大任务单个执行者约 45min 触上下文上限, 中途超时则新起执行者接力 (磁盘产物保留), 勿 resume 高占用会话.
- 挂死教训 (已修复, 勿回退): engine `_run` 收尾 put 在 finally (防消费者永久挂起), pytest-timeout=300, conftest fixture 用 select 轮询 + killpg 清理 (防 testbed 孙进程泄漏); 环境有 SOCKS 代理变量, 真 HTTP 测试/Engine 一律 trust_env=False; 注意 `pkill -f 'testbed'` 会匹配调用者自身命令行, 清理按 pid.
- 敏感信息: 无 API key/密码在仓库 (demo 凭证 demo/demo-pass, demo-token, demo-key, digest demo/digest-pass 全为测试后端固定值); service.json 含运行期 token, 不入库 (.gitignore).