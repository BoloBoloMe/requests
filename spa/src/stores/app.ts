// stores/app.ts: 全局应用状态 (单页, 无路由; M5 决策 1 各面同屏)
// 经 createAppStore(services) 构造注入, 组件 useStore() 取用; 测试注入 mock 服务.
import { reactive, type InjectionKey } from "vue";
import { inject } from "vue";
import type { ApiServices } from "../services/types";
import type { ItemEntry } from "../services/types";

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
  });

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

  async function selectCollection(name: string): Promise<void> {
    state.collection = name;
    state.root = await buildFolder(name, "", name);
    const config = await services.getCollectionConfig(name);
    state.collectionVars = config.vars;
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
    reloadTree,
    toggleFolder,
    selectItem,
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
