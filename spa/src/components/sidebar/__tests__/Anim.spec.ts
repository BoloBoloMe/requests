// G4: 组件动画冒烟 — Transition 包装存在 + CSS 过渡类落盘 (vite ?raw 引入源样式)
// jsdom 不跑 CSS 动画, 断言结构: 过渡包装可开合 + 类名定义在样式表
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import EnvMenu from "../EnvMenu.vue";
import css from "../../../style.css?raw";

async function mountEnvMenu() {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  return mount(EnvMenu, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
}

describe("G4 组件动画", () => {
  it("TC-001: 弹层 Transition (pop) 包装存在, 下拉可开合", async () => {
    const wrapper = await mountEnvMenu();
    await wrapper.find(".env").trigger("click");
    expect(wrapper.find(".envmenu").exists()).toBe(true);
    await wrapper.find(".env").trigger("click");
    expect(wrapper.find(".envmenu").exists()).toBe(false);
  });

  it("TC-002: CSS 过渡类落盘 (pop/fold/tabpane/badge-in + reduced-motion 降级)", () => {
    for (const cls of ["pop-enter-active", "fold-enter-active", "tabpane-enter-active", "badge-in-enter-active"]) {
      expect(css).toContain(cls);
    }
    // 只过渡 transform/opacity (避免布局抖动)
    expect(css).toMatch(/pop-enter-active[^}]*transition:\s*opacity[^;]*transform/s);
    // 动画偏好降级
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
