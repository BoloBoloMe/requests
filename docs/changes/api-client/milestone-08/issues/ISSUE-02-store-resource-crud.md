# ISSUE-02 — Store + 资源 CRUD API

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: Store 模块成为数据仓库读写唯一入口 (M3 D008), 出进皆为领域对象, 隐藏 YAML schema/seq 排序/secrets 合并/`.local` 状态/历史路径形状. 数据仓库布局初始化 (M2 D004): `collections/<集合>/<文件夹>/<slug>.yaml`, `collections/<集合>/_collection.yaml`, `environments/<env>.yaml`, `environments/<env>.secrets.yaml`, `files/`, `.local/`; YAML 子集约定 (M2 D002): 显式 `version` 字段, 禁用锚点/别名, kv 值一律按字符串解析 (防 YAML 1.1 `on/off/yes/no` 布尔陷阱), 正式实现用 PyYAML. 条目字段形状 (M2 D008): url 单字符串 (含 `{{var}}` 插值), params/headers 有序 kv 列表可 `disabled`, body.type = none/json/text/form-urlencoded/multipart, method/name/seq/version/auth/assert (assert 形状按 MILESTONE-06 原型). 集合内排序: seq 整数, 平局按文件名 tiebreak (M2 D003). 环境与 secrets 同 schema (version+vars, 值一律字符串) (M2 D005/D006); 激活环境存 `.local/state.yaml` (M2 D007). 集合默认 `_collection.yaml`: vars + defaults (auth/headers) (M2 D010). 全部写走 tmp+rename 原子写 (M3 D008, 防 Runner 批量写与 Sync commit 交叠出半写文件). REST CRUD 端点 (M3 D010): `GET /collections`; `GET/PUT/DELETE /collections/{c}/items/{slug}` (PUT 即 upsert); `GET /collections/{c}/items?folder=` 按 seq 排序; `GET/PUT /collections/{c}/collection`; `GET/PUT /environments/{name}`; `PUT /environments/{name}/secrets`; `GET/PUT /state` (激活环境). 适合 AFK: 存储语义/格式全由账本钉死, 无待定问题.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (数据层 + REST 壳)
- 决策: `docs/changes/api-client/milestone-02/DECISIONS.md`, D001-D008/D010; `docs/changes/api-client/milestone-03/DECISIONS.md`, D008/D010/D014-1

## 相关决策
- `docs/changes/api-client/milestone-02/DECISIONS.md`: D001 (每请求一文件), D002 (YAML 子集), D003 (frontmatter seq), D004 (目录布局), D005 (环境进 git), D006 (secrets gitignored), D007 (激活环境 state), D008 (请求字段形状), D010 (集合级默认继承)
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D008 (Store 模块职责, tmp+rename 原子写), D010 (REST CRUD 形态), D014-1 (Store 纯单测)

## 允许范围
- 新建 `src/api_client/store.py` (领域对象/读写/原子写/排序), `src/api_client/web/` 路由 (CRUD 壳), `tests/api_client/test_store.py`, `tests/api_client/test_crud_api.py`.
- 修改 `pyproject.toml`: dependencies 增 `PyYAML`; 其余改动沿用 ISSUE-01.

## 禁止范围
- 不实现变量解析/执行/断言/runner/sync (ISSUE-03 起); 不实现历史写入 (Engine 副作用, ISSUE-03); 不做 git 操作 (ISSUE-06).
- 不改 `src/testbed/`; 不改任何 DECISIONS/ADR; 不引入 JSON 存储或其他文件格式.

## 代码定位提示
- 参照: `docs/changes/api-client/milestone-02/DECISIONS.md` (schema/布局/排序/继承), `docs/changes/api-client/prototypes/assertion-dsl/dsl.py` 尾部 `to_yaml` (仅作 assert 块标量序列化形态参考), `docs/changes/api-client/milestone-03/DECISIONS.md` D008 (Store 职责: 藏 YAML schema/seq/secrets 合并/.local 状态/历史落盘路径).
- 阅读顺序: store.py (领域对象 → 读写 → 排序/原子写) → CRUD 路由 → 两个测试文件.

## TDD 切片
- TS-001 (Store 集合/条目, D014-1):
  接缝: Store 公开 API, pytest tmp_path 数据目录 (无网络/无服务).
  测试用例: TC-001 — 条目 YAML 往返保字段形状 (url 单字符串含 `{{var}}`, params/headers 有序 kv 可 disabled, body.type 五态, version/auth/assert 字段); TC-002 — seq 排序平局文件名 tiebreak; TC-003 — 文件夹=子目录映射与读取; TC-004 — 原子写: 写入后文件完整 (读回等价), 无半写残留.
  先写的失败测试: `test_item_roundtrip_preserves_field_shape` — 预期失败: 序列化丢字段顺序/disabled/body.type.
  最小绿色实现范围: PyYAML safe_load/dump + 领域对象 dataclass + 条目读写/排序/文件夹遍历 + tmp+rename 原子写封装.
  不得测试: 变量解析 (ISSUE-03); 内部私有方法.
  覆盖: M2 D001/D002/D003/D004/D008, M3 D008.
- TS-002 (环境/secrets/激活状态, D014-1):
  接缝: 同上.
  测试用例: TC-005 — env 与 secrets 同 schema 读写, secrets 合并时优先级最高; TC-006 — `.local/state.yaml` 激活环境读写, 未设时为空; TC-007 — YAML 子集: 值 `on/off/yes/no` 一律按字符串读写 (不解析为布尔).
  先写的失败测试: `test_yaml_subset_values_stay_strings` — 预期失败: PyYAML 默认把 `on` 解析为布尔 true.
  最小绿色实现范围: env/secrets/state 读写 + 合并语义 + 字符串化读侧处理 (或 dump 前全部 str()).
  不得测试: 解析引擎优先级 (ISSUE-03); gitignore 写入 (ISSUE-06).
  覆盖: M2 D005/D006/D007/D002.
- TS-003 (CRUD API 壳薄测, D014-3):
  接缝: TestClient (显式 `Host: localhost` + 有效 token 头), 依赖注入 tmp 数据目录.
  测试用例: TC-008 — PUT 创建条目后 GET 取回同一领域对象; DELETE 后 GET 404; TC-009 — PUT env / PUT secrets / GET/PUT state 形状正确; TC-010 — 无 token 401 (沿用 ISSUE-01 中间件); TC-011 — 不存在集合/条目 404.
  先写的失败测试: `test_crud_upsert_then_get` — 预期失败: 壳未接 Store.
  最小绿色实现范围: 路由薄壳: 参数校验 + Store 调用 + 404/401 语义, 不做业务逻辑.
  不得测试: 业务断言下沉到 Store 测试已覆盖的行为 (D014-3).
  覆盖: M3 D010.
- TS-004 (集合默认读写):
  接缝: Store 公开 API.
  测试用例: TC-012 — `_collection.yaml` 的 vars/defaults (auth/headers) 读写往返.
  先写的失败测试: `test_collection_defaults_roundtrip` — 预期失败: 未实现 defaults 字段.
  最小绿色实现范围: 集合默认文件读写.
  不得测试: 继承解析 (ISSUE-03).
  覆盖: M2 D010.

## 验证入口
- `uv run pytest tests/api_client/test_store.py tests/api_client/test_crud_api.py` — 全绿.
- 起服务后 curl 冒烟: `uv run apic serve --data-dir /tmp/apic-crud &`; 带 token `curl -X PUT -H "X-Auth-Token: $TOKEN" -H "Content-Type: application/json" -d '{"name":"ping","method":"GET","url":"http://127.0.0.1:9000/echo"}' http://127.0.0.1:$PORT/collections/demo/items/ping` 后 GET 取回; 无 token 期望 401.

## 风险提示
- YAML 子集约定 (字符串化/禁锚点) 若漏一处, `on/off` 布尔陷阱即回潮, 用 TC-007 钉死.
- 原子写若漏 tmp+rename 直接覆写, Runner 批量写与 Sync commit 并发时会出半写文件 (M3 D008 点名), TC-004 覆盖.
- 领域对象与 dict 混用会让字段形状漂移, 坚持出进皆为领域对象.

## 停止条件
- 需要改变 M2 的目录布局/YAML schema/seq 语义或 REST 资源路径约定时停止.

## 适合 AFK 的原因
- 存储格式与布局已由 M2 账本与样例钉死, CRUD 路径属成熟惯例, 无待定决策.

## 验收标准
- [ ] 数据仓库布局初始化符合 M2 D004 树形.
- [ ] 条目/环境/secrets/state/集合默认读写往返保形状, seq 排序平局文件名 tiebreak.
- [ ] 全部写走 tmp+rename, 无半写文件残留.
- [ ] CRUD 壳: PUT upsert / GET / DELETE 404 / 无 token 401 语义正确.
- [ ] YAML 子集: 值一律字符串, 禁用锚点/别名.

## 被阻塞于
- ISSUE-01 (服务骨架/安全中间件/token 校验)
