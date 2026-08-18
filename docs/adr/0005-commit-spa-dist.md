---
Status: accepted
---

# SPA 构建产物 dist/ commit 进源码仓库

SPA (Vue3) 构建产物 dist/ tracked 进源码仓库, FastAPI 直接静态托管. 一般直觉是生成物不入库, 这里反其道而行, 未来读者会问为什么.

## 备选方案

- 首次运行自动 build — 拒绝: 运行时需要 node, 直接违反硬约束 "任何有 uv 的设备 `uv run` 即起".
- 用户手动 build — 拒绝: 换机/换目录起服务前多一步, 违背目的地.

## 后果

- clone 即用, 零构建; node 仅是构建期依赖.
- 代价是仓库内有生成物: 改前端就带一份 dist diff, 用独立提交隔离 (如 `build: 更新 SPA dist`).
- 产物漂移风险 (改源码忘 build, 服务照常托管旧产物且无感知): 启动时比较 src/dist 时间戳, dist 旧则警告.
- token 注入只能是运行时动作 (启动时生成随机 token): 内存内占位符替换 serve, index.html 响应 `Cache-Control: no-store`, 防浏览器缓存旧 token 页面后 401.
- Vite/esbuild 的 dev server CVE 攻击面与本形态无关 (漏洞载体全是 dev-only 代码, build 产物里不存在).
