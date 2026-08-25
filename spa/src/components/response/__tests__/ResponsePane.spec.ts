// ISSUE-04 组装测试: ResponsePane 消费 mock 事件流渲染 头行/三 tab
// 接缝: store.send() (services.execute 异步迭代) + ResponsePane 组件
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import ResponsePane from "../ResponsePane.vue";
import type { HistoryEntry } from "../../../services/types";

const HISTORY: HistoryEntry = {
  file: "h1.json",
  timestamp: "2026-08-25T11:00:00",
  item: "billing/create",
  duration_ms: 88,
  request: {
    method: "POST",
    url: "https://{{host}}/v1/orders",
    params: [],
    headers: [{ key: "Authorization", value: "Bearer {{api_token}}" }],
    body: { type: "json", text: '{"item":"年度订阅"}' },
  },
  response: {
    status: 200,
    headers: [{ key: "content-type", value: "application/json" }],
    body: { kind: "text", content_type: "application/json", text: '{"id":1024}' },
  },
};

async function mountPane() {
  const seed = presetBilling();
  seed.executeEvents = [
    { type: "meta", timestamp: "t0", item: "billing/create", method: "POST", resolved_url: "https://api.example.com/v1/orders", env: "prod" },
    { type: "chunk", timestamp: "t1", item: "billing/create", index: 0, data: '{"id":1024,"status":"open"}' },
    {
      type: "done",
      timestamp: "t2",
      item: "billing/create",
      status: 200,
      duration_ms: 88,
      assertions: [{ assertion: { target: "status", op: "eq", expect: 200 }, ok: true, actual: 200, message: "" }],
    },
  ];
  seed.history = [HISTORY];
  const services = createMockServices(seed);
  const store = createAppStore(services);
  await store.init();
  store.selectItem({ slug: "create", folder: "订单", item: await services.getItem("billing", "create", "订单") });
  await store.loadDraft();
  const wrapper = mount(ResponsePane, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("ResponsePane 组装", () => {
  it("send() 消费事件流: 头行状态徽章 + 断言胶囊, Body 渲染 JSON 树", async () => {
    const { wrapper, store } = await mountPane();
    await store.send();
    expect(store.state.sending).toBe(false);
    expect(wrapper.find(".r-hd .status").classes()).toContain("ok");
    expect(wrapper.find(".r-hd .status").text()).toContain("200");
    expect(wrapper.find(".asserts").text()).toContain("断言 1/1");
    // Body tab 默认: JSON 树
    expect(wrapper.find(".json").exists()).toBe(true);
    expect(wrapper.text()).toContain("1024");
  });

  it("发送中头行显示发送中态", async () => {
    const { wrapper, store, services } = await mountPane();
    // 可控事件流: 不完结, 发送中态应保持
    services.execute = () =>
      (async function* () {
        yield { type: "meta", timestamp: "t", item: "x", method: "POST", resolved_url: "https://x/", env: "prod" } as const;
        await new Promise(() => {});
      })();
    const pending = store.send();
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".r-hd").text()).toContain("发送中");
    void pending;
  });

  it("Headers tab 展示历史响应头, 日志 tab 展示完整收发转录 (不脱敏)", async () => {
    const { wrapper, store } = await mountPane();
    await store.send();
    store.state.responseTab = "Headers";
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("content-type");
    store.state.responseTab = "日志";
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".log-out").exists()).toBe(true);
    expect(wrapper.find(".log-in").exists()).toBe(true);
    expect(wrapper.text()).toContain("→ POST https://api.example.com/v1/orders");
    // 不脱敏: 集合变量/环境变量外的未知变量原样保留, 已知变量解析 (M5-D5)
    expect(wrapper.text()).toContain("Authorization: Bearer {{api_token}}");
  });

  it("发送前自动保存草稿: 发送的是编辑后的 URL, 不是旧存储版本", async () => {
    const { store, services } = await mountPane();
    const putSpy = vi.spyOn(services, "putItem");
    store.state.draft!.url = "http://127.0.0.1:9000/echo?a=1";
    await store.send();
    // saveDraft 先亂 execute: putItem 携草稿 URL 被调用
    expect(putSpy).toHaveBeenCalled();
    expect(putSpy.mock.calls.at(-1)?.[2].url).toBe("http://127.0.0.1:9000/echo?a=1");
  });

  it("发送失败合成 done.error: 头行展示原因, promise 不拒绝", async () => {
    const { wrapper, store, services } = await mountPane();
    services.execute = () =>
      (async function* (): AsyncGenerator<never> {
        throw new Error("执行失败 422: UNRESOLVED_VARIABLES");
      })();
    // 不抛未处理拒绝
    await store.send();
    expect(store.state.sending).toBe(false);
    expect(store.state.response?.done?.status).toBeNull();
    expect(store.state.response?.done?.error?.message).toContain("UNRESOLVED_VARIABLES");
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".r-hd").text()).toContain("REQUEST_FAILED");
  });

  it("非 JSON 响应体降级裸文本", async () => {
    const { wrapper, store, services } = await mountPane();
    (services as ReturnType<typeof createMockServices>).execute = () =>
      (async function* () {
        yield { type: "chunk", timestamp: "t", item: "x", index: 0, data: "plain text body" } as const;
        yield { type: "done", timestamp: "t", item: "x", status: 200, duration_ms: 5, assertions: [] } as const;
      })();
    await store.send();
    expect(wrapper.find(".json").exists()).toBe(false);
    expect(wrapper.text()).toContain("plain text body");
  });
});
