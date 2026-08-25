// TS-001/TS-002 (ISSUE-05): runner 内联 (M5 决策 3)
// 接缝: FolderTree 徽标/红字 + store.run() 消费 mock run 事件流 (D010 RPC, D007 事件模型)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import Sidebar from "../Sidebar.vue";
import type { RunEvent } from "../../../services/types";

const RUN_EVENTS: RunEvent[] = [
  { type: "meta", timestamp: "t0", item: "billing/list", method: "GET", resolved_url: "https://x/orders", env: "prod" },
  {
    type: "done",
    timestamp: "t1",
    item: "billing/list",
    status: 200,
    duration_ms: 30,
    assertions: [{ assertion: { target: "status", op: "eq", expect: 200 }, ok: true, actual: 200, message: "" }],
  },
  { type: "meta", timestamp: "t2", item: "billing/create", method: "POST", resolved_url: "https://x/orders", env: "prod" },
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

async function mountSidebarWithRun() {
  const seed = presetBilling();
  seed.runEvents = RUN_EVENTS;
  const services = createMockServices(seed);
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(Sidebar, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

/** 找订单文件夹的条目行 (按 slug 顺序 list/create/cancel) */
function reqRows(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll(".req");
}

describe("runner 内联徽标", () => {
  it("TC-001: 文件夹运行后条目三态徽标 (✓/✗/·) 与文件夹计数徽章", async () => {
    const { wrapper, store } = await mountSidebarWithRun();
    // 初始全部未运行
    expect(wrapper.findAll(".st.none").length).toBeGreaterThan(0);
    // 点订单文件夹 ▶ 运行
    const folderHd = wrapper.findAll(".f-hd").find((h) => h.text().includes("订单"))!;
    await folderHd.find(".run").trigger("click");
    await store.state.runDone; // 等运行收尾
    const rows = reqRows(wrapper);
    const byName = (name: string) => rows.find((r) => r.text().includes(name))!;
    // list ✓ / create ✗ / cancel 未运行 · (行按名称定位, 文件夹按码位排序)
    expect(byName("订单列表").find(".st").classes()).toContain("ok");
    expect(byName("订单列表").find(".st").text()).toBe("✓");
    expect(byName("创建订单").find(".st").classes()).toContain("bad");
    expect(byName("创建订单").find(".st").text()).toBe("✗");
    expect(byName("取消订单").find(".st").classes()).toContain("none");
    // 文件夹头计数徽章: 有失败显失败数
    expect(folderHd.find(".count").text()).toContain("1✗");
  });

  it("运行中条目显 ◌ spinner, 重复运行被忽略", async () => {
    const { wrapper, store, services } = await mountSidebarWithRun();
    let release!: () => void;
    services.runCollection = () =>
      (async function* () {
        yield { type: "meta", timestamp: "t", item: "billing/list", method: "GET", resolved_url: "https://x/", env: "prod" } as const;
        await new Promise<void>((r) => (release = r));
      })();
    const folderHd = wrapper.findAll(".f-hd").find((h) => h.text().includes("订单"))!;
    await folderHd.find(".run").trigger("click");
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".st.run").exists()).toBe(true);
    expect(wrapper.find(".st.run").text()).toBe("◌");
    // 并发保护: 重复点击不产生第二次运行
    let calls = 0;
    const orig = services.runCollection;
    services.runCollection = (...a) => {
      calls += 1;
      return orig(...a);
    };
    await folderHd.find(".run").trigger("click");
    expect(calls).toBe(0);
    release();
    await store.state.runDone;
  });

  it("TC-002: 失败红字明细含 target/why/实际值, 点击跳断言 tab 并定位失败行", async () => {
    const { wrapper, store } = await mountSidebarWithRun();
    const folderHd = wrapper.findAll(".f-hd").find((h) => h.text().includes("订单"))!;
    await folderHd.find(".run").trigger("click");
    await store.state.runDone;
    const note = wrapper.find(".failnote");
    expect(note.exists()).toBe(true);
    expect(note.text()).toContain("✗ status");
    expect(note.text()).toContain("期望 eq 201");
    expect(note.text()).toContain("实际 200");
    await note.trigger("click");
    expect(store.state.selected?.slug).toBe("create");
    expect(store.state.builderTab).toBe("断言");
    expect(store.state.assertionHighlight).toBe(0);
  });
});
