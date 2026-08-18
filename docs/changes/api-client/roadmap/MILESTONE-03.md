# 状态: 已关闭
# 类型: deliberate
# 阻塞于: MILESTONE-02

## 问题

后端核心架构. 后端是产品本体, SPA/CLI 皆为外壳:

- 核心库边界: 集合/环境/执行引擎/断言/runner/git 同步各模块的职责与依赖方向.
- CLI 形态: 内嵌核心库独立运行 (无需起服务) vs 纯 API client (必须连本地服务) vs 双模. 对 AI 使用场景的影响是关键取舍.
- FastAPI API 形态: REST 资源建模 vs RPC; SPA 与 (可能的) client 模式 CLI 共用同一 API.
- 执行代理设计: 请求 relay 格式 (可借鉴 Hoppscotch interceptor/proxyscotch 协议), 流式响应的回传方式 (若 MILESTONE-07 激活).
- 前端构建产物分发: build 产物 commit 进仓库? 首次运行自动 build? (影响 uv run 即起的成立方式).
- 本地安全模型: 绑定地址, CORS 白名单, 是否需要本地 token (侦查: Vite/esbuild dev server CVE 证明 127.0.0.1 攻击面真实存在).
