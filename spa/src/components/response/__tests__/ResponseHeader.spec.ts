// TS-004 (ISSUE-04): 响应头行 (原型 .r-hd: 状态徽章/元信息/断言计数胶囊)
// 接缝: src/components/response/ResponseHeader.vue
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ResponseHeader from "../ResponseHeader.vue";
import type { DoneEvent } from "../../../services/types";

function done(status: DoneEvent["status"], assertions: DoneEvent["assertions"] = []): DoneEvent {
  return {
    type: "done",
    timestamp: "2026-08-25T11:00:00",
    item: "billing/create",
    status,
    duration_ms: 128,
    assertions,
  };
}

describe("ResponseHeader", () => {
  it("TC-008: 状态码 <300→ok, 300-499→warn, >=500→err", () => {
    expect(mount(ResponseHeader, { props: { done: done(200), bodyBytes: 100 } }).find(".status").classes()).toContain("ok");
    expect(mount(ResponseHeader, { props: { done: done(302), bodyBytes: 100 } }).find(".status").classes()).toContain("warn");
    expect(mount(ResponseHeader, { props: { done: done(404), bodyBytes: 100 } }).find(".status").classes()).toContain("warn");
    expect(mount(ResponseHeader, { props: { done: done(500), bodyBytes: 100 } }).find(".status").classes()).toContain("err");
  });

  it("TC-009: 显示 ms/KB/时刻与断言计数胶囊 (全过 ok, 有失败 bad)", () => {
    const assertions: DoneEvent["assertions"] = [
      { assertion: { target: "status", op: "eq", expect: 200 }, ok: true, actual: 200, message: "" },
      { assertion: { target: "body.id", op: "exists" }, ok: true, actual: 1024, message: "" },
    ];
    const wrapper = mount(ResponseHeader, {
      props: { done: { ...done(200, assertions), duration_ms: 128 }, bodyBytes: 4300, receivedAt: new Date("2026-08-25T11:00:00") },
    });
    expect(wrapper.find(".meta").text()).toContain("128");
    expect(wrapper.find(".meta").text()).toContain("4.2");
    expect(wrapper.find(".asserts").text()).toContain("断言 2/2");
    expect(wrapper.find(".asserts").classes()).toContain("ok");

    const bad = mount(ResponseHeader, {
      props: {
        done: done("assert_failed", [
          ...assertions,
          { assertion: { target: "body.x", op: "eq", expect: 1 }, ok: false, actual: 2, message: "" },
        ]),
        bodyBytes: 100,
      },
    });
    expect(bad.find(".status").classes()).toContain("err");
    expect(bad.find(".asserts").classes()).toContain("bad");
    expect(bad.find(".asserts").text()).toContain("断言 2/3");
  });

  it("传输失败 (status null + error) 显示 err 与错误码", () => {
    const wrapper = mount(ResponseHeader, {
      props: { done: { ...done(null), error: { code: "TIMEOUT", message: "请求超时" } }, bodyBytes: 0 },
    });
    expect(wrapper.find(".status").classes()).toContain("err");
    expect(wrapper.text()).toContain("TIMEOUT");
  });

  it("断言失败显示首个失败明细 (target op expect → actual), 全过则不显示", () => {
    const bad = mount(ResponseHeader, {
      props: {
        done: done("assert_failed", [
          { assertion: { target: "status", op: "eq", expect: 500 }, ok: false, actual: 200, message: "" },
        ]),
        bodyBytes: 100,
      },
    });
    expect(bad.find(".failnote").text()).toContain("status eq 500");
    expect(bad.find(".failnote").text()).toContain("200");
    const ok = mount(ResponseHeader, {
      props: {
        done: done(200, [{ assertion: { target: "status", op: "eq", expect: 200 }, ok: true, actual: 200, message: "" }]),
        bodyBytes: 100,
      },
    });
    expect(ok.find(".failnote").exists()).toBe(false);
  });
});
