# 状态: 已关闭
# 类型: task
# 阻塞于: MILESTONE-05, MILESTONE-08

## 问题

SPA 实现 (AFK 编码任务, 走 tdd-as-orchestra):

- Vue3 SPA 全量实现, 按 MILESTONE-05 原型与 MILESTONE-03 的 API 契约, 对接真实后端.
- 组件组合参照方向 A 侦查结论 (CodeMirror 6/拖拽/JSON 树等), 避开停更库 (react-json-view, Shoelace).
- 含 git 仓库绑定/同步管理界面.
- 构建产物分发方式按 MILESTONE-03 决策落地, 保证 uv run 即起.

## 关闭记录

- 关闭日期: 2026-08-25 (AFK 执行段).
- 执行: `docs/changes/api-client/milestone-09/EXECUTION.md` 任务书, 5 issues 链式 (骨架+token → 侧栏树/环境/变量 → 请求构建器 → 响应查看器+SSE → runner 内联+git), 每 issue TDD 切片红→绿.
- 产物: `spa/` 完整 Vite+Vue3+TS 工程 (src/api + services 可注入适配层 + components + stores + util), dist 入库; vitest 68 测试全绿; `npm run build` 通过.
- 提交: 8a82464 (I-01) / fd02050 (I-02) / b958c8c (I-03) / 495d83f (I-04) / 9932e3f (I-05) / be8e1b0 (build: 更新 SPA dist).
- 真实后端集成冒烟 (执行者完成, 非 HITL 遗留): apic serve 托管 + token 注入无占位符残留 + no-store + CSP; /execute SSE 端到端 meta/chunk/done 与 types.ts 一致; /history 落盘; run 事件序列 + report; /git/sync 未绑定 409 原样.
- 已知展示降级 (不阻塞): 无 git 状态端点 → GitRow branch 静态 main 无 ahead 数 (仅 ↑); 无文件夹/环境枚举端点 → 维持 ISSUE-02 既有降级; run 事件 item=collection/slug 与树按 slug 定位, 跨文件夹同名 slug 徽标串扰 (与后端口径一致).
- 视觉按原型变体 B (M5 决策 1-4); 日志/历史不脱敏 (决策 5).