// TS-004 (ISSUE-03): Auth 编辑器 (继承集合默认 / 覆盖 / 无认证 三选)
// 接缝: AuthEditor 组件; auth=null 继承, {type:"none"} 无认证, {type:...} 覆盖 (M1 D003)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Auth } from "../../../services/types";
import AuthEditor from "../AuthEditor.vue";

function mountAuth(auth: Auth) {
  return mount(AuthEditor, { props: { auth } });
}

describe("AuthEditor", () => {
  it("TC-007: 三选一 (继承/覆盖/无) 选中态正确", async () => {
    // 继承 (auth=null)
    let wrapper = mountAuth(null);
    expect(wrapper.find('input[value="inherit"]').element).toHaveProperty("checked", true);
    // 无认证 (type=none)
    wrapper = mountAuth({ type: "none" });
    expect(wrapper.find('input[value="none"]').element).toHaveProperty("checked", true);
    // 覆盖 (具体类型)
    wrapper = mountAuth({ type: "bearer", token: "t" });
    expect(wrapper.find('input[value="override"]').element).toHaveProperty("checked", true);
  });

  it("TC-007b: 切换三选发出对应 auth 模型", async () => {
    const wrapper = mountAuth({ type: "bearer", token: "t" });
    await wrapper.find('input[value="inherit"]').setValue(true);
    expect(wrapper.emitted("update:auth")!.at(-1)![0]).toBeNull();
    await wrapper.find('input[value="none"]').setValue(true);
    expect(wrapper.emitted("update:auth")!.at(-1)![0]).toEqual({ type: "none" });
  });

  it("TC-008: 覆盖态展示类型选择 (Basic/Bearer/API Key/Digest) 与关联字段", async () => {
    const wrapper = mountAuth({ type: "basic", username: "u", password: "p" });
    const select = wrapper.find("select.authtype");
    expect(select.exists()).toBe(true);
    const options = select.findAll("option").map((o) => o.attributes("value"));
    expect(options).toEqual(["basic", "bearer", "apikey", "digest"]);
    // 字段编辑写回
    const userInput = wrapper.find('input[data-field="username"]');
    await userInput.setValue("u2");
    const auth = wrapper.emitted("update:auth")!.at(-1)![0] as Record<string, unknown>;
    expect(auth).toMatchObject({ type: "basic", username: "u2" });
    // 切换类型保留 radio 选中态
    await select.setValue("digest");
    const next = wrapper.emitted("update:auth")!.at(-1)![0] as Record<string, unknown>;
    expect(next.type).toBe("digest");
  });
});
