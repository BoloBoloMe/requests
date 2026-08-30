// G3: 集合运行结果回看 — run 后点条目, 响应面板显示该次运行的 meta/body/断言
// 接缝: store.run() 缓存 runViews + selectItem 注入 + send/loadDraft 不污染
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import Sidebar from "../Sidebar.vue";
import ResponsePane from "../../response/ResponsePane.vue";
import type { RunEvent } from "../../../services/types";

const RUN_EVENTS: RunEvent[] = [
  { type: "meta", timestamp: "t0", item: "billing/list", method: "GET", resolved_url: "https://x/orders", env: "prod" },
  { type: "chunk", timestamp: "t0.5", item: "billing/list", index: 0, data: '{"orders":[]}' },
  {
    type: "done",
    timestamp: "t1",
    item: "billing/list",
    status: 200,
    duration_ms: 30,
    assertions: [{ assertion: { target: "status", op: "eq", expect: 200 }, ok: true, actual: 200, message: "" }],
  },
  { type: "meta", timestamp: "t2", item: "billing/create", method: "POST", resolved_url: "https://x/orders", env: "prod" },
  { type: "chunk", timestamp: "t2.5", item: "billing/create", index: 0, data: '{"id":1}' },
  {
    type: "done",
    timestamp: "t3",
    item: "billing/create",
    status: "assert_failed",
    duration_ms: 45,
    assertions: [
      { assertion: { target: "status", op: "eq", expect: 201 }, ok: false, actual: 200, message: "期望 eq 201" },
    ],
  },
  {
    type: "summary",
    timestamp: "t4",
    total: 2,
    passed: 1,
    failed: 1,
    items: [
      { item: "billing/list", status: 200, passed: true },
      { item: "billing/create", status: "assert_failed", passed: false },
    ],
  },
  { type: "report", format: "junit", content: "<testsuite/>" },
];

async function mountApp() {
  const seed = presetBilling();
  seed.runEvents = RUN_EVENTS;
  const services = createMockServices(seed);
  const store = createAppStore(services);
  await store.init();
  const sidebar = mount(Sidebar, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  const pane = mount(ResponsePane, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { sidebar, pane, store, services };
}

/** 找订单文件夹头并点 ▶ 运行 */
async function runFolder(sidebar: ReturnType<typeof mount>): Promise<void> {
  const folderHd = sidebar.findAll(".f-hd").find((h) => h.text().includes("订单"))!;
  await folderHd.find(".run").trigger("click");
}

function rowOf(sidebar: ReturnType<typeof mount>, name: string) {
  return sidebar.findAll(".req").find((r) => r.text().includes(name))!;
}

describe("G3 运行结果回看", () => {
  it("TC-001: run 后点条目, 响应面板显示该次运行 body 与断言明细", async () => {
    const { sidebar, pane, store } = await mountApp();
    await runFolder(sidebar);
    await store.state.runDone;
    // 点通过的条目 (订单列表 = list)
    await rowOf(sidebar, "订单列表").trigger("click");
    expect(store.state.response?.done?.status).toBe(200);
    expect(pane.find(".status").text()).toContain("200");
    expect(pane.find(".rawtext").text().replace(/\s+/g, "")).toContain('{"orders":[]}');
    // 断言计数胶囊
    expect(pane.find(".asserts").text()).toContain("断言 1/1");
    // 回看提示条
    expect(pane.find(".runview-note").exists()).toBe(true);
    // 点失败条目 (创建订单 = create): 断言失败 + 失败明细
    await rowOf(sidebar, "创建订单").trigger("click");
    expect(store.state.response?.done?.status).toBe("assert_failed");
    expect(pane.find(".status").text()).toContain("断言失败");
    expect(pane.find(".failnote").text()).toContain("期望 eq 201");
    expect(store.state.runViewing).toBe(true);
  });

  it("TC-002: 切到无运行缓存条目, 回看态清空不残留", async () => {
    const { sidebar, store } = await mountApp();
    await runFolder(sidebar);
    await store.state.runDone;
    await rowOf(sidebar, "订单列表").trigger("click");
    expect(store.state.runViewing).toBe(true);
    // 取消订单 (cancel) 未在 run 事件流中 -> 面板清空
    await rowOf(sidebar, "取消订单").trigger("click");
    expect(store.state.runViewing).toBe(false);
    expect(store.state.response).toBeNull();
  });

  it("TC-003: send 后面板为发送结果, run 回看缓存仍在可再点回", async () => {
    const { sidebar, pane, store, services } = await mountApp();
    await runFolder(sidebar);
    await store.state.runDone;
    // 选中 list 并模拟 send (execute 事件流)
    await rowOf(sidebar, "订单列表").trigger("click");
    services.execute = () =>
      (async function* () {
        yield { type: "meta", timestamp: "s0", item: "billing/list", method: "GET", resolved_url: "https://x/", env: "prod" };
        yield { type: "chunk", timestamp: "s1", item: "billing/list", index: 0, data: '{"sent":true}' };
        yield {
          type: "done", timestamp: "s2", item: "billing/list", status: 200, duration_ms: 5,
          assertions: [{ assertion: { target: "status", op: "eq", expect: 200 }, ok: true, actual: 200, message: "" }],
        };
      })();
    await store.send();
    expect(store.state.runViewing).toBe(false);
    expect(pane.find(".runview-note").exists()).toBe(false);
    expect(pane.find(".rawtext").text().replace(/\s+/g, "")).toContain('{"sent":true}');
    // 再点同一条目: 回看缓存仍在, 重新注入 (注意 selectItem 对回看态守卫: 同 slug 已在回看态则不重复注入,
    // 此处 send 后 runViewing=false, 重新点即注入 run 缓存)
    await rowOf(sidebar, "订单列表").trigger("click");
    expect(store.state.runViewing).toBe(true);
    expect(store.state.response?.bodyText).toContain('{"orders":[]}');
  });

  it("TC-004: 重新 run 清空旧缓存, 回看不残留上次数据", async () => {
    const { sidebar, store, services } = await mountApp();
    await runFolder(sidebar);
    await store.state.runDone;
    await rowOf(sidebar, "订单列表").trigger("click");
    expect(store.state.response?.bodyText).toContain('{"orders":[]}');
    // 换一组事件流再 run
    services.runCollection = () =>
      (async function* () {
        yield { type: "meta", timestamp: "r0", item: "billing/list", method: "GET", resolved_url: "https://x/", env: "prod" };
        yield { type: "chunk", timestamp: "r1", item: "billing/list", index: 0, data: '{"fresh":1}' };
        yield { type: "done", timestamp: "r2", item: "billing/list", status: 200, duration_ms: 1, assertions: [] };
      })();
    await store.run();
    await store.state.runDone;
    await rowOf(sidebar, "订单列表").trigger("click");
    expect(store.state.response?.bodyText).toContain('{"fresh":1}');
    expect(store.state.response?.bodyText).not.toContain('{"orders":[]}');
  });

  it("TC-005: 集合切换清空回看缓存与回看态", async () => {
    const { sidebar, store } = await mountApp();
    await runFolder(sidebar);
    await store.state.runDone;
    await rowOf(sidebar, "订单列表").trigger("click");
    expect(store.state.runViewing).toBe(true);
    await store.selectCollection("billing"); // 同名重建即清空
    expect(store.state.runViews).toEqual({});
    expect(store.state.runViewing).toBe(false);
  });
});
