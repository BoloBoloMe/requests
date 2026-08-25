// components/response/logLines.ts: 日志转录行构建器 (纯函数, RES-04)
// 一次请求的完整收发转录: 连接元信息 + → 请求行/头/体 + ← 响应行/头/原始体;
// 变量按当前环境解析 (复用 ISSUE-03 解析器), 不脱敏 secrets (M5 决策 5).
import type { HistoryEntry } from "../../services/types";
import { resolvePreview } from "../../util/vars";

export interface LogLine {
  /** out=请求 (→), in=响应 (←), meta=连接元信息 */
  dir: "out" | "in" | "meta";
  text: string;
}

/** query 串渲染: params 未 disabled 行拼接到 URL (变量先解析再编码) */
function urlWithParams(
  url: string,
  params: { key: string; value: string; disabled?: boolean }[],
  resolve: (text: string) => string,
): string {
  const qs = params
    .filter((p) => !p.disabled && p.key)
    .map((p) => `${encodeURIComponent(resolve(p.key))}=${encodeURIComponent(resolve(p.value))}`)
    .join("&");
  if (!qs) return resolve(url);
  return resolve(url) + (url.includes("?") ? "&" : "?") + qs;
}

/** 由历史条目构建转录行; vars 为当前环境解析表 (集合 vars < 环境 merged) */
export function buildLogLines(entry: HistoryEntry, vars: Record<string, string>): LogLine[] {
  const resolve = (text: string) => resolvePreview(text, vars);
  const lines: LogLine[] = [];
  const req = entry.request;

  let host = "";
  try {
    host = new URL(resolve(req.url)).host;
  } catch {
    host = "(URL 未解析)";
  }
  lines.push({ dir: "meta", text: `# ${host} · 共 ${entry.duration_ms}ms` });

  lines.push({ dir: "out", text: `→ ${req.method} ${urlWithParams(req.url, req.params, resolve)}` });
  for (const h of req.headers) {
    if (h.disabled) continue;
    lines.push({ dir: "out", text: `→ ${h.key}: ${resolve(h.value)}` });
  }
  if (req.body && req.body.type !== "none" && req.body.text) {
    for (const l of resolve(req.body.text).split("\n")) lines.push({ dir: "out", text: `→ ${l}` });
  }

  if (entry.response) {
    lines.push({ dir: "in", text: `← ${entry.response.status}` });
    for (const h of entry.response.headers) {
      lines.push({ dir: "in", text: `← ${h.key}: ${h.value}` });
    }
    lines.push({ dir: "in", text: "← " });
    if (entry.response.body.kind === "text") {
      for (const l of entry.response.body.text.split("\n")) lines.push({ dir: "in", text: `← ${l}` });
    } else {
      lines.push({ dir: "in", text: `← <二进制 ${entry.response.body.size} 字节>` });
    }
  } else if (entry.error) {
    lines.push({ dir: "meta", text: `# 传输失败 ${entry.error.code}: ${entry.error.message}` });
  }
  return lines;
}
