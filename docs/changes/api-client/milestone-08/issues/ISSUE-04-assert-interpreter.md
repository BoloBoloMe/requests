# ISSUE-04 — Assert 解释器接入

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: 断言求值接入执行流 — 照 `prototypes/assertion-dsl/dsl.py` 重写为 `src/api_client/assertions.py` (原型一次性代码, 重写不直接复用). 结构化断言 (M6 决策 1): `target + op + expect` 三元组或 `target + schema`; target 集 = status / elapsed_ms / header.<名> (大小写不敏感) / body / body.<jmespath>; op 集 = eq ne lt lte gt gte contains not_contains matches exists (exists 无 expect). Python 逃生舱: `{"python": "<代码>"}`, exec 注入 response 视图 (.status/.headers/.body/.text/.elapsed_ms), 全量 Python 无沙箱; AssertionError = 断言失败 (取其消息), 其他异常 = 错误 (类型+消息). 序列化 (M6 决策 2): 断言列表存条目 YAML `assert:` 键下, 多行 python 用 `|` 块标量, PyYAML 往返. 非 JSON 体降级 (M6 决策 3): 非 JSON 体的 `body.<路径>` 一律解析失败, 降级为裸 body + contains/not_contains/matches/eq; "体非 JSON" 与 "路径不存在" 报错文案区分. 结果进 done 事件 `assertions` 字段 (M4 D003), 断言失败反映在 done.status 但不中断执行 (供 ISSUE-05 runner). 适合 AFK: 求值语义已由原型验证 + 决策钉死, 只差重写与接线.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (断言解释器)
- 决策: `docs/changes/api-client/milestone-06/DECISIONS.md`, 决策 1/2/3; `docs/changes/api-client/milestone-01/DECISIONS.md`, D008; `docs/changes/api-client/milestone-03/DECISIONS.md`, D008/D014-1; `docs/changes/api-client/milestone-04/DECISIONS.md`, D003

## 相关决策
- `docs/changes/api-client/milestone-06/DECISIONS.md`: 决策 1 (双形态: 结构化为主 + Python 逃生舱), 决策 2 (YAML 序列化, python 块标量), 决策 3 (非 JSON 体降级, 报错文案区分)
- `docs/changes/api-client/milestone-01/DECISIONS.md`: D008 (砍 JS 脚本, 断言结构化, 无通用可编程钩子)
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D008 (Assert 模块位置: 响应+断言定义 → 结果列表), D014-1 (Assert 纯单测)
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D003 (done 事件含 assertions 字段)

## 允许范围
- 新建 `src/api_client/assertions.py` (纯函数求值器), `tests/api_client/test_assert.py`; 修改 `src/api_client/engine.py` 与 execute 路由 (done 事件带 assertions 结果); Store 条目 `assert:` 字段读写已在 ISSUE-02, 此处仅接求值.
- 参照 `docs/changes/api-client/prototypes/assertion-dsl/dsl.py` 的求值语义 (重写, 不复制文件).

## 禁止范围
- 不实现 JS/通用脚本断言 (M1 D008); 不为数组长度/浮点容差等缺口扩展 op (M6 决策 1 分工: 走逃生舱); 不做沙箱 (M6 决策 1: 自用无沙箱).
- 不改 `src/testbed/`; 不改任何 DECISIONS/ADR.

## 代码定位提示
- 参照: `docs/changes/api-client/prototypes/assertion-dsl/dsl.py` (Response/Result/resolve/compare/ResponseView/_eval_python/evaluate 结构与语义), `docs/changes/api-client/milestone-06/DECISIONS.md` 决策 3 (实现注意: 区分 "体非 JSON" 与 "路径不存在"), 决策 2 (块标量序列化).
- 阅读顺序: assertions.py → engine 接线 → test_assert.py.

## TDD 切片
- TS-001 (结构化求值全覆盖, D014-1):
  接缝: `evaluate(response, assertions) -> list[Result]` 纯函数.
  测试用例: TC-001 — op 十种全覆盖 (eq/ne/lt/lte/gt/gte/contains/not_contains/matches/exists), 数值比较拒布尔; TC-002 — target 集: status/elapsed_ms/header.<名> (大小写不敏感)/body/body.<jmespath>; TC-003 — schema 整体校验 (jsonschema.validate), 失败取校验消息; TC-004 — exists 无 expect; TC-005 — 报错文案区分: 非 JSON 体的 `body.<路径>` 报 "体非 JSON 不可取路径", JSON 体路径不存在报 "路径不存在".
  先写的失败测试: `test_non_json_body_path_error_message_distinct` — 预期失败: 原型中两案混为一句, 重写须区分.
  最小绿色实现范围: resolve/compare/evaluate 纯函数重写 (语义照原型, 文案按决策 3 区分).
  不得测试: 内部私有实现; 网络.
  覆盖: M6 决策 1/3, M1 D008.
- TS-002 (Python 逃生舱分类):
  接缝: 同上.
  测试用例: TC-006 — 注入视图字段可访问 (.status/.headers/.body/.text/.elapsed_ms); TC-007 — AssertionError = 失败且消息入 result.message (无消息时给默认文案); TC-008 — 其他异常 (如 KeyError/TypeError) = 错误, message 含类型+消息; TC-009 — 无沙箱 (exec 可执行任意 Python, 原型语义).
  先写的失败测试: `test_python_assert_error_classification` — 预期失败: 未区分 AssertionError 与普通异常.
  最小绿色实现范围: ResponseView + exec 求值 + 异常分类.
  不得测试: 沙箱行为 (不存在).
  覆盖: M6 决策 1.
- TS-003 (send 集成, M4 D003):
  接缝: execute 路由 + testbed 真响应.
  测试用例: TC-010 — 条目带断言打 testbed: POST /things 201 → `body.id gte 1` 通过; /status/404 → `status eq 404` 通过; 断言失败 → done.assertions 含失败条目且 done.status 为断言失败; TC-011 — `assert:` 键 YAML 往返 (python 块标量) 后求值一致.
  先写的失败测试: `test_done_event_carries_assertions` — 预期失败: done 事件无 assertions 字段.
  最小绿色实现范围: Engine 求值后组装 done.assertions (每条: assertion 定义/ok/actual/message), 失败不中断.
  不得测试: runner 批量 (ISSUE-05).
  覆盖: M4 D003, M6 决策 2.

## 验证入口
- `uv run pytest tests/api_client/test_assert.py` — 全绿.
- 真服务冒烟: 条目带断言打 testbed /things (201), 观察 done 事件 assertions 全通过; 改成 `status eq 500` 再发, done.assertions 含失败且 status 标记断言失败.

## 风险提示
- exec 无沙箱是决策明确接受 (M6 决策 1: 自用无他人仓库, RCE 权重不成立), 不得加沙箱或告警.
- 报错文案区分 (决策 3 实现注意) 是原型遗留缺口, TS-005 钉死.
- done.status 的断言失败语义要与 runner (ISSUE-05) 的统计对齐, 先定字段再批量.

## 停止条件
- 需要扩展 op/target 集、改变异常分类或给逃生舱加沙箱时停止 (均违反 M6 决策 1).

## 适合 AFK 的原因
- 求值语义已由 MILESTONE-06 原型 + 真实样例验证并决策, 重写路径明确.

## 验收标准
- [ ] 结构化断言 10 op + 5 类 target + schema 全覆盖, exists 无 expect.
- [ ] Python 逃生舱: AssertionError=失败取消息, 其他异常=错误 (类型+消息), 无沙箱.
- [ ] "体非 JSON" 与 "路径不存在" 报错文案区分.
- [ ] `assert:` YAML 往返 (python 块标量) 后求值一致; done 事件带 assertions 结果, 失败不中断.

## 被阻塞于
- ISSUE-03 (Resolve/Engine/send 执行流与 done 事件)
