// api/sse.ts: SSE 流解析 (M3 D007 事件模型 meta/chunk/done, direction-a Q1-6 自研点)
// /execute 是 POST, EventSource 不可用 → fetch + ReadableStream 分块解析;
// 行缓冲合并跨块边界 (半行/半事件), data 载荷按 JSON 解码为结构化事件.
import type { ExecuteEvent } from "../services/types";

export interface SseParser {
  /** 喂入一段文本, 返回本段内凑齐的完整事件 */
  push(chunk: string): ExecuteEvent[];
}

/** 增量 SSE 解析器: event:/data: 字段, 空行结帧, 多行 data 以 \n 连接 */
export function createSseParser(): SseParser {
  let buffer = "";
  let eventName = "";
  let dataLines: string[] = [];

  function flushFrame(): ExecuteEvent | null {
    if (dataLines.length === 0) {
      eventName = "";
      return null;
    }
    const raw = dataLines.join("\n");
    const payload = JSON.parse(raw) as ExecuteEvent & { type?: string };
    // event: 字段优先; 缺省按载荷自身 type (M3 D007 事件均带 type)
    if (eventName && payload && typeof payload === "object") {
      (payload as { type: string }).type = eventName;
    }
    eventName = "";
    dataLines = [];
    return payload;
  }

  function push(chunk: string): ExecuteEvent[] {
    buffer += chunk;
    const events: ExecuteEvent[] = [];
    let nl: number;
    while ((nl = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, nl).replace(/\r$/, "");
      buffer = buffer.slice(nl + 1);
      if (line === "") {
        const event = flushFrame();
        if (event) events.push(event);
      } else if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
      // 注释行 (: 开头) 与其他字段忽略
    }
    return events;
  }

  return { push };
}

/** 从 fetch Response 体产出事件流 (UTF-8 解码 + 增量解析) */
export async function* eventsFromResponse(resp: Response): AsyncGenerator<ExecuteEvent> {
  if (!resp.body) throw new Error("响应体为空: /execute 未返回可读流 (M3 D007)");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const event of parser.push(decoder.decode(value, { stream: true }))) yield event;
    }
    for (const event of parser.push(decoder.decode())) yield event;
  } finally {
    // 断连只停消费, 后端执行不取消 (M3 D006)
    reader.releaseLock();
  }
}
