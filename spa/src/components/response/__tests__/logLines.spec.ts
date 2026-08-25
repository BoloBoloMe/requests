// TS-003 (ISSUE-04): 日志转录行构建器 (M5 决策 5: 完整收发转录, 不脱敏)
// 接缝: src/components/response/logLines.ts 纯函数
import { describe, expect, it } from "vitest";
import { buildLogLines, type LogLine } from "../logLines";
import type { HistoryEntry } from "../../../services/types";

const ENTRY: HistoryEntry = {
  file: "2026-08-25T11-00-00_create.json",
  timestamp: "2026-08-25T11:00:00",
  item: "billing/create",
  duration_ms: 128,
  request: {
    method: "POST",
    url: "https://{{host}}/v1/orders",
    params: [{ key: "coupon", value: "{{coupon}}" }],
    headers: [
      { key: "Authorization", value: "Bearer {{api_token}}" },
      { key: "Content-Type", value: "application/json" },
    ],
    body: { type: "json", text: '{\n  "item": "年度订阅"\n}' },
  },
  response: {
    status: 201,
    headers: [
      { key: "content-type", value: "application/json; charset=utf-8" },
      { key: "content-length", value: "58" },
    ],
    body: { kind: "text", content_type: "application/json", text: '{"id":1024,"status":"open"}' },
  },
};

const VARS = { host: "api.example.com", coupon: "SUMMER26", api_token: "sk-live-secret" };

describe("logLines buildLogLines", () => {
  it("TC-006: 含连接元信息 + → 请求行/头/体 + ← 响应行/头/体, 变量按环境替换", () => {
    const lines = buildLogLines(ENTRY, VARS);
    const texts = lines.map((l) => l.text);
    // 元信息行 (host · TLS · 计时)
    const meta = lines.find((l) => l.dir === "meta");
    expect(meta?.text).toContain("api.example.com");
    expect(meta?.text).toContain("128");
    // 请求行: 方法 + 已解析 URL
    expect(texts).toContain("→ POST https://api.example.com/v1/orders?coupon=SUMMER26");
    // 请求头逐行
    expect(texts).toContain("→ Content-Type: application/json");
    // 请求体逐行
    expect(texts).toContain('→   "item": "年度订阅"');
    // 响应行/头/体
    expect(texts.some((t) => t.startsWith("← 201"))).toBe(true);
    expect(texts).toContain("← content-length: 58");
    expect(texts).toContain('← {"id":1024,"status":"open"}');
    // 方向归类
    const dirs = new Set(lines.map((l: LogLine) => l.dir));
    expect(dirs.has("out")).toBe(true);
    expect(dirs.has("in")).toBe(true);
  });

  it("TC-007: 保留 Authorization 等 secrets 原值 (M5-D5 不脱敏)", () => {
    const lines = buildLogLines(ENTRY, VARS);
    const auth = lines.find((l) => l.text.startsWith("→ Authorization"));
    expect(auth?.text).toBe("→ Authorization: Bearer sk-live-secret");
    expect(auth?.text).not.toContain("•");
    expect(JSON.stringify(lines)).not.toContain("脱敏");
  });

  it("响应缺失 (传输失败) 时仅请求段 + 错误行", () => {
    const failed: HistoryEntry = {
      ...ENTRY,
      response: null,
      error: { code: "TIMEOUT", message: "请求超时" },
    };
    const lines = buildLogLines(failed, VARS);
    expect(lines.some((l) => l.dir === "out")).toBe(true);
    expect(lines.some((l) => l.text.includes("TIMEOUT"))).toBe(true);
    expect(lines.filter((l) => l.dir === "in")).toHaveLength(0);
  });
});
