// stores/app.ts: 全局应用状态 (单页, 无路由; M5 决策 1 各面同屏)
// 经 createAppStore(services) 构造注入, 组件 useStore() 取用; 测试注入 mock 服务.
import { reactive, type InjectionKey } from "vue";
import { inject } from "vue";
import type {
  ApiServices,
  AssertionResult,
  DoneEvent,
  HistoryEntry,
  MetaEvent,
} from "../services/types";
import type { ItemData, ItemEntry } from "../services/types";

/** 集合树文件夹节点: path 为相对集合根的路径 ("" = 根) */
export interface FolderNode {
  name: string;
  path: string;
  open: boolean;
  folders: FolderNode[];
  items: ItemEntry[];
}

/** 当前选中的请求条目定位 */
export interface SelectedItem {
  collection: string;
  slug: string;
  folder: string;
}

/** 树条目运行三态徽标 (RUN-01): running ◌ / passed ✓ / failed ✗; 缺省 · 未运行 */
export interface ItemRunResult {
  status: "running" | "passed" | "failed";
  /** 首条失败断言 (红字明细与跳断言定位) */
  firstFailure?: { index: number; result: AssertionResult };
}

export interface AppState {
  collections: string[];
  /** 当前集合名 */
  collection: string | null;
  /** 集合树根 (name = 集合名, path = "") */
  root: FolderNode | null;
  /** 环境名列表与激活环境 (M2 D007 激活状态在后端) */
  envs: string[];
  activeEnv: string | null;
  /** 激活环境的合并变量视图 (secrets 已并入), 供 URL 解析预览 (ISSUE-03) */
  envVars: Record<string, string>;
  /** 集合变量 (M2 D010) */
  collectionVars: Record<string, string>;
  selected: SelectedItem | null;
  /** 请求构建器草稿: 选中条目的编辑副本 (写回走 saveDraft) */
  draft: ItemData | null;
  /** 发送中的展示态 (ISSUE-03; ISSUE-04 接 SSE) */
  sending: boolean;
  /** 构建器激活 tab (runner 失败跳断言用, ISSUE-05) */
  builderTab: string;
  /** 断言高亮定位 (失败红字跳转, ISSUE-05) */
  assertionHighlight: number | null;
  /** 响应面板数据 (ISSUE-04): SSE 事件累积 + 历史转录 */
  response: {
    meta: MetaEvent | null;
    bodyText: string;
    bodyBytes: number;
    done: DoneEvent | null;
    history: HistoryEntry | null;
  } | null;
  /** 响应面板激活 tab */
  responseTab: string;
  /** runner 内联: 条目 slug → 运行结果 (ISSUE-05, 事件 item 为 collection/slug) */
  runResults: Record<string, ItemRunResult>;
  /** 批量运行进行中 (并发保护: 重复触发被忽略) */
  running: boolean;
  /** 当前运行的收尾 promise (测试与 UI 等待用) */
  runDone: Promise<void> | null;
  /** git 行状态机 (RUN-02, M5-D2 单同步; D009 冲突即停原样输出) */
  git: { state: "dirty" | "syncing" | "synced" | "failed"; error: string | null };
}

export function createAppStore(services: ApiServices) {
  const state = reactive<AppState>({
    collections: [],
    collection: null,
    root: null,
    envs: [],
    activeEnv: null,
    envVars: {},
    collectionVars: {},
    selected: null,
    draft: null,
    sending: false,
    builderTab: "Params",
    assertionHighlight: null,
    response: null,
    responseTab: "Body",
    runResults: {},
    running: false,
    runDone: null,
    git: { state: "dirty", error: null },
  });

  /** run 事件 item 为 item_ref (collection/slug), 树徽标按 slug 定位 */
  function slugOf(itemRef: string): string {
    return itemRef.split("/").pop() ?? itemRef;
  }

  async function buildFolder(collection: string, path: string, name: string): Promise<FolderNode> {
    const [items, subNames] = await Promise.all([
      services.listItems(collection, path),
      services.listFolders(collection, path),
    ]);
    const folders: FolderNode[] = [];
    for (const sub of subNames) {
      folders.push(await buildFolder(collection, path ? `${path}/${sub}` : sub, sub));
    }
    return { name, path, open: true, folders, items };
  }

  /** 首屏装载: 集合列表 + 激活环境 + 默认集合树 */
  async function init(): Promise<void> {
    state.collections = await services.listCollections();
    state.activeEnv = await services.getActiveEnvironment();
    state.envs = await services.listEnvironments();
    if (state.activeEnv) await loadEnvVars(state.activeEnv);
    if (state.collections.length > 0) await selectCollection(state.collections[0]);
  }

  async function loadEnvVars(name: string): Promise<void> {
    const env = await services.getEnvironment(name);
    state.envVars = env.merged;
  }

  /** 集合绑定状态清零 (切/新建集合防旧集合残留): 选中条目/草稿/响应面板/运行徽标/
   *  断言高亮/进行中标记; 全局状态 (collections/envs/activeEnv/envVars/git) 不动. */
  function clearCollectionState(): void {
    state.selected = null;
    state.draft = null;
    state.response = null;
    state.responseTab = "Body";
    state.runResults = {};
    state.assertionHighlight = null;
    state.builderTab = "Params";
    state.sending = false;
    state.running = false;
    state.runDone = null;
  }

  async function selectCollection(name: string): Promise<void> {
    state.collection = name;
    clearCollectionState();
    state.root = await buildFolder(name, "", name);
    const config = await services.getCollectionConfig(name);
    state.collectionVars = config.vars;
  }

  /** 新建集合: 写默认配置即隐式建集合 (后端 write_collection 自动建目录);
   *  成功后刷新集合列表并选中. 名称非法/后端 422 时错误抛给 UI 展示. */
  async function createCollection(name: string): Promise<void> {
    await services.putCollectionConfig(name, {
      vars: {},
      defaults: { auth: null, headers: [] },
    });
    state.collections = await services.listCollections();
    await selectCollection(name);
  }

  async function reloadTree(): Promise<void> {
    if (!state.collection) return;
    const openPaths = new Set<string>();
    const walk = (n: FolderNode) => {
      if (n.open) openPaths.add(n.path);
      n.folders.forEach(walk);
    };
    if (state.root) walk(state.root);
    state.root = await buildFolder(state.collection, "", state.collection);
    const restore = (n: FolderNode) => {
      n.open = openPaths.size === 0 || openPaths.has(n.path);
      n.folders.forEach(restore);
    };
    restore(state.root);
  }

  function toggleFolder(node: FolderNode): void {
    node.open = !node.open;
  }

  function selectItem(entry: ItemEntry): void {
    if (!state.collection) return;
    state.selected = { collection: state.collection, slug: entry.slug, folder: entry.folder };
  }

  /** 装载选中条目到草稿 (构建器数据源); 换条目时清空响应面板 */
  async function loadDraft(): Promise<void> {
    if (!state.selected) {
      state.draft = null;
      return;
    }
    const { collection, slug, folder } = state.selected;
    state.draft = await services.getItem(collection, slug, folder);
    state.response = null;
    state.responseTab = "Body";
  }

  /** 草稿写回适配层 (PUT 即 upsert, D010); 先取纯快照避免 reactive 代理过不了传输/克隆边界 */
  async function saveDraft(): Promise<void> {
    if (!state.selected || !state.draft) return;
    const { collection, slug, folder } = state.selected;
    const snapshot = JSON.parse(JSON.stringify(state.draft)) as ItemData;
    await services.putItem(collection, slug, snapshot, folder);
  }

  /** 文件夹/集合批量运行 (RUN-01): 消费 run 事件流驱动树徽标与红字明细 */
  function run(): void {
    if (!state.collection || state.running) return;
    const collection = state.collection;
    state.running = true;
    state.runResults = {};
    state.runDone = (async () => {
      try {
        for await (const event of services.runCollection(collection, state.activeEnv)) {
          if (event.type === "meta") {
            state.runResults[slugOf(event.item)] = { status: "running" };
          } else if (event.type === "done") {
            const failedIndex = event.assertions.findIndex((a) => !a.ok);
            state.runResults[slugOf(event.item)] = {
              // 三态口径: 仅 HTTP 码落地且断言全过计 passed (与后端 summary 一致)
              status: typeof event.status === "number" ? "passed" : "failed",
              ...(failedIndex >= 0
                ? { firstFailure: { index: failedIndex, result: event.assertions[failedIndex] } }
                : {}),
            };
          }
          // summary/report 事件不驱动树 UI (报告输出物不落盘, M3)
        }
      } finally {
        state.running = false;
      }
    })();
  }

  /** 失败红字跳转: 选中条目 + 装载草稿 + 断言 tab + 定位失败行 (RUN-01/ISSUE-03 联动) */
  async function jumpToFailure(entry: ItemEntry): Promise<void> {
    const result = state.runResults[entry.slug];
    selectItem(entry);
    await loadDraft();
    state.builderTab = "断言";
    state.assertionHighlight = result?.firstFailure?.index ?? null;
  }

  /** git 单同步 (RUN-02): 一键 pull+push 合并式; 失败原样展示后端输出 (D009) */
  async function syncGit(): Promise<void> {
    if (state.git.state === "syncing") return;
    state.git.state = "syncing";
    state.git.error = null;
    try {
      await services.gitSync();
      state.git.state = "synced";
    } catch (exc) {
      state.git.state = "failed";
      state.git.error = exc instanceof Error ? exc.message : String(exc);
    }
  }

  /** 发送当前条目: 消费 /execute SSE 事件流累积响应, done 后拉历史转录 (RES-01..05) */
  async function send(): Promise<void> {
    if (!state.selected || state.sending) return;
    const { collection, slug, folder } = state.selected;
    state.sending = true;
    state.response = { meta: null, bodyText: "", bodyBytes: 0, done: null, history: null };
    state.responseTab = "Body";
    const encoder = new TextEncoder();
    try {
      for await (const event of services.execute({ collection, item: slug, folder })) {
        if (!state.response) break;
        if (event.type === "meta") state.response.meta = event;
        else if (event.type === "chunk") {
          state.response.bodyText += event.data;
          state.response.bodyBytes += encoder.encode(event.data).length;
        } else if (event.type === "done") state.response.done = event;
      }
      // Headers/日志 tab 数据源: 历史完整收发转录 (M2 D011; 后端按时间升序, 最新取末条)
      const entries = await services.listHistory(collection, slug, folder);
      if (state.response) state.response.history = entries[entries.length - 1] ?? null;
    } finally {
      state.sending = false;
    }
  }

  /** 环境切换 (M2 D007): 写后端激活状态 + 刷新变量视图 */
  async function setActiveEnv(name: string | null): Promise<void> {
    await services.setActiveEnvironment(name);
    state.activeEnv = name;
    state.envVars = name ? (await services.getEnvironment(name)).merged : {};
  }

  /** 新建请求条目 (进指定文件夹, 缺省集合根); slug 由名称派生去重 */
  async function createItem(folder: string): Promise<ItemEntry> {
    if (!state.collection || !state.root) throw new Error("未选择集合");
    const node = findFolder(state.root, folder);
    const existing = new Set(node.items.map((i) => i.slug));
    let slug = "new-request";
    for (let i = 1; existing.has(slug); i += 1) slug = `new-request-${i}`;
    const item = {
      name: "未命名请求",
      method: "GET",
      url: "https://{{host}}/",
      seq: node.items.length,
      params: [],
      headers: [],
      body: { type: "none" as const },
      auth: null,
      assert: [],
    };
    await services.putItem(state.collection, slug, item, folder);
    await reloadTree();
    const entry: ItemEntry = { slug, folder, item };
    selectItem(entry);
    return entry;
  }

  async function deleteItem(entry: { slug: string; folder: string }): Promise<void> {
    if (!state.collection) return;
    await services.deleteItem(state.collection, entry.slug, entry.folder);
    if (state.selected?.slug === entry.slug && state.selected.folder === entry.folder) {
      state.selected = null;
    }
    await reloadTree();
  }

  /** 重命名 = 同文件夹内换 slug (文件改名, M2 D003) */
  async function renameItem(entry: { slug: string; folder: string }, newSlug: string): Promise<void> {
    if (!state.collection || !newSlug || newSlug === entry.slug) return;
    const item = await services.getItem(state.collection, entry.slug, entry.folder);
    await services.putItem(state.collection, newSlug, item, entry.folder);
    await services.deleteItem(state.collection, entry.slug, entry.folder);
    if (state.selected?.slug === entry.slug) {
      state.selected = { collection: state.collection, slug: newSlug, folder: entry.folder };
    }
    await reloadTree();
  }

  /** 同文件夹内拖拽重排: 按新顺序重写 seq (M2 D003) 并持久化 */
  async function reorderItems(folder: string, slugsInOrder: string[]): Promise<void> {
    if (!state.collection) return;
    for (let i = 0; i < slugsInOrder.length; i += 1) {
      const item = await services.getItem(state.collection, slugsInOrder[i], folder);
      if ((item.seq ?? 0) !== i) {
        item.seq = i;
        await services.putItem(state.collection, slugsInOrder[i], item, folder);
      }
    }
    await reloadTree();
  }

  function findFolder(node: FolderNode, path: string): FolderNode {
    if (node.path === path) return node;
    for (const f of node.folders) {
      if (path === f.path || path.startsWith(`${f.path}/`)) return findFolder(f, path);
    }
    throw new Error(`文件夹不存在: ${path}`);
  }

  return {
    state,
    init,
    selectCollection,
    createCollection,
    reloadTree,
    toggleFolder,
    selectItem,
    loadDraft,
    saveDraft,
    send,
    run,
    jumpToFailure,
    syncGit,
    setActiveEnv,
    createItem,
    deleteItem,
    renameItem,
    reorderItems,
    findFolder,
  };
}

export type AppStore = ReturnType<typeof createAppStore>;

export const STORE_KEY: InjectionKey<AppStore> = Symbol("apic-store");

export function useStore(): AppStore {
  const store = inject(STORE_KEY);
  if (!store) throw new Error("store 未注入: 组件树外或测试未提供");
  return store;
}
