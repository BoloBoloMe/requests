# 交接 — M11 验收后未竟之事

日期: 2026-08-27 · 项目根: `/var/mnt/DATA/Workspace/requests` · 上一会话角色: M11 成品验收收官

## 下一会话用途

用户将让下一会话完成验收收官后的未竟之事 (两条线, 均为本会话结束时仍敞开的事实):

1. **G1~G5 五件待办**: 验收收官时用户裁决"要修/新增"已全部落档, 本会话未实现.
2. **git 推送**: 本地 main 领先 origin/main 12 个提交, 推送未成功.

## 现状 (其他文档未覆盖的增量事实)

- **M11 已验收关闭, Roadmap 已清空** — 验收四纲、12 条 AFK 裁定、缺口裁定于 2026-08-27 全部完成 (验收全貌见必读 1 与必读 2, 不再复述).
- **git 状态**: 上会话 10 个缺陷修复提交 + 本会话文档收口两提交 (`ef5eed2` roadmap/账本/手记, `b1c7f4a` 本交接文档), 共 12 个未推送. 工作区干净. **push 失败根因 (已实测)**: remote 为 https://github.com/BoloBoloMe/requests.git, 本机无 credential.helper 配置、无 ~/.git-credentials, GitHub 返回 "Password authentication is not supported"; 凭据方案用户尚未表态.
- **服务**: apic 已 stop (验收 F 步骤, status=stopped); testbed (端口 9000) 为本会话 nohup 后台所起, 可能仍活或随宿主环境消失. 服务/端口/token 一律现查 `/tmp/apic-acc/.local/service.json` (token 勿外泄入文档).
- **数据目录** `/tmp/apic-acc`: 集合 smoke (echo/bearer/sse/fail/vars) / acc (echo) / d-agent (echo/bearer); 环境 env (host=http://127.0.0.1:9000, 已激活); git 已绑 `/tmp/apic-remote.git` (init+sync 双提交, 与本地一致). `/tmp` 随关机清空, 重建途径记于必读 2.
- **未竟之事定义 (G1~G5)**: G1 run 含未解析变量条目整批 exit 2 → 改为跳过 (send 单条硬失败不变); G2 SPA 环境管理 UI (CRUD+切换激活, 数据仍落 environments/*.yaml); G3 集合运行结果回看 (run 后点条目带出该次日志/响应); G4 SPA 组件动画; G5 弹窗/下拉展开态点击外部自动折叠. 每条的需求原文、已勘察方案、涉及文件、验收判据、已知坑位全部记于必读 2 (08-27 详案手记), 本会话未再改动方案.
- 环境事实与基线: 后端 pytest 255 / SPA vitest 91 / typecheck+build 全绿为本会话结束时状态; 命令面形态 (`apic service status/token` 为子命令)、proxy 约束 (真 HTTP trust_env=False, 本机 curl 加 `--noproxy '*'`) 见必读 2/3.

## 必读推荐

1. `docs/changes/handoff/2026-08-26-m11-acceptance-resume.md` — 验收前件全貌: B~F 验收流程与判据、8 类已修缺陷 (提交号)、数据目录重建样例、命令面/测试基线/proxy 坑、G 系列方案初稿.
2. `docs/changes/handoff/2026-08-27-m11-closed-g-tasks-handoff.md` — G1~G5 详案 (方案/文件/判据/坑位/测试 fixture 模式), 本会话交接正文依赖它; 其中"提交时机未定"已被本文档现状节取代.
3. `docs/changes/api-client/UNAUTHORIZED_DECISIONS.md` — 12 条裁定全文 (含 08-27 补记 D-AFK-011): summary/done 契约语义 (G1/G3 判据), GET /environments 出处 (G2).
4. `docs/changes/api-client/roadmap/MILESTONE-11.md` + `ROADMAP.md` — 已关闭注记与目的地达成表述, 未决迷雾 (实时协议二期/AI 高阶) 按回访条件不动.
5. 代码位置: `src/api_client/runner.py`+`web/run.py` (G1), `src/api_client/web/` 路由+`store.py` 环境/state 函数 (G2), `spa/src/stores/app.ts`+`components/response/ResponsePane.vue`+`services/http.ts` (G3), `spa/src/components/sidebar/*` (G4/G5).

## 路线图

1. 起点: 空仓库. 目的地: 自用本地优先 Postman 替代品 — Python 后端 + SPA 供人 + CLI 供 AI, uv run 即起, 数据本地文件 git 管理.
2. 里程碑: M1~12 (决策/原型/执行链) 全关闭 → M11 成品验收 (2026-08-27: 四纲亲测 + 12 裁定复核 + 缺口裁定全过) → Roadmap 清空, 目的地达成.
3. 当前位置: 目的地已达成; 未竟之事两条线 — G1~G5 (已裁定已勘察未实现) + 12 提交未推送 (凭据未决).
4. 剩余距离: G1~G5 落地 (实现+测试+dist 入库+提交) + 推送凭据落地. 未决迷雾 (实时协议二期/AI 高阶) 不在范围.