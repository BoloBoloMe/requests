// api/http.ts: 共享 HTTP client (ISSUE-01, M3 D004)
// token 由后端托管页注入 (window.__APIC_TOKEN__, CSP 下经 meta[apic-token] 兜底);
// 全部请求携带 X-Auth-Token 头; 缺失/空 token 抛可诊断错误, 不静默失败.

export type TokenProvider = () => string | null;

export interface HttpDeps {
  fetchFn?: typeof fetch;
  tokenProvider?: TokenProvider;
  baseUrl?: string;
}

/** token 缺失/空时的可诊断错误: 未托管场景 (直接 vite dev / dist 被静态服务器托管) 的降级行为. */
export class MissingTokenError extends Error {
  constructor() {
    super(
      "缺少 API token: 页面未经 apic serve 托管或 token 注入失败, 请经 `apic serve` 打开 (M3 D004)",
    );
    this.name = "MissingTokenError";
  }
}

/** 值占位符: 未替换即视为未注入 (与后端 web/static.py 约定一致). */
export const TOKEN_PLACEHOLDER = "__APIC_TOKEN_VALUE__";

/** 默认 token 来源: window.__APIC_TOKEN__ 优先, meta[apic-token] 兜底 (CSP 拦内联脚本场景). */
export function windowTokenProvider(): string | null {
  const fromWindow = (window as unknown as Record<string, unknown>).__APIC_TOKEN__;
  const fromMeta = document
    .querySelector('meta[name="apic-token"]')
    ?.getAttribute("content");
  const token =
    typeof fromWindow === "string" && fromWindow ? fromWindow : fromMeta || null;
  if (!token || token === TOKEN_PLACEHOLDER) return null;
  return token;
}

/** 公开请求函数: fetch 与 token provider 均可注入替换 (测试接缝). */
export async function request(
  path: string,
  init: RequestInit = {},
  deps: HttpDeps = {},
): Promise<Response> {
  const fetchFn = deps.fetchFn ?? fetch;
  const tokenProvider = deps.tokenProvider ?? windowTokenProvider;
  const token = tokenProvider();
  if (!token) throw new MissingTokenError();
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
    "X-Auth-Token": token,
  };
  return fetchFn((deps.baseUrl ?? "") + path, { ...init, headers });
}

/** JSON 请求便捷封装: 自动 JSON 编解码; 非 2xx 抛携带状态码与后端 detail 的错误. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function requestJson<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
  deps: HttpDeps = {},
): Promise<T> {
  const { json, ...rest } = init;
  const finalInit: RequestInit = { ...rest };
  if (json !== undefined) {
    finalInit.body = JSON.stringify(json);
    finalInit.headers = {
      "Content-Type": "application/json",
      ...(rest.headers as Record<string, string> | undefined),
    };
  }
  const resp = await request(path, finalInit, deps);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const payload: unknown = await resp.json();
      const raw = (payload as { detail?: unknown }).detail;
      detail = typeof raw === "string" ? raw : JSON.stringify(raw ?? payload);
    } catch {
      // 非 JSON 错误体: 保留 statusText
    }
    throw new ApiError(resp.status, `请求失败 ${resp.status}: ${detail}`);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
