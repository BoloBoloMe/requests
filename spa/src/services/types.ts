// services/types.ts: 领域类型 (与后端 store.py / D010 契约形状对齐)
// 术语遵循 UBIQUITOUS_LANGUAGE: 集合/请求条目/环境/集合变量/历史/执行事件流

/** 有序 kv 对 (params/headers/form-urlencoded), 可 disabled (M2 D008) */
export interface KV {
  key: string;
  value: string;
  disabled?: boolean;
  /** SPA 侧描述列 (原型 .desc), 不入后端契约 */
  desc?: string;
}

export interface MultipartPart {
  name: string;
  value?: string;
  file?: string;
  contentType?: string;
}

/** 请求体五态 (M2 D008) */
export interface Body {
  type: "none" | "json" | "text" | "form-urlencoded" | "multipart";
  text?: string;
  params?: KV[];
  parts?: MultipartPart[];
}

/** 认证 (M1 D003): basic/bearer/apikey/digest 或 null (继承由 SPA 表达) */
export type Auth = Record<string, unknown> | null;

/** 断言双形态 (M6 决策 1): 结构化 target/op/expect 或 python 逃生舱 */
export interface Assertion {
  target?: string;
  op?: string;
  expect?: unknown;
  schema?: unknown;
  python?: string;
}

/** 请求条目 (D010 条目形状; assert 键名保持 DSL 原名) */
export interface ItemData {
  name: string;
  method: string;
  url: string;
  seq?: number;
  params: KV[];
  headers: KV[];
  body: Body;
  auth: Auth;
  assert: Assertion[];
}

/** 集合列表条目: slug + 所在文件夹路径 + 领域对象 */
export interface ItemEntry {
  slug: string;
  folder: string;
  item: ItemData;
}

/** 集合配置: 集合变量 vars + 集合级默认 defaults (M2 D010) */
export interface CollectionConfigData {
  vars: Record<string, string>;
  defaults: { auth: Auth; headers: KV[] };
}

/** 环境: vars/secrets 分列, merged 为合并视图 (M2 D005/D006) */
export interface EnvironmentData {
  name: string;
  vars: Record<string, string>;
  secrets: Record<string, string>;
  merged: Record<string, string>;
}

// --- 执行事件流 (M3 D007: meta/chunk/done; run 末尾附 summary/report) ---

export interface MetaEvent {
  type: "meta";
  timestamp: string;
  item: string;
  method: string;
  resolved_url: string;
  env: string | null;
}

export interface ChunkEvent {
  type: "chunk";
  timestamp: string;
  item: string;
  index: number;
  data: string;
}

export interface AssertionResult {
  assertion: Assertion;
  ok: boolean;
  actual?: unknown;
  message: string;
}

export interface DoneEvent {
  type: "done";
  timestamp: string;
  item: string;
  /** int 状态码 / "assert_failed" / null (传输失败) */
  status: number | "assert_failed" | null;
  duration_ms: number;
  assertions: AssertionResult[];
  error?: { code: string; message: string };
}

export interface SummaryEvent {
  type: "summary";
  timestamp: string;
  total: number;
  passed: number;
  failed: number;
  items: { item: string; status: number | "assert_failed" | null; passed: boolean }[];
}

export interface ReportEvent {
  type: "report";
  format: "junit";
  content: string;
}

export type ExecuteEvent = MetaEvent | ChunkEvent | DoneEvent;
export type RunEvent = ExecuteEvent | SummaryEvent | ReportEvent;

/** POST /execute 请求体 (D010) */
export interface ExecuteRequest {
  collection: string;
  item: string;
  folder?: string;
  env?: string | null;
}

/** 历史条目 (M2 D011; /history 只读端点, 完整收发转录来源) */
export interface HistoryEntry {
  file: string;
  timestamp: string;
  item: string;
  duration_ms: number;
  request: {
    method: string;
    url: string;
    params: KV[];
    headers: KV[];
    body: { type: string; text?: string; params?: KV[]; parts?: unknown[] } | null;
  };
  response: {
    status: number;
    headers: KV[];
    body:
      | { kind: "text"; content_type: string; text: string }
      | { kind: "binary"; content_type: string; size: number };
  } | null;
  error?: { code: string; message: string };
}

/** services 适配层接口: 组件只依赖本接口, 传输可注入替换 (mock/HTTP) */
export interface ApiServices {
  listCollections(): Promise<string[]>;
  /** 列文件夹内请求条目 (folder 缺省为集合根) */
  listItems(collection: string, folder?: string): Promise<ItemEntry[]>;
  /** 列子文件夹名; HTTP 适配层契约无枚举端点时返回 [] (降级为平铺树) */
  listFolders(collection: string, folder?: string): Promise<string[]>;
  getItem(collection: string, slug: string, folder?: string): Promise<ItemData>;
  putItem(
    collection: string,
    slug: string,
    item: ItemData,
    folder?: string,
  ): Promise<ItemData>;
  deleteItem(collection: string, slug: string, folder?: string): Promise<void>;
  getCollectionConfig(collection: string): Promise<CollectionConfigData>;
  putCollectionConfig(
    collection: string,
    config: CollectionConfigData,
  ): Promise<CollectionConfigData>;
  /** 环境名列表; HTTP 适配层无枚举端点时降级为 [激活环境] */
  listEnvironments(): Promise<string[]>;
  getEnvironment(name: string): Promise<EnvironmentData>;
  putEnvironment(
    name: string,
    vars: Record<string, string>,
  ): Promise<EnvironmentData>;
  getActiveEnvironment(): Promise<string | null>;
  setActiveEnvironment(name: string | null): Promise<void>;
  /** 执行事件流 (SSE/NDJSON 消费已被适配层统一为异步迭代) */
  execute(req: ExecuteRequest): AsyncIterable<ExecuteEvent>;
  runCollection(collection: string, env?: string | null): AsyncIterable<RunEvent>;
  listHistory(collection: string, slug: string, folder?: string): Promise<HistoryEntry[]>;
  gitSync(): Promise<void>;
}
