# MILESTONE-03 决策账本 — 后端核心架构

产物归属: `docs/changes/api-client/roadmap/MILESTONE-03.md` (已关闭).
盘问方式: deliberate skill, 三轮盘问 + 反方攻击 (子代理) 与自扫并行, 用户逐条确认.
输入约束: [MILESTONE-01 账本](../milestone-01/DECISIONS.md), [MILESTONE-02 账本](../milestone-02/DECISIONS.md) (记作 M2-D001 等), [本地安全调研](RESEARCH-local-security.md) (反方攻击发现已逐项裁决并入).
上游账本决策记作 "M1-D007"/"M2-D011" 等.

## 决策

### D001 — CLI = 纯 API client (瘦客户端)

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: CLI 不含业务逻辑, 不 import 核心库, 必须连本地 FastAPI 服务才能工作. CLI 内嵌幂等拉起: 服务在则不动作, 不在则拉起, 拉起后常驻. 服务是唯一执行与安全边界.
- 理由: 用户明确偏好瘦客户端 — 客户端只是人与服务之间的交互界面, 不实际干活; 排除内嵌模式 (核心库 import) 与双模 (降级路径与服务拉起失败共享同一环境病灶, 几乎不触发却要双份测试).
- 依赖事实: F001, F004
- 预计影响: CLI 全部实现, 服务进程模型, 核心库包装方式. 见 [ADR 0004](../../../adr/0004-thin-cli-service-convergence.md)
- 相关 issue: 待关联

### D002 — launch 模块共享 (D001 的纯度修正)

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 拉起/服务发现逻辑抽为独立 launch 模块, CLI 与服务共同 import. launch 只含进程管理/端口/token 发现, 不含业务逻辑; 它是 "CLI 不 import 核心库" 的唯一例外.
- 理由: 反方攻击 D1-C: 不共享则 CLI 与服务各写一份启动协议 (service.json schema), 双写漂移; 瘦客户端的本意是不含业务逻辑, launch 是进程管理而非业务.
- 预计影响: 核心库包结构 (launch 独立成包/模块), CLI 与服务双方.
- 相关 issue: 待关联

### D003 — SPA 构建产物 dist/ commit 进源码仓库

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: dist/ tracked, FastAPI 静态托管; 启动时 token 注入 = 内存内占位符替换 serve, index.html 响应 `Cache-Control: no-store` (防旧 token 页面缓存后 401); 启动时比较 src/dist 时间戳, dist 旧于源码则警告 (防产物漂移).
- 理由: 目的地硬约束 "任何有 uv 的设备 `uv run` 即起"; node 仅是构建期依赖; diff 噪音用独立提交隔离 (如 `build: 更新 SPA dist`). 排除: 首次运行自动 build (需 node, 违反硬约束), 用户手动 build (违背目的地).
- 依赖事实: F005
- 预计影响: 仓库布局, 服务静态托管层, 启动流程. 见 [ADR 0005](../../../adr/0005-commit-spa-dist.md)
- 相关 issue: 待关联

### D004 — 本地安全模型五件套

- 状态: 当前有效
- 约束性: 必须遵守
- 内容:
  1. 默认绑 `127.0.0.1`, `--host` 显式开启才监听外部 (语义见 D005);
  2. Host 头白名单: 精确匹配 localhost/127.0.0.1 + IPv6 loopback, 拒绝多 Host 头 (防 DNS rebinding; endswith/包含匹配可被 `localhost.evil.com` 绕过);
  3. CORS 默认不放行任何跨站 origin (SPA 同源托管, 本来不需要 CORS);
  4. 启动随机 token (≥128 bit): 注入 SPA 托管页, 写入 service.json (D011 单一权威源); 所有 API 仅认 header token; 仅 SSE 握手额外接受 `?token=` (EventSource 无法自定义 header, F002); 访问日志对 token 脱敏;
  5. 不做 XSRF cookie (负面决策, 不计入件数; header token 已免疫表单盲写, 不重复设防);
  6. SPA 侧: CSP `script-src 'self'` + 响应体默认纯文本渲染 (token 在页面内, XSS 即全 API 沦陷, 且 Engine 可打内网构成 SSRF 放大).
- 理由: RESEARCH-local-security.md 事实链: 绑 127.0.0.1 不等于安全 (恶意网页借浏览器 CSRF 盲写 / WS 不受 CORS 挡 / DNS rebinding 绕 SOP 读响应, Vite/esbuild/Sliver CVE 实证); 本工具是高敏感本地服务 (读写本地文件 + 携带凭证发任意请求, 与 Jupyter/Sliver MCP 同类); 启动随机 token 是唯一同时覆盖读/写/WS 三面的机制 (Jupyter 默认开启先例).
- 依赖事实: F002, F003
- 预计影响: 服务中间件层, SPA 托管页模板, CLI token 读取, 安全中间件参数化单测 (D014).
- 相关 issue: 待关联

### D005 — `--host` 语义与 token 子命令

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: `--host` 仅服务 WSL/容器端口转发等本机回环变体, 不承诺远程访问 (外部浏览器拿不到 token, 且 CORS 挡跨源读响应); 提供 CLI `token` 子命令显示/复制当前 token, 供非浏览器客户端手动携带.
- 理由: 反方攻击 D3-B: 不澄清则 --host 形同虚设 (外部客户端拿不到 token) 且语义误导.
- 预计影响: CLI 命令面, 服务启动参数文档.
- 相关 issue: 待关联

### D006 — 执行引擎内嵌服务进程

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 请求执行引擎是核心库模块, 运行于 FastAPI 服务进程内; 不做独立代理进程, 不存在跨进程 relay 协议 (Hoppscotch interceptor/proxyscotch 模式不适用自用单机). Engine 用 async httpx, 事件经 asyncio.Queue 出流 (同步 httpx 会卡死事件循环上的全部 API). SSE 断连不取消底层执行, 执行继续至完成或连接关闭, 按 M2-D011 规则落盘 (连接关闭时聚合已收事件落盘).
- 理由: Q1=b 后所有执行已 100% 收敛在服务进程, 独立代理只剩隔离性一个理由, 不值一个进程加一套协议; 第二套进程管理会使 D001 竞态问题翻倍.
- 预计影响: 核心库 Engine 模块, 服务 /execute 端点.
- 相关 issue: 待关联

### D007 — 流式回传: SSE + JSONL, 单一事件模型

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: SPA↔服务流式回传用 SSE (浏览器 EventSource, 单向够用, 自动重连); CLI 收 JSONL 逐行事件 (AI 零歧义解析); 同一 `/execute` 端点按 Accept 协商 `text/event-stream` vs `application/x-ndjson`, 内部是单一事件模型 (meta/chunk/done), 两种编码只是序列化差异. 排除 WebSocket (能力过剩 + 攻击面 + WS API 同样不能自定义 header, 无认证优势) 与不流式 (违背 M1-D001 流式渲染决策).
- 预计影响: 服务 /execute 端点, SPA 响应查看器, CLI 输出渲染; MILESTONE-04 (CLI 原型) 直接输入.
- 相关 issue: 待关联

### D008 — 核心库模块边界

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 六个 module + launch (D002), 依赖方向单向:
```text
Runner ──► Engine ──► Resolve ──► Store
            │  │
            │  └──► Assert
            └──► Store (写历史, M2-D011 发送即记录)
Sync ──► 只碰数据仓库文件路径, 不进上述链
launch ──► 被 CLI 与服务共同 import (D002)
```
  - **Store**: 数据仓库读写唯一入口. 藏 YAML schema/seq 排序/secrets 合并/.local 状态/历史落盘; 全部写走 tmp+rename 原子写 (防 Runner 批量写与 Sync commit 并发交叠出半写文件). 出进皆为领域对象.
  - **Resolve**: 请求条目 + 环境 → 可执行请求. 藏变量优先级 (M2-D012)/集合级默认继承 (M2-D010)/动态变量白名单 (M1-D010).
  - **Engine**: 可执行请求 → 事件流 (meta/chunk/done). 藏 httpx/五种认证/multipart/取消/超时; 副作用只有经 Store 写历史.
  - **Assert**: 响应 + 断言定义 → 结果列表. DSL 形状以 MILESTONE-06 原型为准, 此处只定模块位置.
  - **Runner**: 集合 → 批量事件流 + JUnit 报告 (pytest 为 CI 宿主, subprocess + JUnit, 方向 C 结论).
  - **Sync**: git 绑定/提交/推拉封装, SPA 入口调用. 冲突策略见 D009.
- 理由: deep module 原则 (codebase-design skill); CLI 不 import 核心库 (D001) 后核心库唯一消费者 = FastAPI 服务, seam 少一层, 模块间全是进程内调用. 反方攻击确认模块划分与依赖方向本身无伪深模块 (Sync 的浅度问题由 D009 修复).
- 预计影响: 核心库包结构, 后续全部编码 Milestone.
- 相关 issue: 待关联

### D009 — Sync 冲突策略: 冲突即停

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: Sync 只做 `add/commit/push/pull --rebase`; 遇冲突/dirty 异常即停, 把 git 原样输出抛给用户手工处理, 绝不自动合并.
- 理由: 反方攻击 D5-A: 无冲突策略的 Sync 是伪装成 deep 的 shallow module; 自用场景自动合并策略收益不抵风险.
- 预计影响: Sync 模块, SPA git 入口错误展示.
- 相关 issue: 待关联

### D010 — API 形态: REST CRUD + RPC 动作混合

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: 资源 CRUD 走 REST 惯例 (`/collections/...`, `/environments/...`, `/history/...`), 动作走 RPC 端点 (`POST /execute` 带协商式流式回传, `POST /collections/{x}/run`, `POST /git/sync`). SPA 与 CLI 共用同一 API. 文件树↔资源映射: 集合=目录, 请求条目=slug 文件 (M2-D001/D003); 跨集合移动条目 = 改变变量作用域, 允许且语义即跟随 (移动后按新集合的 vars/defaults 解析).
- 理由: 自用 API 无需教义纯洁; CRUD 占调用大头有成熟惯例, 动作类本不是资源; 反方攻击确认混合形态无矛盾.
- 预计影响: 服务路由层, CLI 命令面, SPA store 层.
- 相关 issue: 待关联

### D011 — 服务发现与生命周期

- 状态: 当前有效
- 约束性: 必须遵守
- 内容:
  1. 单一权威源: 服务启动时在数据仓库 `.local/service.json` 原子写 (tmp+rename) `{port, token, pid}`; 不设独立 `.local/token` 文件 (双权威源一致性无定义);
  2. 端口: `bind(0)` 内核分配随机空闲端口 (消除探测-绑定 TOCTOU), 不用固定端口;
  3. 拉起串行化: flock + 锁内二次检查 (AI 代理并发调 CLI 是常态, F004);
  4. 连接: CLI 读 service.json 后 kill(pid, 0) 存活校验 (stale 文件防护), 连接失败则拉起, 请求级重试一次;
  5. 拉起细节: 显式 detach, 日志落 `.local/service.log`, 有限重试 (3 次), ready 判定 = TCP 连通 + token 校验通过, 失败明确报错给出原因;
  6. 数据仓库定位: 默认 `~/.local/share/<app>/`, `--data-dir` 覆盖; v1 不做多仓库并存管理;
  7. 生命周期: 常驻, CLI `stop` 子命令 (接受 `--data-dir` 定位停哪个) + SPA 关闭入口; 不做闲置自动回收 (自用场景伪需求; 多 data-dir 常驻泄漏风险由 stop 定位参数对冲).
- 理由: 用户拍板 CLI 幂等拉起常驻; 反方攻击 D1-A/D1-B/D7-A/D7-B/D7-C 的裁决合并.
- 依赖事实: F004
- 预计影响: launch 模块, 服务启动流程, CLI 命令面.
- 相关 issue: 待关联

### D012 — 平台范围: v1 仅 POSIX

- 状态: 当前有效
- 约束性: 必须遵守
- 内容: v1 仅支持 Linux/macOS; flock/fork/pid 语义按 POSIX 实现; Windows 不支持不报错承诺.
- 理由: 用户确认; 若日后需要 Windows, 拉起/锁改跨平台库, 成本可控但须立项重定.
- 预计影响: launch 模块, 服务进程管理.
- 相关 issue: 待关联

### D013 — 杂项收敛 (自扫补充)

- 状态: 当前有效
- 约束性: 可调整
- 内容: API 不版本化 (自用, 壳与服务同版本发布); Runner v1 顺序执行 (不并发); 引擎超时/响应大小上限为 v1 内置常量, 不进配置面.
- 理由: 自用规模下三者皆是过早设计; 收紧成本低, 放松成本也低, 先取简.
- 预计影响: Runner, Engine, 服务路由.
- 相关 issue: 待关联

### D014 — 测试策略

- 状态: 当前有效
- 约束性: 必须遵守
- 内容:
  1. Store/Resolve/Assert 纯单测, 无 I/O 或 tmp 目录 I/O, 不起服务;
  2. Engine/Runner 打 MILESTONE-12 测试后端 (真实 HTTP, replace-don't-layer, 不 mock httpx — 价值恰在真实传输行为: SSE/认证/multipart);
  3. FastAPI 壳用 TestClient 薄测 API 形状与 token 校验, 业务断言下沉到核心库测试;
  4. CLI 用 fake HTTP 服务测参数解析与输出渲染;
  5. launch/拉起逻辑专项测试矩阵: 双 CLI 并发拉起, 端口占用, stale service.json, 拉起失败路径 (反方攻击 D8-A: 拉起是 CLI 中唯一有真实复杂度的代码, 缺席即裸奔);
  6. 安全中间件函数级参数化单测: Host 白名单变体 (IPv6/重复头/伪造), query token vs header token, SSE 握手;
  7. MILESTONE-12 输入: 测试后端保持最小 (回显/延迟/断连), 复杂场景归集成冒烟, 防其无限膨胀.
- 预计影响: 全部编码 Milestone 的测试设计前置.
- 相关 issue: 待关联

## 事实

### F001 — 浏览器 CORS 限制

- 状态: 当前有效
- 来源: RESEARCH-local-security.md 第 4.3 节 (Postman Desktop Agent 官方文档)
- 内容: 浏览器页面无法直连任意 API, 请求执行必须在浏览器外; 这是 D001/D006 "执行收敛服务进程" 的地基.

### F002 — EventSource 无法自定义请求头

- 状态: 当前有效
- 来源: 浏览器 EventSource API 规范 (反方攻击 D3-A 引用, 高置信常识)
- 内容: SSE 握手的 token 只能经 query 参数携带; WebSocket API 同样不能自定义 header, 故 WS 相对 SSE 无认证优势.

### F003 — 本地安全攻击面调研

- 状态: 当前有效
- 来源: [RESEARCH-local-security.md](RESEARCH-local-security.md) (基于官方 advisory 一手来源)
- 内容: 绑 127.0.0.1 不等于安全 — 恶意网页可借浏览器向 localhost 发请求 (CSRF 盲写不受 CORS 挡, WS 不受 CORS 挡, DNS rebinding 绕 SOP 读响应; Vite GHSA-vg6x/esbuild GHSA-67mh/Sliver CVE-2026-34227 实证); 启动随机 token 是唯一同时覆盖读/写/WS 三面的机制 (Jupyter 默认开启先例); Vite build 静态产物 + FastAPI 托管不在 Vite/esbuild dev server CVE 攻击面内.

### F004 — AI 代理并发调用 CLI 是常态

- 状态: 当前有效
- 来源: 产品定义 (CLI 供 AI 使用) + 反方攻击 D1-A
- 内容: 每次 CLI 调用是独立 subprocess, 并发调用是常态; "服务在则不动作, 不在则拉起" 无串行化必然竞态 → D011 的 flock/原子写/bind(0) 由此而来.

### F005 — dist 产物漂移风险

- 状态: 当前有效
- 来源: 反方攻击 D2-B
- 内容: 改前端源码忘 build 时, 服务照常托管旧 dist, 自用场景高频发生且无感知 → D003 的启动时时间戳警告由此而来.

## 反方攻击裁决记录

完整报告在会话中, 要点归档: 7 条成立 (D1-A/B, D3-B, D5-A, D7-A, D8-A 等) 已全部并入 D002/D004/D005/D009/D011/D014; 12 条部分成立中成立部分已并入对应决策; 舍弃: D5-C 历史无限增长 (M2-D011 已定 v1 不自动清理, 反方无此上下文), E2/E3/E4/E5/E9 排除项翻案不成立, E7 固定端口翻案维持排除 (随机端口 + bind(0) 消除 TOCTOU).
