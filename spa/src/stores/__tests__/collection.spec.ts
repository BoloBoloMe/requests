// TS-013 (验收缺口): 新建集合 action + 空集合目录行为
// 接缝: store.createCollection — 经适配层写默认配置隐式建集合 (后端 mkdir parents),
// 成功后刷新集合列表并选中新集合; 失败 (名称非法/422) 错误抛给 UI.
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../services/mock";
import { createAppStore } from "../app";

describe("新建集合 (store)", () => {
  it("TC-100: 写默认配置隐式建集合, 列表刷新并选中新集合", async () => {
    const services = createMockServices(presetBilling());
    const store = createAppStore(services);
    await store.init();
    const putSpy = vi.spyOn(services, "putCollectionConfig");
    await store.createCollection("orders");
    // 默认配置形状: 空 vars + 空 defaults (D010 PUT 即整体替换)
    expect(putSpy).toHaveBeenCalledWith("orders", {
      vars: {},
      defaults: { auth: null, headers: [] },
    });
    expect(store.state.collections).toContain("orders");
    expect(store.state.collection).toBe("orders");
    // 选中新集合后集合树装载 (空树)
    expect(store.state.root?.name).toBe("orders");
    expect(store.state.root?.items).toEqual([]);
  });

  it("TC-101: 后端拒绝 (名称非法/422) 时错误抛出, 当前集合不变", async () => {
    const services = createMockServices(presetBilling());
    const store = createAppStore(services);
    await store.init();
    vi.spyOn(services, "putCollectionConfig").mockRejectedValue(
      new Error("422: 集合名非法"),
    );
    await expect(store.createCollection("bad name")).rejects.toThrow("422");
    expect(store.state.collection).toBe("billing");
    expect(store.state.collections).toEqual(["billing"]);
  });

  it("TC-102: 空集合目录 init 不自动选中, 新建首个集合后即选中", async () => {
    const services = createMockServices({ collections: {} });
    const store = createAppStore(services);
    await store.init();
    expect(store.state.collections).toEqual([]);
    expect(store.state.collection).toBeNull();
    expect(store.state.root).toBeNull();
    await store.createCollection("first");
    expect(store.state.collection).toBe("first");
    expect(store.state.root?.name).toBe("first");
  });
});
