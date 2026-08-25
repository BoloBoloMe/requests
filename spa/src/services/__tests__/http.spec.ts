// services/http.ts 契约测试: HTTP 适配层请求形状对齐 D010 (REST CRUD, 无版本前缀 D013)
// 接缝: createHttpServices 的公开方法, fetch 注入 fake
import { describe, expect, it, vi } from "vitest";
import { createHttpServices } from "../http";

interface Call {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: unknown;
}

function fakeBackend(routes: Record<string, unknown>) {
  const calls: Call[] = [];
  const fetchFn = vi.fn(async (input: unknown, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    calls.push({
      url,
      method,
      headers: (init?.headers ?? {}) as Record<string, string>,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    const key = `${method} ${url}`;
    const hit = routes[key];
    if (hit === undefined) return new Response('{"detail":"not found"}', { status: 404 });
    if (hit instanceof Response) return hit;
    return new Response(JSON.stringify(hit), { status: 200 });
  });
  return { calls, fetchFn: fetchFn as unknown as typeof fetch };
}

const deps = () => ({ tokenProvider: () => "tok" });

describe("services/http REST 形状", () => {
  it("listCollections → GET /collections", async () => {
    const { calls, fetchFn } = fakeBackend({ "GET /collections": { collections: ["billing"] } });
    const s = createHttpServices({ fetchFn, ...deps() });
    expect(await s.listCollections()).toEqual(["billing"]);
    expect(calls[0].headers["X-Auth-Token"]).toBe("tok");
  });

  it("listItems 带 folder query → GET /collections/{c}/items?folder=", async () => {
    const { calls, fetchFn } = fakeBackend({
      "GET /collections/billing/items?folder=%E8%AE%A2%E5%8D%95": { items: [] },
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    await s.listItems("billing", "订单");
    expect(calls[0].url).toBe("/collections/billing/items?folder=" + encodeURIComponent("订单"));
  });

  it("putItem → PUT /collections/{c}/items/{slug} 整体条目", async () => {
    const item = {
      name: "n",
      method: "GET",
      url: "https://x",
      params: [],
      headers: [],
      body: { type: "none" as const },
      auth: null,
      assert: [],
    };
    const { calls, fetchFn } = fakeBackend({
      [`PUT /collections/billing/items/a?folder=${encodeURIComponent("订单")}`]: item,
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    await s.putItem("billing", "a", item, "订单");
    expect(calls[0].method).toBe("PUT");
    expect(calls[0].url).toContain("folder=");
    expect(calls[0].body).toMatchObject({ name: "n", method: "GET" });
  });

  it("deleteItem → DELETE, 204 无体", async () => {
    const { calls, fetchFn } = fakeBackend({
      "DELETE /collections/billing/items/a": new Response(null, { status: 204 }),
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    await expect(s.deleteItem("billing", "a")).resolves.toBeUndefined();
    expect(calls[0].method).toBe("DELETE");
  });

  it("集合配置读写 → GET/PUT /collections/{c}/collection", async () => {
    const config = { vars: { host: "h" }, defaults: { auth: null, headers: [] } };
    const { calls, fetchFn } = fakeBackend({
      "GET /collections/billing/collection": config,
      "PUT /collections/billing/collection": config,
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    expect((await s.getCollectionConfig("billing")).vars.host).toBe("h");
    await s.putCollectionConfig("billing", config);
    expect(calls[1].body).toMatchObject({ vars: { host: "h" } });
  });

  it("激活环境 → GET/PUT /state", async () => {
    const { calls, fetchFn } = fakeBackend({
      "GET /state": { active_environment: "prod" },
      "PUT /state": { active_environment: "staging" },
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    expect(await s.getActiveEnvironment()).toBe("prod");
    await s.setActiveEnvironment("staging");
    expect(calls[1].body).toEqual({ active_environment: "staging" });
  });

  it("环境枚举无契约端点时降级为 [激活环境] (后端缺口降级, 见备注)", async () => {
    const { fetchFn } = fakeBackend({
      "GET /state": { active_environment: "prod" },
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    // GET /environments 404 → 降级
    expect(await s.listEnvironments()).toEqual(["prod"]);
  });

  it("文件夹枚举无契约端点时降级为 [] (平铺树)", async () => {
    const { fetchFn } = fakeBackend({});
    const s = createHttpServices({ fetchFn, ...deps() });
    expect(await s.listFolders("billing")).toEqual([]);
  });

  it("gitSync → POST /git/sync, 409 抛带后端原文错误", async () => {
    const { calls, fetchFn } = fakeBackend({
      "POST /git/sync": new Response('{"detail":"冲突: 原样 git 输出"}', { status: 409 }),
    });
    const s = createHttpServices({ fetchFn, ...deps() });
    await expect(s.gitSync()).rejects.toThrow(/冲突/);
    expect(calls[0].method).toBe("POST");
  });
});
