// TS-004 (ISSUE-02): 集合变量编辑 kv 表
// 接缝: VarEditor 组件 (集合变量 kv 表), 保存经适配层写入
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import VarEditor from "../VarEditor.vue";

async function mountVarEditor() {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(VarEditor, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("集合变量编辑", () => {
  it("TC-007: 渲染现有变量行, 加行/改值后编辑态正确", async () => {
    const { wrapper } = await mountVarEditor();
    // 预置 vars: host/coupon
    const rows = wrapper.findAll(".kv");
    expect(rows.length).toBeGreaterThanOrEqual(3); // 两行数据 + 末行加行
    const firstKey = rows[0].findAll("input")[0];
    expect((firstKey.element as HTMLInputElement).value).toBe("host");
    // 改值
    const firstVal = rows[0].findAll("input")[1];
    await firstVal.setValue("api.v2.example.com");
    // 末行回车增行
    const addRow = wrapper.find(".kv.add");
    await addRow.findAll("input")[0].setValue("region");
    await addRow.findAll("input")[0].trigger("keydown", { key: "Enter" });
    const keys = wrapper
      .findAll(".kv:not(.add)")
      .map((r) => (r.findAll("input")[0].element as HTMLInputElement).value);
    expect(keys).toContain("region");
  });

  it("TC-008: 保存调用 mock 服务写入变量集", async () => {
    const { wrapper, services } = await mountVarEditor();
    const putSpy = vi.spyOn(services, "putCollectionConfig");
    const rows = wrapper.findAll(".kv:not(.add)");
    await rows[1].findAll("input")[1].setValue("WINTER26");
    await wrapper.find(".btn.primary").trigger("click");
    expect(putSpy).toHaveBeenCalledOnce();
    const [collection, config] = putSpy.mock.calls[0] as unknown as [
      string,
      { vars: Record<string, string> },
    ];
    expect(collection).toBe("billing");
    expect(config.vars).toEqual({ host: "api.example.com", coupon: "WINTER26" });
  });

  it("TC-008b: 删行后保存不再含该变量", async () => {
    const { wrapper, services } = await mountVarEditor();
    const putSpy = vi.spyOn(services, "putCollectionConfig");
    await wrapper.findAll(".kv:not(.add)")[1].find(".x").trigger("click");
    await wrapper.find(".btn.primary").trigger("click");
    const [, config] = putSpy.mock.calls[0] as unknown as [
      string,
      { vars: Record<string, string> },
    ];
    expect(config.vars).toEqual({ host: "api.example.com" });
  });
});

describe("G5: 点击外部收起", () => {
  // click-outside 监听器在宏任务注册, 触发外部点击前先让出宏任务
  function flushMacrotask() {
    return new Promise<void>((resolve) => setTimeout(resolve, 0));
  }

  it("TC-009: 点击弹层外部触发 close", async () => {
    const { wrapper } = await mountVarEditor();
    await flushMacrotask();
    expect(wrapper.emitted("close")).toBeUndefined();
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await vi.waitFor(() => expect(wrapper.emitted("close")).toHaveLength(1));
  });

  it("TC-010: 点击弹层内部输入框不触发 close", async () => {
    const { wrapper } = await mountVarEditor();
    await flushMacrotask();
    await wrapper.find("input").trigger("click");
    expect(wrapper.emitted("close")).toBeUndefined();
  });

  it("TC-011: 点击取消按钮仅由按钮自身逻辑关闭, 不与外部监听冲突", async () => {
    const { wrapper } = await mountVarEditor();
    await flushMacrotask();
    await wrapper.find(".btn:not(.primary)").trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });
});
