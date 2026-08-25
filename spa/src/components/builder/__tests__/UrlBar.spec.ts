// TS-001 (ISSUE-03): URL 变量高亮 + 解析预览
// 接缝: UrlBar 组件 + 环境 store (变量优先级: 集合 vars < 环境 vars, M2 D012)
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMockServices, presetBilling } from "../../../services/mock";
import { SERVICES_KEY } from "../../../services";
import { createAppStore, STORE_KEY } from "../../../stores/app";
import UrlBar from "../UrlBar.vue";

async function mountUrlBar(url: string) {
  const services = createMockServices(presetBilling());
  const store = createAppStore(services);
  await store.init();
  const wrapper = mount(UrlBar, {
    props: { url, method: "GET" },
    global: { provide: { [SERVICES_KEY as symbol]: services, [STORE_KEY as symbol]: store } },
  });
  return { wrapper, store };
}

describe("UrlBar 变量高亮与解析预览", () => {
  it("TC-001: {{var}} 高亮为变量 span (非纯文本)", async () => {
    const { wrapper } = await mountUrlBar("https://{{host}}/v1/orders");
    const varSpan = wrapper.find(".urlin .var");
    expect(varSpan.exists()).toBe(true);
    expect(varSpan.text()).toBe("{{host}}");
  });

  it("TC-002: 环境切换后解析预览行 → URL 相应替换变量值", async () => {
    const { wrapper, store } = await mountUrlBar("https://{{host}}/v1/orders?c={{coupon}}");
    // 激活环境 prod + 集合变量 coupon: 环境 vars 优先于集合 vars (M2 D012)
    expect(wrapper.find(".resolved").text()).toBe(
      "→ https://api.example.com/v1/orders?c=SUMMER26",
    );
    await store.setActiveEnv("staging");
    expect(wrapper.find(".resolved").text()).toBe(
      "→ https://api.staging.example.com/v1/orders?c=SUMMER26",
    );
  });

  it("TC-002b: 未解析变量在预览中原样保留 {{var}}", async () => {
    const { wrapper } = await mountUrlBar("https://{{missing}}/x");
    expect(wrapper.find(".resolved").text()).toBe("→ https://{{missing}}/x");
  });
});
