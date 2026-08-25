// TS-001 (ISSUE-04): SSE 流解析器 (M3 D007 事件模型 meta/chunk/done)
// 接缝: src/api/sse.ts 行缓冲增量解析器 + 从 fetch Response 体产出事件流
import { describe, expect, it, vi } from "vitest";
import { createSseParser, eventsFromResponse } from "../sse";
import type { ChunkEvent, DoneEvent, MetaEvent } from "../../services/types";

const META = { type: "meta", timestamp: "t0", item: "billing/list", method: "GET", resolved_url: "https://x/", env: "prod" };
const CHUNK = { type: "chunk", timestamp: "t1", item: "billing/list", index: 0, data: '{"a":1}' };
const DONE = { type: "done", timestamp: "t2", item: "billing/list", status: 200, duration_ms: 42, assertions: [] };

function frame(name: string, payload: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`;
}

describe("api/sse createSseParser", () => {
  it("TC-001: data 行序列解析为 meta/chunk/done 事件序列", () => {
    const p = createSseParser();
    const events = p.push(frame("meta", META) + frame("chunk", CHUNK) + frame("done", DONE));
    expect(events.map((e) => e.type)).toEqual(["meta", "chunk", "done"]);
    expect((events[0] as MetaEvent).resolved_url).toBe("https://x/");
    expect((events[1] as ChunkEvent).data).toBe('{"a":1}');
    expect((events[2] as DoneEvent).status).toBe(200);
  });

  it("TC-002: 事件跨块分片 (分块边界落在行中) 仍合并为完整事件", () => {
    const p = createSseParser();
    const raw = frame("chunk", CHUNK);
    const cut = raw.indexOf('"a"'); // 切在 data 行中间
    expect(p.push(raw.slice(0, cut))).toEqual([]);
    const events = p.push(raw.slice(cut));
    expect(events).toHaveLength(1);
    expect((events[0] as ChunkEvent).data).toBe('{"a":1}');
  });

  it("TC-003: 提取事件类型 (event: 字段), 缺省按 data 载荷 type 字段", () => {
    const p = createSseParser();
    const events = p.push(frame("done", DONE) + `data: ${JSON.stringify(CHUNK)}\n\n`);
    expect(events.map((e) => e.type)).toEqual(["done", "chunk"]);
  });

  it("多行 data 以 \\n 连接 (JSON 载荷跨 data 行)", () => {
    const p = createSseParser();
    const events = p.push('event: chunk\ndata: {"type":"chunk","item":"x","index":0,"data":\ndata: "hello"}\n\n');
    expect(events).toHaveLength(1);
    expect((events[0] as ChunkEvent).data).toBe("hello");
  });
});

describe("api/sse eventsFromResponse", () => {
  function sseResponse(raw: string): Response {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(raw));
        controller.close();
      },
    });
    return new Response(stream, { status: 200 });
  }

  it("从 Response ReadableStream 产出完整事件序列", async () => {
    const resp = sseResponse(frame("meta", META) + frame("done", DONE));
    const types: string[] = [];
    for await (const e of eventsFromResponse(resp)) types.push(e.type);
    expect(types).toEqual(["meta", "done"]);
  });

  it("body 缺失时抛可诊断错误", async () => {
    await expect(async () => {
      for await (const _ of eventsFromResponse(new Response(null, { status: 200 }))) void _;
    }).rejects.toThrow(/响应体/);
  });
});

describe("services/http execute (SSE 接线)", () => {
  it("POST /execute 带 Accept: text/event-stream 并产出事件流", async () => {
    const { createHttpServices } = await import("../../services/http");
    const raw = frame("meta", META) + frame("chunk", CHUNK) + frame("done", DONE);
    const fetchFn = vi.fn(
      async () =>
        new Response(
          new ReadableStream<Uint8Array>({
            start(c) {
              c.enqueue(new TextEncoder().encode(raw));
              c.close();
            },
          }),
          { status: 200 },
        ),
    );
    const services = createHttpServices({ fetchFn, tokenProvider: () => "tok" });
    const events = [];
    for await (const e of services.execute({ collection: "billing", item: "list", folder: "订单" })) {
      events.push(e);
    }
    expect(events.map((e) => e.type)).toEqual(["meta", "chunk", "done"]);
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/execute");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Accept"]).toContain("text/event-stream");
    expect((init.headers as Record<string, string>)["X-Auth-Token"]).toBe("tok");
    expect(JSON.parse(String(init.body))).toMatchObject({ collection: "billing", item: "list", folder: "订单" });
  });
});
