# MILESTONE-03 事实调研: 本地安全模型 (绑定地址 / CORS / 本地 token)

调研日期: 2026-07 (基于当日可访问的官方 advisory 与文档)
性质: 纯事实探查, 不含设计决策. 每条结论标注置信度: [高] = 官方原文一手来源; [中] = 官方页面但经二手转述或多源交叉; [低] = 单一非官方来源.

## 1. Vite dev server 已知 CVE

### 1.1 CVE-2023-34092 本体

- CVE-2023-34092 = GHSA-353f-5xf4-qw67 (2023-06, High, CVSS 7.5): dev server 的 `server.fs.deny` 可用双斜杠 `//` 绕过 (如 `//.env`), 读取项目根附近受限文件. PoC 为 curl 直读 `.env`. 来源: [GHSA-353f-5xf4-qw67](https://github.com/advisories/GHSA-353f-5xf4-qw67). [高]
- 官方 Impact 原文: "Only users explicitly exposing the Vite dev server to the network (using `--host` or the `server.host` config option) are affected". 即官方将其定性为「显式暴露到网络的 dev server」问题, 不是 DNS rebinding. [高]
- 定性: 这是 dev server 文件服务中间件的路径规范化缺陷 (CWE-50), 攻击前提是「攻击者能让请求到达 dev server」— 到达途径可以是网络暴露, 也可以是受害者浏览器 (见 1.2). [高]

### 1.2 真正证明「绑 127.0.0.1 也不安全」的是另一条

- GHSA-vg6x-rcgg-rjx6 (CVE-2025-24010, 2025-01, Moderate): 默认 CORS 设置过宽 + WebSocket 连接不校验 Origin, 导致「任意网站可向 dev server 发任意请求并读取响应」. 官方原文: "This vulnerability even applies to users that only run the Vite dev server on the local machine and does not expose the dev server to the network." 来源: [GHSA-vg6x-rcgg-rjx6](https://github.com/advisories/GHSA-vg6x-rcgg-rjx6). [高] (CVE 编号对应关系来自 Red Hat/NTT Zen 等第三方库交叉, [中])
- 修复引入三件事: 收紧默认 CORS, 新增 `server.allowedHosts`, 给 HMR WebSocket 加一次性 token 校验 (保留 `legacy.skipWebSocketTokenCheck` 退出开关). [高]

### 1.3 DNS rebinding 在 Vite 语境里的位置

- Vite 官方文档 `server.allowedHosts` 的 DANGER 段原文: 设为 `true` 时 "allows any website to send requests to your dev server through DNS rebinding attacks, allowing them to download your source code", 并直接引用 GHSA-vg6x. 来源: [Vite server-options 文档](https://vite.dev/config/server-options.html). [高]
- 即: DNS rebinding 是 dev server 的官方确认攻击向量, 防御手段是 Host 头白名单 (`allowedHosts` 默认放行 `localhost` / `*.localhost` / IP). [高]

### 1.4 漏洞面持续性

- 2025-03 系列: CVE-2025-30208 (`?raw??` 绕过 fs.deny, GHSA-x574-m823-4x7w, EPSS 75%), 加 CVE-2025-31125 / 31486 / 32395 (多家厂商合并通报). 来源: [GHSA-x574-m823-4x7w](https://github.com/advisories/GHSA-x574-m823-4x7w), [IBM 公告](https://www.ibm.com/support/pages/node/7235981). [高] (30208 为一手, 31125/31486/32395 细节为二手 [中])
- 官方 [advisory 列表](https://github.com/vitejs/vite/security/advisories) 至 2026-06 仍在新增 dev server 文件读取类漏洞 (如 2026-04 "Arbitrary File Read via Vite Dev Server WebSocket" GHSA-p9ff-h696-f583, 2026-06 Windows 路径绕过 GHSA-fx2h-pf6j-xcff). 列表可见的 19 条全部针对 dev server 组件 (`server.fs`, dev WebSocket, dev HTML transform, host 检查), 唯一例外见第 3 节. [高]

## 2. esbuild

- GHSA-67mh-4wv8-2f99 (2025-02, Moderate 5.3, **无 CVE 编号**): serve 模式给所有响应 (含 SSE) 加 `Access-Control-Allow-Origin: *`, 恶意网页可 `fetch('http://127.0.0.1:8000/main.js')` 并读响应; 开 sourcemap 时可读未编译源码. 攻击场景原文明确是「恶意网页 -> 受害者浏览器 -> 127.0.0.1」, 与是否暴露网络无关. 来源: [GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99). [高]
- 修复 (esbuild 0.25.0, 其首个安全修复): 默认禁用 CORS + 校验 Host 必须匹配 `--serve=` 指定的 host; 同时披露 esbuild dev server 默认 host 是 `0.0.0.0`. 来源: [CHANGELOG-2025](https://github.com/evanw/esbuild/blob/main/CHANGELOG-2025.md). [高]
- 证伪: **CVE-2025-25280 与 esbuild 无关** — 它是 Century Systems FutureNet FA-215 路由器的缓冲区溢出. 来源: [Tenable CVE-2025-25280](https://www.tenable.com/cve/CVE-2025-25280). [高]

## 3. 关键区分: dev server 独有 vs 生产产物也受影响

- 上述全部 Vite/esbuild 漏洞的载体是 dev-only 代码: `server.fs.deny` 检查, `/@fs/` 路由, HMR WebSocket, dev HTML 中间件, host 校验. `vite build` 产物里这些代码不存在. [高]
- 已知唯一影响生产产物的反例: GHSA-64vr-g452-qvp3 = CVE-2024-45812 (DOM clobbering XSS in bundled scripts, 2024-09). 触发条件苛刻: build 输出格式显式设为 `cjs`/`iife`/`umd` 且宿主页面存在 scriptless HTML 注入点; 默认 ESM 输出走 `import.meta.url`, 不经过可被 clobber 的 `document.currentScript` 分支. webpack 同期同型漏洞 GHSA-4vvj-4cpr-p986. 来源: [GHSA-64vr-g452-qvp3](https://github.com/advisories/GHSA-64vr-g452-qvp3). [高]
- 事实结论: 「Vite build 静态产物 + FastAPI 托管」不在第 1/2 节任何 CVE 的攻击面内; 该形态的风险面转为 (a) 构建器把漏洞编进产物 (用受支持的 Vite 版本规避, 见上条反例), (b) 自己的 FastAPI 服务的本地攻击面 (见第 4 节). [高]
- 相关事实: uvicorn CLI 默认 `--host 127.0.0.1` (源码 click option default 原文可见), FastAPI 常规起法默认只听回环. 来源: [uvicorn main.py](https://github.com/encode/uvicorn/blob/master/uvicorn/main.py). [高]

## 4. 「绑定 127.0.0.1」的真实攻击面与业界做法

### 4.1 向量清单 (均有实证)

1. 恶意网页借浏览器向 localhost 发请求. 三个官方实证: esbuild GHSA-67mh (读构建产物), Vite GHSA-vg6x (官方明言本机-only 也中招), Sliver CVE-2026-34227 (见 4.2). [高]
2. CORS 不是写入保护: CORS 只挡跨站「读响应」, 不挡「简单请求」(如 form POST / 无预检 GET) 到达服务器. Chrome 官方将此类问题定性为针对本地设备的 CSRF, 是其 LNA 权限提示的立项理由. 来源: [Chrome LNA blog](https://developer.chrome.com/blog/local-network-access). [高]
3. DNS rebinding: 攻击域先解析公网 IP 加载页面, 再改解析到 127.0.0.1, 使后续请求「同源化」绕过 SOP 读响应. 防御 = 校验 Host 头. 两个官方先例原文: Jupyter `allow_remote_access` 帮助文本 "This protects against 'DNS rebinding' attacks" ([jupyter_server/serverapp.py](https://github.com/jupyter-server/jupyter_server/blob/main/jupyter_server/serverapp.py)); Vite `allowedHosts` DANGER 段 (见 1.3). [高]
4. 跨站 WebSocket: WS 握手不受 CORS 约束; Chrome LNA 目前也尚未覆盖 WebSocket/WebTransport/WebRTC (官方 blog 已知限制, 各带 crbug 链接). 防御须服务端做 Origin 校验或握手 token. 实证: Vite 修复 GHSA-vg6x 时给 HMR WS 加 token; Jupyter 的 tornado 层 `xsrf_cookies=True`. [高]
5. 浏览器侧收口进行中但不能依赖: Chrome 的 PNA (预检方案) 已官方搁置, 改推 LNA 权限提示 — Chrome 138 起可 flag 开启, Chrome 142 起推送; OS 层 Android/iOS/macOS 已各有本地网络权限. WS 未覆盖且仅 Chromium 系实现; Safari/Firefox 等价机制现状本次未核实. 来源: [Chrome LNA blog](https://developer.chrome.com/blog/local-network-access). [高]

### 4.2 事故级实证

- CVE-2026-34227 / GHSA-6fpf-248c-m7wm (Critical): Sliver 客户端内嵌 MCP 服务, 默认 `localhost:8080`, 无认证 + 所有响应 `ACAO: *`. 操作员点一个恶意链接, 攻击者即可经其浏览器操控全部 C2 会话 (列会话/任意文件读删); 若误配 `0.0.0.0` 则升级为直接未认证远程访问. 来源: [GHSA-6fpf-248c-m7wm](https://github.com/advisories/GHSA-6fpf-248c-m7wm). [高]
- 背景: 2025-2026 本地/0.0.0.0 无认证服务成为漏洞高发类 (MCP 生态综述: 大量服务 0.0.0.0 暴露 + 命令执行缺陷). 来源: [Composio: MCP Vulnerabilities](https://composio.dev/blog/mcp-vulnerabilities-every-developer-should-know). [中]

### 4.3 业界防护做法先例 (仅列举, 不构成决策)

| 做法 | 先例 | 来源 |
|---|---|---|
| 默认绑回环 | uvicorn 默认 `127.0.0.1`; Jupyter `allow_remote_access` 默认 False | uvicorn 源码 / jupyter_server 源码 [高] |
| Host 头白名单 (防 rebinding) | Jupyter `local_hostnames` (默认 `['localhost']`); Vite `server.allowedHosts` (默认 localhost/`*.localhost`/IP) | 两家官方文档/源码 [高] |
| Origin/默认 CORS 收紧 | Vite 2025-01 修复收紧默认 CORS; esbuild 0.25 直接禁 CORS + Host 匹配 | 两家 advisory/changelog [高] |
| 启动时随机 token | Jupyter: token 认证默认开启, 打进启动 URL 或 `Authorization` header, 官方明言不推荐关闭; Vite: 仅给 HMR WebSocket 加一次性 token | [Jupyter 安全文档](https://jupyter-server.readthedocs.io/en/latest/operators/security.html), GHSA-vg6x [高] |
| XSRF cookie | Jupyter `xsrf_cookies=True` (tornado) | jupyter_server 源码 [高] |
| 专用本地 agent 绕 CORS | Postman web 版需本地 Desktop Agent 的官方理由即「绕过浏览器 CORS」; 桌面版不需要 agent | [Postman 文档](https://learning.postman.com/v11/docs/getting-started/basics/about-postman-agent/) [高] (agent<->web 间握手鉴权细节公开文档未见, [未核实]) |
| Unix domain socket | uvicorn 支持 `--uds`; 浏览器 HTTP 客户端无法寻址 unix socket, 同机进程可独享该通道 | uvicorn 源码有该选项 [高]; 「浏览器不支持 unix socket」为高置信常识, 未见单独文档 [中] |

### 4.4 与 token 相关的机制覆盖面事实

- Host 校验: 只挡 DNS rebinding 类 (Host 不符的请求).
- CORS 白名单: 只挡跨站「读」.
- 两者都挡不住无预检的简单写请求盲发到达服务器 (CSRF 本体), 也不天然覆盖 WebSocket.
- 启动时随机 token 是同时覆盖「读+写+WS」三面的机制; Jupyter 因此把它设为默认, Vite 只对 WS 通道采用. [高]
- 敏感度对照 (事实而非决策): 本工具的本地 API 计划能力 = 读写本地文件数据 + 携带用户凭证向任意 API 发请求, 与 Sliver MCP / Jupyter (官方自述「访问 server 即可执行任意代码」) 同属高敏感本地服务类.

## 5. 未找到 / 未核实清单

- Postman Desktop Agent 与 web app 之间的鉴权细节 (公开文档未披露).
- webpack-dev-server `allowedHosts` 文档原文 (同类机制, 未逐字核实, 故未引用).
- Safari/Firefox 对 local network 请求的限制现状.
- 传闻中 Composio 关于 BrowserTools MCP「任意网页可读 localhost 凭证」的原始报告未检索到原文; 该项目可证实的是另一类问题 (命令注入 CVE-2026-7064, 第三方库条目), 不作为本报告证据.
- GHSA-vg6x-rcgg-rjx6 = CVE-2025-24010 的编号对应来自第三方库 (Red Hat XML / NTT Zen), 未读 NVD 原页.
