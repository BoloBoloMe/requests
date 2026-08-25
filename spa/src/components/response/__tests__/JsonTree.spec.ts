// TS-002 (ISSUE-04): JsonTree 折叠树 (原型 .json/.fold/.ln + 键/字符串/数字/布尔着色)
// 接缝: src/components/response/JsonTree.vue
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import JsonTree from "../JsonTree.vue";

const DOC = { orders: [{ id: 1024, status: "open" }, { id: 1025 }], total: 57, paid: false, note: "含\"引号" };

describe("JsonTree", () => {
  it("TC-004: 渲染嵌套 JSON 并带行号与着色类", () => {
    const wrapper = mount(JsonTree, { props: { data: DOC } });
    const lines = wrapper.findAll(".json > div");
    expect(lines.length).toBeGreaterThan(3);
    expect(wrapper.find(".ln").exists()).toBe(true);
    // 行号从 1 连续编号
    expect(wrapper.findAll(".ln").map((n) => n.text())).toEqual(
      lines.map((_, i) => String(i + 1)),
    );
    expect(wrapper.find(".k").exists()).toBe(true); // 键
    expect(wrapper.find(".n").exists()).toBe(true); // 数字
    expect(wrapper.find(".s").exists()).toBe(true); // 字符串
    expect(wrapper.find(".b").exists()).toBe(true); // 布尔
    expect(wrapper.text()).toContain('"orders"');
    expect(wrapper.text()).toContain("1024");
  });

  it("TC-005: 点折叠记号收起子树, 状态按路径键记录", async () => {
    const wrapper = mount(JsonTree, { props: { data: DOC } });
    const before = wrapper.findAll(".json > div").length;
    const fold = wrapper.find('[data-path="orders"] .fold, .fold[data-path="orders"]');
    expect(fold.exists()).toBe(true);
    await fold.trigger("click");
    const after = wrapper.findAll(".json > div").length;
    expect(after).toBeLessThan(before);
    // 折叠后显示 ▸ 与占位
    expect(wrapper.text()).toContain("▸");
    expect(wrapper.text()).toContain("…");
    // 再点展开还原
    await wrapper.find('.fold[data-path="orders"]').trigger("click");
    expect(wrapper.findAll(".json > div").length).toBe(before);
  });

  it("非对象/数组标量与 null 也可渲染", () => {
    expect(mount(JsonTree, { props: { data: null } }).text()).toContain("null");
    expect(mount(JsonTree, { props: { data: "文本" } }).text()).toContain("文本");
  });
});
