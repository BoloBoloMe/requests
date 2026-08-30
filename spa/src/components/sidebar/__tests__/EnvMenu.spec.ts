// TS-002 (ISSUE-02): 环境胶囊下拉切换
// 接缝: EnvMenu 组件 + 全局环境状态 (store)
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import EnvMenu from "../EnvMenu.vue";

async function mountEnvMenu() {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(EnvMenu, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("环境胶囊", () => {
  it("TC-003: 点环境胶囊弹下拉, 列出全部环境", async () => {
    const { wrapper } = await mountEnvMenu();
    expect(wrapper.find(".envmenu").exists()).toBe(false);
    await wrapper.find(".env").trigger("click");
    const menu = wrapper.find(".envmenu");
    expect(menu.exists()).toBe(true);
    const names = menu.findAll("div[data-env]").map((d) => d.attributes("data-env"));
    expect(names).toEqual(["prod", "staging"]);
  });

  it("TC-004: 选另一环境后全局环境状态切换 (写入适配层激活状态)", async () => {
    const { wrapper, store, services } = await mountEnvMenu();
    expect(store.state.activeEnv).toBe("prod");
    await wrapper.find(".env").trigger("click");
    await wrapper.find('[data-env="staging"]').trigger("click");
    expect(store.state.activeEnv).toBe("staging");
    expect(await services.getActiveEnvironment()).toBe("staging");
    // 胶囊显示同步, 下拉关闭
    expect(wrapper.find(".env").text()).toContain("staging");
    expect(wrapper.find(".envmenu").exists()).toBe(false);
    // 变量视图随环境刷新 (供 URL 解析预览, ISSUE-03)
    expect(store.state.envVars.host).toBe("api.staging.example.com");
  });
});

describe("G5: 点击外部收起", () => {
  // click-outside 监听器在宏任务注册, 触发外部点击前先让出宏任务
  function flushMacrotask() {
    return new Promise<void>((resolve) => setTimeout(resolve, 0));
  }

  it("TC-012: 点击下拉外部自动收起", async () => {
    const { wrapper } = await mountEnvMenu();
    await wrapper.find(".env").trigger("click");
    expect(wrapper.find(".envmenu").exists()).toBe(true);
    await flushMacrotask();
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await vi.waitFor(() => expect(wrapper.find(".envmenu").exists()).toBe(false));
  });

  it("TC-013: 点击下拉内部不自动收起", async () => {
    const { wrapper } = await mountEnvMenu();
    await wrapper.find(".env").trigger("click");
    expect(wrapper.find(".envmenu").exists()).toBe(true);
    await wrapper.find(".envmenu").trigger("click");
    expect(wrapper.find(".envmenu").exists()).toBe(true);
  });

  it("TC-014: 管理环境入口打开弹层时父下拉已收起, 状态不错乱", async () => {
    const { wrapper } = await mountEnvMenu();
    await wrapper.find(".env").trigger("click");
    await wrapper.find("[data-manage-env]").trigger("click");
    expect(wrapper.find(".envmenu").exists()).toBe(false);
    expect(wrapper.find(".enveditor").exists()).toBe(true);
  });
});
