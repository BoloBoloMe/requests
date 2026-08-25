// ISSUE-03 组装测试: RequestBuilder 草稿装载/五 tab/写回
// 接缝: RequestBuilder 组件 + store 选中联动 (验收: 编辑结果经适配层可写回)
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import RequestBuilder from "../RequestBuilder.vue";

async function mountBuilder() {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  store.selectItem({ slug: "create", folder: "订单", item: (await services.getItem("billing", "create", "订单")) });
  await store.loadDraft();
  const wrapper = mount(RequestBuilder, {
    attachTo: document.body,
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("RequestBuilder 组装", () => {
  it("选中条目后渲染 URL 栏与五 tab (断言带计数胶囊)", async () => {
    const { wrapper } = await mountBuilder();
    expect(wrapper.find(".urlbar").exists()).toBe(true);
    const tabs = wrapper.findAll(".tabs span");
    expect(tabs.map((t) => t.text())).toEqual([
      "Params",
      "Headers1",
      "Body",
      "Auth",
      expect.stringContaining("断言"),
    ]);
  });

  it("编辑 URL 后保存经适配层写回", async () => {
    const { wrapper, store, services } = await mountBuilder();
    const putSpy = vi.spyOn(services, "putItem");
    // 进入编辑态改 URL
    await wrapper.find(".urlin").trigger("click");
    const input = wrapper.find("input.urlin");
    await input.setValue("https://{{host}}/v2/orders");
    await input.trigger("keydown", { key: "Enter" });
    expect(store.state.draft?.url).toBe("https://{{host}}/v2/orders");
    await wrapper.find('button[data-action="save"]').trigger("click");
    expect(putSpy).toHaveBeenCalled();
    const saved = await services.getItem("billing", "create", "订单");
    expect(saved.url).toBe("https://{{host}}/v2/orders");
  });

  it("切 tab 到 Body 挂载 CodeMirror (json), Auth 渲染三选", async () => {
    const { wrapper, store } = await mountBuilder();
    store.state.builderTab = "Body";
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".cm-editor").exists()).toBe(true);
    store.state.builderTab = "Auth";
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".authbox").exists()).toBe(true);
    store.state.builderTab = "断言";
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".alist").exists()).toBe(true);
    wrapper.unmount();
  });

  it("发送按钮触发执行 (SSE 消费经 store.send, ISSUE-04 接线)", async () => {
    const { wrapper, store, services } = await mountBuilder();
    const execSpy = vi.spyOn(services, "execute");
    await wrapper.find("button.send").trigger("click");
    expect(execSpy).toHaveBeenCalledWith({ collection: "billing", item: "create", folder: "订单" });
    // mock 事件流为空, 发送立即完成, 发送中态复位
    expect(store.state.sending).toBe(false);
  });
});
