# ISSUE-05 — Runner 批量运行 (POST /collections/{x}/run)

## 父级
- `../EXECUTION.md`

## 执行(Execution)
- [ ] 已实现

## 要构建什么
端到端可观察: Runner 顺序执行集合内全部请求条目 (v1 不并发, M3 D013), 对每条目发完整 meta/chunk/done (M4 D003, 不吞 chunk — agent 须能从 run 输出直接定位失败条目响应体, 禁止要求重放 send), 断言失败不中断后续条目; 末尾发 summary (total/passed/failed/items). `POST /collections/{c}/run` 与 `/execute` 同协商 (SSE/NDJSON), 事件流末尾附 `report` 事件携带 JUnit XML 内容 (手写最小 XML, xml.etree, testsuite/testcase/name/classname/failure 标签, 兼容 pytest --junitxml 消费); JUnit 报告是输出物, 不属于数据仓库 (M2 D011). 适合 AFK: 语义已由账本钉死, 靶子现成.

## 覆盖依据
- 任务定义: `docs/changes/api-client/roadmap/MILESTONE-08.md`, 后端核心实现 (runner)
- 决策: `docs/changes/api-client/milestone-03/DECISIONS.md`, D008/D013; `docs/changes/api-client/milestone-04/DECISIONS.md`, D003; `docs/changes/api-client/milestone-02/DECISIONS.md`, D011

## 相关决策
- `docs/changes/api-client/milestone-03/DECISIONS.md`: D008 (Runner 职责: 集合 → 批量事件流 + JUnit 报告), D013 (v1 顺序执行不并发), D014-2 (Runner 打 testbed 真实 HTTP)
- `docs/changes/api-client/milestone-04/DECISIONS.md`: D003 (run 对每条目发完整 meta/chunk/done + summary, 不吞 chunk)
- `docs/changes/api-client/milestone-02/DECISIONS.md`: D011 (JUnit 报告是输出物, 不入数据仓库)

## 允许范围
- 新建 `src/api_client/runner.py`, `src/api_client/web/run.py` (路由+协商), `tests/api_client/test_runner.py`; 修改 engine/execute 复用 (send 单条已就绪).
- 测试 fixture: 子进程拉起 `uv run testbed --port 0` 真 HTTP (D014-2); runner 用 testbed 三个端点构造 3 条目集合 (echo 通过 / status/404 断言失败 / auth/bearer 通过).

## 禁止范围
- 不并发执行 (D013); 不把 JUnit 报告写进数据仓库 (M2 D011); 不做重放/重试逻辑 (未决策).
- 不 mock httpx (D014-2); 不改 `src/testbed/`; 不实现 CLI (MILESTONE-10).

## 代码定位提示
- 参照: `src/testbed/README.md` (端点: /echo, /status/{code}, /auth/bearer, /sse), `docs/changes/api-client/milestone-04/DECISIONS.md` D003 (summary 字段与不吞 chunk 教训), `tests/testbed/` 的 pytest 集成方式.
- 阅读顺序: runner.py (顺序遍历条目 → 复用 Engine 事件 → summary) → run 路由 → test_runner.py.

## TDD 切片
- TS-001 (Runner 顺序批量, D014-2):
  接缝: `runner.run_collection(store, resolve, engine, c) -> AsyncIterator[Event]`, 打 testbed 真 HTTP.
  测试用例: TC-001 — 3 条目集合: 事件序 = meta/chunk/done x3 + summary, 顺序执行 (条目 2 依赖条目 1 的时序可观察); TC-002 — 中间条目断言失败不中断, 后续条目照常执行; TC-003 — summary 的 total/passed/failed 与断言结果一致; TC-004 — chunk 不吞: 每条目的响应体在 run 事件流中可完整定位 (失败条目的 chunk 数据含响应体).
  先写的失败测试: `test_runner_emits_full_events_per_item_no_chunk_swallow` — 预期失败: 若 runner 只发 meta/done 吞 chunk 则失败条目响应体不可定位 (M4 D003 首轮 dogfood 教训).
  最小绿色实现范围: 顺序遍历条目 → 逐条复用 Engine 完整事件流 → 聚合 summary.
  不得测试: 单条执行细节 (Engine 已测); 并发行为 (不存在).
  覆盖: M3 D008/D013, M4 D003.
- TS-002 (JUnit 报告):
  接缝: `runner.junit_xml(results) -> str` 纯函数.
  测试用例: TC-005 — 输出可被 xml.etree 解析; TC-006 — 结构: testsuite 属性 (tests/failures/errors/time) + testcase (name/classname/time) + 失败条目含 failure 元素 (消息=断言消息), 通过条目无 failure; TC-007 — 标签与 pytest --junitxml 消费兼容 (以 xml.etree 按 pytest junit 结构断言, 不依赖外部解析器).
  先写的失败测试: `test_junit_report_parseable_and_structured` — 预期失败: 未实现或结构非 JUnit 约定.
  最小绿色实现范围: xml.etree 生成 testsuite/testcase/failure, 失败消息透传.
  不得测试: 写盘路径 (报告不入仓库, 由消费方落盘).
  覆盖: M2 D011 (输出物形态), M3 D008.
- TS-003 (run API 壳薄测, D014-3):
  接缝: TestClient.
  测试用例: TC-008 — POST /collections/{c}/run 协商 SSE/NDJSON 同 /execute; 事件流末尾含 report 事件 (format=junit, content=XML); TC-009 — 不存在集合 404; 无 token 401.
  先写的失败测试: `test_run_ends_with_report_event` — 预期失败: 无 report 事件.
  最小绿色实现范围: run 路由薄壳 + 协商 + report 事件组装.
  不得测试: 业务统计 (Runner 已测).
  覆盖: M3 D010, M2 D011.

## 验证入口
- `uv run pytest tests/api_client/test_runner.py` — 全绿.
- 真服务冒烟: `uv run apic serve --data-dir /tmp/apic-run &` (testbed `uv run testbed --port 9000 &`); `curl -N -H "Accept: application/x-ndjson" -H "X-Auth-Token: $TOKEN" -X POST http://127.0.0.1:$PORT/collections/demo/run` 观察逐行 meta/chunk/done/summary/report; report 事件 XML 落临时文件后 `uv run python -c "import xml.etree.ElementTree as E; E.parse('report.xml'); print('ok')"`.

## 风险提示
- 吞 chunk 是 M4 首轮 dogfood 最大不一致 (D003 点名), TC-004 必须钉死.
- 顺序执行下单条目悬挂会拖死整批: 超时/大小上限常量由 Engine (ISSUE-03) 保证, runner 不得绕过.
- JUnit 结构若与 pytest 消费方预期不符, 后续 CI 集成返工; 以 TS-002 结构断言为准.

## 停止条件
- 需要引入并发、改变 summary 字段或把报告写入数据仓库时停止 (均违反 D013/D003/M2 D011).

## 适合 AFK 的原因
- 批量语义/事件契约/JUnit 形态已由账本钉死, 靶子现成, 无待定决策.

## 验收标准
- [ ] 集合内条目顺序执行, 断言失败不中断, 事件流含完整 meta/chunk/done x N + summary.
- [ ] run 输出可直接定位失败条目响应体 (不吞 chunk).
- [ ] JUnit 报告可解析且结构与 pytest --junitxml 兼容, 报告不入数据仓库.
- [ ] run API 协商/404/401 语义正确.

## 被阻塞于
- ISSUE-04 (断言结果进 done 事件, runner 统计依赖)
