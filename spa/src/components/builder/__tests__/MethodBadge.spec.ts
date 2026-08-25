// TS-002 (ISSUE-03): 方法徽章语义着色类
// 接缝: UrlBar 方法选择器 (GET 绿/POST 黄/PUT 蓝/DEL 红, 原型 MCOLOR)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import UrlBar from "../UrlBar.vue";

async function mountWithMethod(method: string) {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  return mount(UrlBar, {
    props: { url: "https://{{host}}/", method },
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
}

describe("方法徽章着色", () => {
  it("TC-003: 每方法渲染对应语义着色类 (GET/POST/PUT/DELETE)", async () => {
    const expected: Record<string, string> = {
      GET: "get",
      POST: "post",
      PUT: "put",
      DELETE: "del",
    };
    for (const [method, cls] of Object.entries(expected)) {
      const wrapper = await mountWithMethod(method);
      expect(wrapper.find(".msel").classes(), method).toContain(cls);
    }
  });
});
