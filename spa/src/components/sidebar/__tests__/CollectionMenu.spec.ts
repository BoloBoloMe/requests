// TS-014 (验收缺口): 集合菜单 — 集合名下拉切换 + 内联新建集合 + 空集合引导
// 接缝: CollectionMenu/Sidebar 组件 + store.createCollection/selectCollection
// 审核修复: 非法名用例走 mock 真校验 (对齐后端 _validate_name); 提交防重复 + Esc/取消.
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling, type MockSeed } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import type { CollectionConfigData } from "../../../services/types";
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

  it("TC-106: 非法名 (mock 真校验, 对齐后端 422) 在下拉内展示错误, 不静默", async () => {
    const { wrapper } = await mountMenu(presetBilling());
    await wrapper.find(".name").trigger("click");
    await wrapper.find("[data-new-collection]").trigger("click");
    const input = wrapper.find(".collform input");
    // 真非法字符: 后端 _validate_name 拒绝路径分隔符; 不再用空格名 (真后端接受空格)
    await input.setValue("foo/bar");
    await input.trigger("keydown", { key: "Enter" });
    await vi.waitFor(() => expect(wrapper.find(".collerror").exists()).toBe(true));
    expect(wrapper.find(".collerror").text()).toContain("422");
    // 失败不收起表单, 可修正重试
    expect(wrapper.find(".collform").exists()).toBe(true);
  });

  it("TC-107: 提交中禁用创建按钮, 重复提交 (Enter/点击) 被忽略", async () => {
    const { wrapper, services } = await mountMenu(presetBilling());
    // 挂起 put: 提交保持进行中; 放行时走原实现 (种子真正建集合, 后续 select 不炸)
    const orig = services.putCollectionConfig.bind(services);
    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const putSpy = vi
      .spyOn(services, "putCollectionConfig")
      .mockImplementation(async (collection: string, config: CollectionConfigData) => {
        await gate;
        return orig(collection, config);
      });
    await wrapper.find(".name").trigger("click");
    await wrapper.find("[data-new-collection]").trigger("click");
    const input = wrapper.find(".collform input");
    await input.setValue("orders");
    await input.trigger("keydown", { key: "Enter" });
    await vi.waitFor(() => expect(putSpy).toHaveBeenCalledTimes(1));
    // 提交中: 创建按钮禁用
    const submitBtn = wrapper.find("[data-create-submit]");
    expect(submitBtn.attributes("disabled")).toBeDefined();
    // 重复触发不产生第二次调用
    await input.trigger("keydown", { key: "Enter" });
    await submitBtn.trigger("click");
    expect(putSpy).toHaveBeenCalledTimes(1);
    // 放行后正常完成
    release!();
    await vi.waitFor(() => expect(wrapper.find(".collmenu").exists()).toBe(false));
    expect(putSpy).toHaveBeenCalledTimes(1);
  });

  it("TC-108: Esc 或取消按钮关闭新建表单 (不误提交)", async () => {
    const { wrapper, services } = await mountMenu(presetBilling());
    const putSpy = vi.spyOn(services, "putCollectionConfig");
    await wrapper.find(".name").trigger("click");
    await wrapper.find("[data-new-collection]").trigger("click");
    const input = wrapper.find(".collform input");
    await input.setValue("orders");
    // Esc 关闭
    await input.trigger("keydown", { key: "Escape" });
    expect(wrapper.find(".collform").exists()).toBe(false);
    expect(putSpy).not.toHaveBeenCalled();
    // 重新打开, 取消按钮关闭; 重开后输入框已清空
    await wrapper.find("[data-new-collection]").trigger("click");
    expect((wrapper.find(".collform input").element as HTMLInputElement).value).toBe("");
    await wrapper.find("[data-create-cancel]").trigger("click");
    expect(wrapper.find(".collform").exists()).toBe(false);
    expect(putSpy).not.toHaveBeenCalled();
  });
});

describe("G5: 点击外部收起", () => {
  // click-outside 监听器在宏任务注册, 触发外部点击前先让出宏任务
  function flushMacrotask() {
    return new Promise<void>((resolve) => setTimeout(resolve, 0));
  }

  it("TC-110: 点击下拉外部自动收起", async () => {
    const { wrapper } = await mountMenu();
    await wrapper.find(".name").trigger("click");
    expect(wrapper.find(".collmenu").exists()).toBe(true);
    await flushMacrotask();
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await vi.waitFor(() => expect(wrapper.find(".collmenu").exists()).toBe(false));
  });

  it("TC-111: 点击下拉内部不自动收起", async () => {
    const { wrapper } = await mountMenu();
    await wrapper.find(".name").trigger("click");
    expect(wrapper.find(".collmenu").exists()).toBe(true);
    await wrapper.find(".envmenu").trigger("click");
    expect(wrapper.find(".collmenu").exists()).toBe(true);
  });

  it("TC-112: 点击触发按钮本身按原语义切换, 不被误判为外部", async () => {
    const { wrapper } = await mountMenu();
    await wrapper.find(".name").trigger("click");
    expect(wrapper.find(".collmenu").exists()).toBe(true);
    // 再次点击触发按钮：原语义是收起
    await wrapper.find(".name").trigger("click");
    expect(wrapper.find(".collmenu").exists()).toBe(false);
  });
});

describe("空集合状态", () => {
  it("TC-109: 无集合时侧栏显示引导, 新建请求按钮禁用不抛错", async () => {
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
