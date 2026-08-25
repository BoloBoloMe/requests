// TS-005 (ISSUE-03): 断言编辑器 (结构化表单 + Python 逃生舱, M6 决策 1 双形态)
// 接缝: AssertionEditor 组件 (target/op/expect 行 + CodeMirror 6 编辑框)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Assertion } from "../../../services/types";
import AssertionEditor from "../AssertionEditor.vue";

function mountAssertions(assertions: Assertion[]) {
  return mount(AssertionEditor, {
    props: { assertions },
    attachTo: document.body,
  });
}

describe("AssertionEditor", () => {
  it("TC-009: 结构化行 target/op/expect 渲染与编辑", async () => {
    const wrapper = mountAssertions([{ target: "status", op: "eq", expect: 200 }]);
    const row = wrapper.find(".alist .row");
    expect((row.find('input[data-f="target"]').element as HTMLInputElement).value).toBe("status");
    expect((row.find('select[data-f="op"]').element as HTMLSelectElement).value).toBe("eq");
    expect((row.find('input[data-f="expect"]').element as HTMLInputElement).value).toBe("200");
    // 编辑 target 写回
    await row.find('input[data-f="target"]').setValue("body.total");
    const out = wrapper.emitted("update:assertions")!.at(-1)![0] as Assertion[];
    expect(out[0]).toMatchObject({ target: "body.total", op: "eq", expect: 200 });
    // expect 按 JSON 解析 (字符串/数字/布尔)
    await row.find('input[data-f="expect"]').setValue('"open"');
    const out2 = wrapper.emitted("update:assertions")!.at(-1)![0] as Assertion[];
    expect(out2[0].expect).toBe("open");
  });

  it("TC-009b: 行增删", async () => {
    const wrapper = mountAssertions([]);
    await wrapper.find('button[data-add="structured"]').trigger("click");
    let out = wrapper.emitted("update:assertions")!.at(-1)![0] as Assertion[];
    expect(out).toHaveLength(1);
    expect(out[0].op).toBe("eq");
    await wrapper.find('button[data-add="python"]').trigger("click");
    out = wrapper.emitted("update:assertions")!.at(-1)![0] as Assertion[];
    expect(out.some((a) => "python" in a)).toBe(true);
  });

  it("TC-010: Python 逃生舱挂载 CodeMirror 编辑框, 输入可读回", async () => {
    const wrapper = mountAssertions([{ python: "assert response.status == 200" }]);
    // CodeMirror 6 挂载: .cm-editor 存在且含初始文档
    const cm = wrapper.find(".cm-editor");
    expect(cm.exists()).toBe(true);
    expect(cm.text()).toContain("assert response.status == 200");
    // 经组件公开事件改值可读回 (双向绑定)
    const editor = wrapper.findComponent({ name: "CodeEditor" });
    editor.vm.$emit("update:value", "assert response.elapsed_ms < 300");
    const out = wrapper.emitted("update:assertions")!.at(-1)![0] as Assertion[];
    expect(out[0].python).toBe("assert response.elapsed_ms < 300");
    wrapper.unmount();
  });
});
