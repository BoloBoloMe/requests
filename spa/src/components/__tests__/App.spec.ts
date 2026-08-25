// TS-002 (ISSUE-01): App 骨架占位结构
// 接缝: App.vue 渲染的左右双栏骨架 (M5 决策 1 布局)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import App from "../../App.vue";

describe("App 骨架", () => {
  it("TC-003: 挂载后同时存在侧栏与请求/响应占位容器", () => {
    const wrapper = mount(App);
    // 左侧栏占位 (变体 B .side) 与右主区上下分区 (.reqpane/.resp)
    expect(wrapper.find(".side").exists()).toBe(true);
    expect(wrapper.find(".main").exists()).toBe(true);
    expect(wrapper.find(".reqpane").exists()).toBe(true);
    expect(wrapper.find(".resp").exists()).toBe(true);
  });
});
