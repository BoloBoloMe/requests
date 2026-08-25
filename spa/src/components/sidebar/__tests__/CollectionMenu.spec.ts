// TS-014 (验收缺口): 集合菜单 — 集合名下拉切换 + 内联新建集合 + 空集合引导
// 接缝: CollectionMenu/Sidebar 组件 + store.createCollection/selectCollection
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling, type MockSeed } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import CollectionMenu from "../CollectionMenu.vue";
import Sidebar from "../Sidebar.vue";

/** 双集合种子: billing (预置) + orders (空集合) */
function presetTwoCollections(): MockSeed {
  const seed = presetBilling();
  seed.collections.orders = { tree: { name: "orders", subfolders: [], items: {} } };
  return seed;
}

async function mountMenu(seed: MockSeed = presetTwoCollections()) {
  const services = createMockServices(seed);
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(CollectionMenu, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("集合菜单", () => {
  it("TC-103: 点集合名弹下拉, 列出全部集合并标记当前", async () => {
    const { wrapper } = await mountMenu();
    expect(wrapper.find(".collmenu").exists()).toBe(false);
    await wrapper.find(".name").trigger("click");
    const menu = wrapper.find(".collmenu");
    expect(menu.exists()).toBe(true);
    const names = menu
      .findAll("div[data-collection]")
      .map((d) => d.attributes("data-collection"));
    expect(names).toEqual(["billing", "orders"]);
    expect(wrapper.find('[data-collection="billing"]').text()).toContain("✓");
  });

  it("TC-104: 选中另一集合即全局切换 (集合树/集合变量随之刷新)", async () => {
    const { wrapper, store } = await mountMenu();
    expect(store.state.collection).toBe("billing");
    await wrapper.find(".name").trigger("click");
    await wrapper.find('[data-collection="orders"]').trigger("click");
    expect(store.state.collection).toBe("orders");
    expect(store.state.root?.name).toBe("orders");
    // 头部集合名同步, 下拉关闭
    expect(wrapper.find(".name").text()).toContain("orders");
    expect(wrapper.find(".collmenu").exists()).toBe(false);
  });

  it("TC-105: 内联输入名称新建集合, 调适配层隐式建集合并选中", async () => {
    const { wrapper, store, services } = await mountMenu(presetBilling());
    const putSpy = vi.spyOn(services, "putCollectionConfig");
    await wrapper.find(".name").trigger("click");
    await wrapper.find("[data-new-collection]").trigger("click");
    const input = wrapper.find(".collform input");
    await input.setValue("orders");
    await input.trigger("keydown", { key: "Enter" });
    // 等异步 action 链 (put → listCollections → selectCollection) 完成: 成功后表单收起, 下拉关闭
    await vi.waitFor(() => expect(wrapper.find(".collmenu").exists()).toBe(false));
    expect(store.state.collection).toBe("orders");
    expect(putSpy).toHaveBeenCalledWith("orders", {
      vars: {},
      defaults: { auth: null, headers: [] },
    });
    expect(store.state.collections).toContain("orders");
  });

  it("TC-106: 新建失败 (422) 在下拉内展示错误, 不静默", async () => {
    const { wrapper, services } = await mountMenu(presetBilling());
    vi.spyOn(services, "putCollectionConfig").mockRejectedValue(
      new Error("422: 集合名非法"),
    );
    await wrapper.find(".name").trigger("click");
    await wrapper.find("[data-new-collection]").trigger("click");
    const input = wrapper.find(".collform input");
    await input.setValue("bad name");
    await input.trigger("keydown", { key: "Enter" });
    await vi.waitFor(() => expect(wrapper.find(".collerror").exists()).toBe(true));
    expect(wrapper.find(".collerror").text()).toContain("422");
    // 失败不收起表单, 可修正重试
    expect(wrapper.find(".collform").exists()).toBe(true);
  });
});

describe("空集合状态", () => {
  it("TC-107: 无集合时侧栏显示引导, 新建请求按钮禁用不抛错", async () => {
    const services = createMockServices({ collections: {} });
    const store = createAppStore(services);
    await store.init();
    const wrapper = mount(Sidebar, {
      global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
    });
    expect(wrapper.find(".empty-hint").exists()).toBe(true);
    expect(wrapper.find(".empty-hint").text()).toContain("暂无集合");
    const addBtn = wrapper.find('button[title="新建请求"]');
    expect(addBtn.attributes("disabled")).toBeDefined();
    await addBtn.trigger("click");
    expect(store.state.root).toBeNull();
  });
});
