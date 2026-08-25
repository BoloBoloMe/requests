// TS-001 (ISSUE-01): http client 的 token 接缝
// 接缝: src/api/http.ts 公开请求函数 (fetch 与 token provider 均可注入替换)
import { describe, expect, it, vi } from "vitest";
import { MissingTokenError, request, windowTokenProvider } from "../http";

function fakeFetch(body = "{}") {
  return vi.fn(async () => new Response(body, { status: 200 }));
}

describe("api/http request", () => {
  it("TC-001: 请求自动携带 X-Auth-Token 头", async () => {
    const fetchFn = fakeFetch();
    await request("/collections", {}, { fetchFn, tokenProvider: () => "tok-1" });
    expect(fetchFn).toHaveBeenCalledOnce();
    const [, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Auth-Token"]).toBe("tok-1");
  });

  it("TC-002: token 缺失/空时抛可诊断错误且不发起请求", async () => {
    const fetchFn = fakeFetch();
    await expect(
      request("/collections", {}, { fetchFn, tokenProvider: () => null }),
    ).rejects.toThrow(MissingTokenError);
    await expect(
      request("/collections", {}, { fetchFn, tokenProvider: () => "" }),
    ).rejects.toThrow(/token/);
    expect(fetchFn).not.toHaveBeenCalled();
  });
});

describe("api/http windowTokenProvider", () => {
  it("从 window.__APIC_TOKEN__ 读取注入 token", () => {
    (window as unknown as Record<string, unknown>).__APIC_TOKEN__ = "injected";
    expect(windowTokenProvider()).toBe("injected");
    delete (window as unknown as Record<string, unknown>).__APIC_TOKEN__;
  });

  it("CSP 拦截内联脚本时从 meta[apic-token] 兜底读取", () => {
    const meta = document.createElement("meta");
    meta.setAttribute("name", "apic-token");
    meta.setAttribute("content", "meta-token");
    document.head.appendChild(meta);
    expect(windowTokenProvider()).toBe("meta-token");
    meta.remove();
  });

  it("未托管场景 (占位符未替换/缺失) 返回 null 走降级", () => {
    const meta = document.createElement("meta");
    meta.setAttribute("name", "apic-token");
    meta.setAttribute("content", "__APIC_TOKEN_VALUE__");
    document.head.appendChild(meta);
    expect(windowTokenProvider()).toBeNull();
    meta.remove();
  });
});
