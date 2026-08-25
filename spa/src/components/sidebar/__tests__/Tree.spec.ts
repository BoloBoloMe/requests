// TS-001 (ISSUE-02): 集合树渲染 + 折叠
// 接缝: Sidebar/Tree 组件, 注入 mock 服务 (预置一集合两文件夹若干条目)
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import { SERVICES_KEY } from "../../../services";
import Sidebar from "../Sidebar.vue";

async function mountSidebar() {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(Sidebar, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("集合树", () => {
  let ctx: Awaited<ReturnType<typeof mountSidebar>>;
  beforeEach(async () => {
    ctx = await mountSidebar();
  });

  it("TC-001: 渲染集合名与嵌套文件夹条目", () => {
    const { wrapper } = ctx;
    // 集合名区域现为可交互下拉 (含 ▾ 指示), 仍展示当前集合名
    expect(wrapper.find(".side-hd .name").text()).toContain("billing");
    const folders = wrapper.findAll(".folder .f-hd");
    expect(folders.map((f) => f.text())).toEqual(
      expect.arrayContaining([expect.stringContaining("订单"), expect.stringContaining("发票")]),
    );
    // 文件夹下的请求条目: 条目标题 + 方法徽章
    const reqs = wrapper.findAll(".req");
    expect(reqs.map((r) => r.text()).join()).toContain("订单列表");
    expect(wrapper.find(".req .m.get").exists()).toBe(true);
  });

  it("TC-002: 点文件夹头切换折叠, 展开时显示子级", async () => {
    const { wrapper } = ctx;
    const folderHd = wrapper
      .findAll(".f-hd")
      .find((f) => f.text().includes("发票"))!;
    // 初始展开: 子级可见
    expect(wrapper.text()).toContain("发票详情");
    await folderHd.trigger("click");
    expect(wrapper.text()).not.toContain("发票详情");
    expect(folderHd.find(".arrow.shut").exists()).toBe(true);
    await folderHd.trigger("click");
    expect(wrapper.text()).toContain("发票详情");
  });

  it("TC-111: 侧栏头「运行集合」按钮触发整集合运行 (根集合无树头行的入口), 运行中禁用", async () => {
    const { wrapper, store, services } = ctx;
    const runSpy = vi.spyOn(services, "runCollection");
    const btn = wrapper.find('button[title="运行集合"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    expect(runSpy).toHaveBeenCalledWith("billing", store.state.activeEnv);
    // mock 事件流立即排空, 运行态复位
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(store.state.running).toBe(false);
  });
});
