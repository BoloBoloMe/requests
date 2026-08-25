// TS-003 (ISSUE-03): kv 行编辑器 (Params/Headers 共用)
// 接缝: KvEditor 组件 (无边框悬停显框 + 描述列 + 末行回车增行 + 行删除)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { KV } from "../../../services/types";
import KvEditor from "../KvEditor.vue";

function mountKv(rows: KV[]) {
  return mount(KvEditor, { props: { rows } });
}

describe("KvEditor", () => {
  it("TC-004: 末行回车新增空白 kv 行", async () => {
    const wrapper = mountKv([{ key: "status", value: "open" }]);
    expect(wrapper.findAll(".kv:not(.add)").length).toBe(1);
    const addRow = wrapper.find(".kv.add");
    await addRow.findAll("input")[0].setValue("limit");
    await addRow.findAll("input")[1].setValue("20");
    await addRow.findAll("input")[1].trigger("keydown", { key: "Enter" });
    const emitted = wrapper.emitted("update:rows");
    expect(emitted).toBeTruthy();
    const rows = emitted!.at(-1)![0] as KV[];
    expect(rows).toHaveLength(2);
    expect(rows[1]).toMatchObject({ key: "limit", value: "20" });
  });

  it("TC-005: 行删除", async () => {
    const wrapper = mountKv([
      { key: "a", value: "1" },
      { key: "b", value: "2" },
    ]);
    await wrapper.findAll(".kv:not(.add)")[0].find(".x").trigger("click");
    const rows = wrapper.emitted("update:rows")!.at(-1)![0] as KV[];
    expect(rows).toEqual([{ key: "b", value: "2" }]);
  });

  it("TC-006: 描述列可编辑", async () => {
    const wrapper = mountKv([{ key: "status", value: "open", desc: "订单状态过滤" }]);
    const descInput = wrapper.find(".kv:not(.add) .desc input");
    expect((descInput.element as HTMLInputElement).value).toBe("订单状态过滤");
    await descInput.setValue("新描述");
    const rows = wrapper.emitted("update:rows")!.at(-1)![0] as KV[];
    expect(rows[0].desc).toBe("新描述");
  });

  it("TC-006b: 编辑已有行 key/value 发出更新", async () => {
    const wrapper = mountKv([{ key: "status", value: "open" }]);
    await wrapper.find(".kv:not(.add) input").setValue("state");
    const rows = wrapper.emitted("update:rows")!.at(-1)![0] as KV[];
    expect(rows[0].key).toBe("state");
  });
});
