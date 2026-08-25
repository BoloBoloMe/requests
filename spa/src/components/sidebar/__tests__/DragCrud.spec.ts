// TS-003 (ISSUE-02): 树拖拽重排 + 条目 CRUD
// 接缝: 拖拽重排 (vuedraggable) + CRUD 动作调用 mock 服务
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import draggable from "vuedraggable";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
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

describe("树拖拽重排与 CRUD", () => {
  it("TC-005: 拖拽条目改变顺序后, mock 服务收到新顺序 (seq 重写)", async () => {
    const { wrapper, store, services } = await mountSidebar();
    const putSpy = vi.spyOn(services, "putItem");
    // 文件夹 订单 原顺序: list, create, cancel; 模拟拖拽后: cancel, list, create
    const node = store.findFolder(store.state.root!, "订单");
    const reordered = [node.items[2], node.items[0], node.items[1]];
    // 选中"订单"文件夹对应的 draggable (根文件夹也有一个)
    const drag = wrapper
      .findAllComponents(draggable)
      .find((d) =>
        (d.props("modelValue") as { slug: string }[]).some((i) => i.slug === "cancel"),
      )!;
    await drag.setValue(reordered);
    drag.vm.$emit("end");
    await vi.waitFor(() => expect(putSpy).toHaveBeenCalled());
    // 新顺序按 seq=0,1,2 提交到适配层
    const calls = putSpy.mock.calls.map((c) => [c[1], (c[2] as { seq?: number }).seq]);
    expect(calls).toContainEqual(["cancel", 0]);
    expect(calls).toContainEqual(["list", 1]);
    expect(calls).toContainEqual(["create", 2]);
    // 树重载后顺序生效
    await vi.waitFor(() => {
      const after = store.findFolder(store.state.root!, "订单");
      expect(after.items.map((i) => i.slug)).toEqual(["cancel", "list", "create"]);
    });
  });

  it("TC-006: 新建/删除请求条目更新树", async () => {
    const { wrapper, store, services } = await mountSidebar();
    // 新建进集合根 (异步动作完成后再断言)
    await wrapper.find('button[title="新建请求"]').trigger("click");
    await vi.waitFor(() => {
      expect(store.state.root!.items.map((i) => i.slug)).toContain("new-request");
    });
    const rootItems = store.state.root!.items.map((i) => i.slug);
    expect(rootItems).toContain("new-request");
    const created = await services.getItem("billing", "new-request");
    expect(created.name).toBe("未命名请求");
    // 新条目被选中
    expect(store.state.selected?.slug).toBe("new-request");
    // 删除: 条目行上的 ×
    const reqRow = wrapper
      .findAll(".req")
      .find((r) => r.text().includes("未命名请求"))!;
    await reqRow.find(".del").trigger("click");
    await vi.waitFor(() => {
      expect(store.state.root!.items.map((i) => i.slug)).not.toContain("new-request");
    });
    await expect(services.getItem("billing", "new-request")).rejects.toThrow();
    expect(store.state.selected).toBeNull();
  });

  it("TC-006b: 重命名条目换 slug 并持久化", async () => {
    const { store, services } = await mountSidebar();
    await store.renameItem({ slug: "invoice", folder: "发票" }, "invoice-detail");
    const node = store.findFolder(store.state.root!, "发票");
    expect(node.items.map((i) => i.slug)).toEqual(["invoice-detail"]);
    await expect(services.getItem("billing", "invoice", "发票")).rejects.toThrow();
    expect((await services.getItem("billing", "invoice-detail", "发票")).name).toBe("发票详情");
  });
});
