// TS-013 (验收缺口): 新建集合 action + 空集合目录行为
// 接缝: store.createCollection — 经适配层写默认配置隐式建集合 (后端 mkdir parents),
// 成功后刷新集合列表并选中新集合; 失败 (名称非法/422) 错误抛给 UI.
// TS-013b: 切换集合清空集合绑定状态 (审核修复: 旧集合残留).
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

  it.each(["foo/bar", "foo\\bar", "a..b", ".hidden"])(
    "TC-101: 非法名 %j 被 mock 以 422 拒绝 (与后端 _validate_name 对齐), 当前集合不变",
    async (badName) => {
      const services = createMockServices(presetBilling());
      const store = createAppStore(services);
      await store.init();
      // 不经 spy 注错: mock 自身校验, 错误形状对齐 http 层 ApiError (带 status)
      await expect(store.createCollection(badName)).rejects.toMatchObject({ status: 422 });
      expect(store.state.collection).toBe("billing");
      expect(store.state.collections).toEqual(["billing"]);
    },
  );

  it("TC-101b: 含空格名后端接受, mock 同样放行 (校验口径一致)", async () => {
    const services = createMockServices(presetBilling());
    const store = createAppStore(services);
    await store.init();
    await store.createCollection("bad name");
    expect(store.state.collection).toBe("bad name");
    expect(store.state.collections).toContain("bad name");
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

describe("切换集合状态清理 (store)", () => {
  it("TC-108: 切换集合清空集合绑定状态 (选中/草稿/响应/运行徽标/断言高亮), 全局状态保留", async () => {
    const seed = presetBilling();
    seed.collections.orders = { tree: { name: "orders", subfolders: [], items: {} } };
    const services = createMockServices(seed);
    const store = createAppStore(services);
    await store.init();
    // 旧集合残留: 选中条目 + 草稿 (经真实 action 装载)
    const node = store.state.root!.folders.find((f) => f.name === "订单")!;
    store.selectItem(node.items.find((i) => i.slug === "list")!);
    await store.loadDraft();
    expect(store.state.selected?.slug).toBe("list");
    expect(store.state.draft?.name).toBe("订单列表");
    // 响应面板/运行徽标/断言高亮/进行中标记 (模拟 send/run 后的残留)
    store.state.response = {
      meta: null,
      bodyText: "ok",
      bodyBytes: 2,
      done: null,
      history: null,
    };
    store.state.responseTab = "Headers";
    store.state.runResults = { list: { status: "failed" } };
    store.state.assertionHighlight = 0;
    store.state.builderTab = "断言";
    store.state.sending = true;
    store.state.running = true;
    store.state.runDone = Promise.resolve();
    const envsBefore = store.state.envs;
    const envVarsBefore = store.state.envVars;

    await store.selectCollection("orders");

    // 集合绑定状态清空
    expect(store.state.selected).toBeNull();
    expect(store.state.draft).toBeNull();
    expect(store.state.response).toBeNull();
    expect(store.state.responseTab).toBe("Body");
    expect(store.state.runResults).toEqual({});
    expect(store.state.assertionHighlight).toBeNull();
    expect(store.state.builderTab).toBe("Params");
    expect(store.state.sending).toBe(false);
    expect(store.state.running).toBe(false);
    expect(store.state.runDone).toBeNull();
    // 新集合装载
    expect(store.state.collection).toBe("orders");
    expect(store.state.root?.name).toBe("orders");
    expect(store.state.collectionVars).toEqual({});
    // 全局状态 (环境) 不清
    expect(store.state.activeEnv).toBe("prod");
    expect(store.state.envs).toEqual(envsBefore);
    expect(store.state.envVars).toEqual(envVarsBefore);
  });

  it("TC-109: 新建集合同样不残留旧集合状态 (createCollection 经 selectCollection)", async () => {
    const services = createMockServices(presetBilling());
    const store = createAppStore(services);
    await store.init();
    const node = store.state.root!.folders.find((f) => f.name === "订单")!;
    store.selectItem(node.items[0]);
    await store.loadDraft();
    store.state.runResults = { list: { status: "passed" } };

    await store.createCollection("orders");

    expect(store.state.collection).toBe("orders");
    expect(store.state.selected).toBeNull();
    expect(store.state.draft).toBeNull();
    expect(store.state.runResults).toEqual({});
  });

  it("TC-110: 选中条目自动装载草稿 (树点击路径, 无需显式 loadDraft)", async () => {
    const services = createMockServices(presetBilling());
    const store = createAppStore(services);
    await store.init();
    const node = store.state.root!.folders.find((f) => f.name === "订单")!;
    // 模拟树点击: 只调 selectItem, 微任务排空后草稿应已装载
    store.selectItem(node.items.find((i) => i.slug === "list")!);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(store.state.selected?.slug).toBe("list");
    expect(store.state.draft?.name).toBe("订单列表");
  });
});
