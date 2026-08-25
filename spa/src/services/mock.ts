// services/mock.ts: 内存 mock 适配层 (组件测试与 vite dev 演示用)
// 数据形状与 D010 契约一致; execute/run 事件流可预置, 供 ISSUE-04/05 消费测试.
import type {
  ApiServices,
  CollectionConfigData,
  EnvironmentData,
  ExecuteEvent,
  ExecuteRequest,
  HistoryEntry,
  ItemData,
  ItemEntry,
  RunEvent,
} from "./types";

export interface MockFolder {
  name: string;
  subfolders: MockFolder[];
  items: Record<string, ItemData>;
}

export interface MockSeed {
  collections: Record<string, { config?: Partial<CollectionConfigData>; tree: MockFolder }>;
  environments?: Record<string, { vars?: Record<string, string>; secrets?: Record<string, string> }>;
  activeEnvironment?: string | null;
  executeEvents?: ExecuteEvent[];
  runEvents?: RunEvent[];
  history?: HistoryEntry[];
}

function folder(name: string, children?: Partial<MockFolder>): MockFolder {
  return { name, subfolders: [], items: {}, ...children };
}

/** 原型变体 B 预置数据: 集合 billing, 文件夹 订单/发票 */
export function presetBilling(): MockSeed {
  return {
    collections: {
      billing: {
        config: { vars: { host: "api.example.com", coupon: "SUMMER26" } },
        tree: folder("billing", {
          subfolders: [
            folder("订单", {
              items: {
                list: {
                  name: "订单列表",
                  method: "GET",
                  url: "https://{{host}}/v1/orders?status=open&limit=20",
                  seq: 0,
                  params: [
                    { key: "status", value: "open" },
                    { key: "limit", value: "20" },
                  ],
                  headers: [{ key: "Accept", value: "application/json" }],
                  body: { type: "none" },
                  auth: null,
                  assert: [{ target: "status", op: "eq", expect: 200 }],
                },
                create: {
                  name: "创建订单",
                  method: "POST",
                  url: "https://{{host}}/v1/orders",
                  seq: 1,
                  params: [],
                  headers: [{ key: "Content-Type", value: "application/json" }],
                  body: { type: "json", text: '{\n  "item": "年度订阅"\n}' },
                  auth: null,
                  assert: [],
                },
                cancel: {
                  name: "取消订单",
                  method: "DELETE",
                  url: "https://{{host}}/v1/orders/1024",
                  seq: 2,
                  params: [],
                  headers: [],
                  body: { type: "none" },
                  auth: null,
                  assert: [],
                },
              },
            }),
            folder("发票", {
              items: {
                invoice: {
                  name: "发票详情",
                  method: "GET",
                  url: "https://{{host}}/v1/invoices/INV-2026-0813",
                  seq: 0,
                  params: [],
                  headers: [],
                  body: { type: "none" },
                  auth: null,
                  assert: [],
                },
              },
            }),
          ],
        }),
      },
    },
    environments: {
      prod: { vars: { host: "api.example.com" } },
      staging: { vars: { host: "api.staging.example.com" } },
    },
    activeEnvironment: "prod",
  };
}

function findFolder(root: MockFolder, path: string): MockFolder {
  if (!path) return root;
  let node = root;
  for (const part of path.split("/")) {
    const next = node.subfolders.find((f) => f.name === part);
    if (!next) throw new Error(`文件夹不存在: ${path}`);
    node = next;
  }
  return node;
}

async function* toStream<T>(events: T[]): AsyncIterable<T> {
  for (const e of events) yield e;
}

/** 内存 mock: ApiServices 完整实现; 调用可被测试经 vi.spyOn 观察. */
export function createMockServices(seed: MockSeed): ApiServices {
  const envs = seed.environments ?? {};
  let activeEnv = seed.activeEnvironment ?? null;

  function collectionTree(collection: string) {
    const c = seed.collections[collection];
    if (!c) throw new Error(`集合不存在: ${collection}`);
    return c;
  }

  return {
    async listCollections() {
      return Object.keys(seed.collections).sort();
    },
    async listItems(collection: string, folderPath = ""): Promise<ItemEntry[]> {
      const node = findFolder(collectionTree(collection).tree, folderPath);
      return Object.entries(node.items)
        .map(([slug, item]) => ({ slug, folder: folderPath, item: structuredClone(item) }))
        .sort((a, b) => (a.item.seq ?? 0) - (b.item.seq ?? 0) || a.slug.localeCompare(b.slug));
    },
    async listFolders(collection: string, folderPath = ""): Promise<string[]> {
      const node = findFolder(collectionTree(collection).tree, folderPath);
      return node.subfolders.map((f) => f.name).sort();
    },
    async getItem(collection: string, slug: string, folderPath = ""): Promise<ItemData> {
      const node = findFolder(collectionTree(collection).tree, folderPath);
      const item = node.items[slug];
      if (!item) throw new Error(`请求条目不存在: ${collection}/${folderPath}/${slug}`);
      return structuredClone(item);
    },
    async putItem(collection: string, slug: string, item: ItemData, folderPath = ""): Promise<ItemData> {
      const node = findFolder(collectionTree(collection).tree, folderPath);
      node.items[slug] = structuredClone(item);
      return structuredClone(item);
    },
    async deleteItem(collection: string, slug: string, folderPath = ""): Promise<void> {
      const node = findFolder(collectionTree(collection).tree, folderPath);
      if (!(slug in node.items)) throw new Error(`请求条目不存在: ${slug}`);
      delete node.items[slug];
    },
    async getCollectionConfig(collection: string): Promise<CollectionConfigData> {
      const c = collectionTree(collection);
      return {
        vars: { ...(c.config?.vars ?? {}) },
        defaults: {
          auth: c.config?.defaults?.auth ?? null,
          headers: c.config?.defaults?.headers ?? [],
        },
      };
    },
    async putCollectionConfig(collection: string, config: CollectionConfigData) {
      // 隐式建集合: 与后端 write_collection (mkdir parents) 对齐, 不存在即建空树
      if (!seed.collections[collection]) {
        seed.collections[collection] = { tree: folder(collection) };
      }
      seed.collections[collection].config = structuredClone(config);
      return structuredClone(config);
    },
    async listEnvironments() {
      return Object.keys(envs).sort();
    },
    async getEnvironment(name: string): Promise<EnvironmentData> {
      const e = envs[name];
      if (!e) throw new Error(`环境不存在: ${name}`);
      const vars = { ...(e.vars ?? {}) };
      const secrets = { ...(e.secrets ?? {}) };
      return { name, vars, secrets, merged: { ...vars, ...secrets } };
    },
    async putEnvironment(name: string, vars: Record<string, string>) {
      envs[name] = { ...(envs[name] ?? {}), vars: { ...vars } };
      return this.getEnvironment(name);
    },
    async getActiveEnvironment() {
      return activeEnv;
    },
    async setActiveEnvironment(name: string | null) {
      activeEnv = name;
    },
    execute(_req: ExecuteRequest) {
      return toStream(seed.executeEvents ?? []);
    },
    runCollection(_collection: string, _env?: string | null) {
      return toStream(seed.runEvents ?? []);
    },
    async listHistory() {
      return seed.history ?? [];
    },
    async gitSync() {
      // mock 恒成功; 失败场景由测试注入抛错的 spy
    },
  };
}
