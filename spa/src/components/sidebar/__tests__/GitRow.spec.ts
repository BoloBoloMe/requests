// TS-003 (ISSUE-05): git 行单同步按钮 (M5 决策 2, D009 冲突即停原样输出)
// 接缝: GitRow 组件 + store.syncGit() 状态机 (dirty/syncing/synced/failed)
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import GitRow from "../GitRow.vue";

async function mountGitRow() {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  const wrapper = mount(GitRow, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

describe("GitRow 单同步", () => {
  it("TC-003: 初始 dirty (⎇ main ↑), 点同步→同步中 (禁重复), 成功→✓ 已同步", async () => {
    const { wrapper, services } = await mountGitRow();
    expect(wrapper.find(".branch").text()).toBe("main");
    expect(wrapper.find(".up").exists()).toBe(true);
    expect(wrapper.find(".up").text()).toContain("↑");

    let release!: () => void;
    const syncSpy = vi
      .spyOn(services, "gitSync")
      .mockImplementation(() => new Promise<void>((r) => (release = r)));
    const btn = wrapper.find('button[data-action="sync"]');
    await btn.trigger("click");
    expect(btn.text()).toContain("同步中");
    expect((btn.element as HTMLButtonElement).disabled).toBe(true);
    // 同步中重复点击不再发起
    await btn.trigger("click");
    expect(syncSpy).toHaveBeenCalledTimes(1);
    release();
    await vi.waitFor(() => expect(wrapper.find(".synced").exists()).toBe(true));
    expect(wrapper.find(".synced").text()).toContain("✓ 已同步");
    expect((wrapper.find('button[data-action="sync"]').element as HTMLButtonElement).disabled).toBe(false);
  });

  it("TC-004: 同步失败展示后端原样错误文案, 按钮可重试", async () => {
    const { wrapper, services } = await mountGitRow();
    vi.spyOn(services, "gitSync").mockRejectedValue(
      new Error("请求失败 409: 冲突: Merge conflict in collections/billing/订单/create.yaml"),
    );
    await wrapper.find('button[data-action="sync"]').trigger("click");
    await vi.waitFor(() => expect(wrapper.find(".git .err, .git-err").exists()).toBe(true));
    expect(wrapper.text()).toContain("Merge conflict in collections/billing/订单/create.yaml");
    // 可重试
    const btn = wrapper.find('button[data-action="sync"]');
    expect((btn.element as HTMLButtonElement).disabled).toBe(false);
    expect(btn.text()).not.toContain("同步中");
  });
});
