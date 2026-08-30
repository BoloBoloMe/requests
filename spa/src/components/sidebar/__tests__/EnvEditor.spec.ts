// G2 (ISSUE-02 后续): 环境管理弹层 — 列表/新建/改名/编辑 vars+secrets/删除/设为激活
// 接缝: EnvMenu 下拉入口 + EnvEditor 组件 + store 环境管理动作 + mock 适配层
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import EnvMenu from "../EnvMenu.vue";

async function mountEnvMenu(seed = presetBilling()) {
  const services = createMockServices(seed);
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(EnvMenu, {
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store, services };
}

async function openEditor() {
  const ctx = await mountEnvMenu();
  await ctx.wrapper.find(".env").trigger("click");
  await ctx.wrapper.find("[data-manage-env]").trigger("click");
  const editor = ctx.wrapper.find(".enveditor");
  expect(editor.exists()).toBe(true);
  return { ...ctx, editor };
}

describe("环境管理弹层", () => {
  it("TC-001: EnvMenu 下拉尾部入口打开弹层, 默认选中激活环境并装载 vars/secrets", async () => {
    const { store, editor } = await openEditor();
    expect(editor.find('[data-env-item="prod"]').classes()).toContain("on");
    expect(editor.find('[data-env-item="staging"]').exists()).toBe(true);
    // prod vars (host) 装载进编辑行
    const keys = editor
    .findAll(".ee-kv input[placeholder='key']")
    .map((i) => (i.element as HTMLInputElement).value);
    expect(keys).toContain("host");
    expect(store.state.activeEnv).toBe("prod");
  });

  it("TC-002: 编辑 vars 与 secrets 保存后整体替换写, 激活环境变量视图刷新", async () => {
    const { editor, services, store } = await openEditor();
    // 改 host 值 + secrets 加一行
    const varValue = editor.findAll(".ee-kv")[0]!.find("input[placeholder='value']");
    await varValue.setValue("http://changed");
    await editor.find("[data-env-secret-key]").setValue("token");
    const secretInputs = editor.findAll(".ee-kv")[1]!.findAll("input");
    await secretInputs[1]!.setValue("s3cret");
    await secretInputs[0]!.trigger("keydown.enter");
    await editor.find("[data-env-save]").trigger("click");
    await vi.waitFor(() => expect(store.state.envVars).toEqual({ host: "http://changed", token: "s3cret" }));
    // 落库形状: vars 整体替换, secrets 单独文件
    const env = await services.getEnvironment("prod");
    expect(env.vars).toEqual({ host: "http://changed" });
    expect(env.secrets).toEqual({ token: "s3cret" });
    // 激活环境 envVars 同步刷新 (merged)
    expect(store.state.envVars).toEqual({ host: "http://changed", token: "s3cret" });
  });

  it("TC-003: 新建环境: 内联表单提交后出现在列表并选中", async () => {
    const { editor, store } = await openEditor();
    await editor.find("[data-env-new]").trigger("click");
    await editor.find("[data-env-new-name]").setValue("test");
    await editor.find("[data-env-new-submit]").trigger("click");
    await vi.waitFor(() => expect(store.state.envs).toContain("test"));
    expect(editor.find('[data-env-item="test"]').classes()).toContain("on");
    // 新环境空 vars, 编辑区名称同步
    expect((editor.find("[data-env-name]").element as HTMLInputElement).value).toBe("test");
  });

  it("TC-004: 改名保存 = 写新删旧; 激活态若是旧名则迁移到新名", async () => {
    const { editor, store, services } = await openEditor();
    await editor.find("[data-env-name]").setValue("production");
    await editor.find("[data-env-save]").trigger("click");
    await vi.waitFor(() => expect(store.state.envs).toContain("production"));
    expect(store.state.envs).not.toContain("prod");
    // 激活态迁移 (prod 原为激活)
    await vi.waitFor(() => expect(store.state.activeEnv).toBe("production"));
    await expect(services.getEnvironment("prod")).rejects.toThrow("环境不存在");
    // vars 随改名迁移
    const env = await services.getEnvironment("production");
    expect(env.vars).toEqual({ host: "api.example.com" });
  });

  it("TC-005: 删除环境: 列表移除; 删除非激活环境不影响激活态", async () => {
    const { editor, store } = await openEditor();
    await editor.find('[data-env-item="staging"]').trigger("click");
    await editor.find("[data-env-delete]").trigger("click");
    await vi.waitFor(() => expect(store.state.envs).toEqual(["prod"]));
    expect(store.state.activeEnv).toBe("prod");
  });

  it("TC-006: 删除激活环境: 激活态归空, 变量视图清空", async () => {
    const { editor, store } = await openEditor();
    await editor.find("[data-env-delete]").trigger("click");
    await vi.waitFor(() => expect(store.state.envs).toEqual(["staging"]));
    await vi.waitFor(() => expect(store.state.activeEnv).toBeNull());
    expect(store.state.envVars).toEqual({});
  });

  it("TC-007: 设为激活: 写适配层激活状态, 列表勾选移动", async () => {
    const { editor, store, services } = await openEditor();
    await editor.find('[data-env-item="staging"]').trigger("click");
    await editor.find("[data-env-activate]").trigger("click");
    await vi.waitFor(() => expect(store.state.activeEnv).toBe("staging"));
    expect(await services.getActiveEnvironment()).toBe("staging");
    expect(editor.find('[data-env-item="staging"] .check').exists()).toBe(true);
    // 变量视图随激活环境刷新
    expect(store.state.envVars.host).toBe("api.staging.example.com");
  });
});

describe("G5: 点击外部收起", () => {
  // click-outside 监听器在宏任务注册, 触发外部点击前先让出宏任务
  function flushMacrotask() {
    return new Promise<void>((resolve) => setTimeout(resolve, 0));
  }

  it("TC-015: 点击弹层外部触发 close", async () => {
    const { wrapper } = await openEditor();
    await flushMacrotask();
    expect(wrapper.find(".enveditor").exists()).toBe(true);
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await vi.waitFor(() => expect(wrapper.find(".enveditor").exists()).toBe(false));
  });

  it("TC-016: 点击弹层内部输入框不触发 close", async () => {
    const { wrapper } = await openEditor();
    await flushMacrotask();
    await wrapper.find("[data-env-name]").trigger("click");
    expect(wrapper.find(".enveditor").exists()).toBe(true);
  });

  it("TC-017: 点击取消按钮仅由按钮自身逻辑关闭, 不与外部监听冲突", async () => {
    const { wrapper } = await openEditor();
    await flushMacrotask();
    await wrapper.find("[data-env-cancel]").trigger("click");
    expect(wrapper.find(".enveditor").exists()).toBe(false);
  });
});
