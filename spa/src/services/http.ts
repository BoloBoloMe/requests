// services/http.ts: HTTP 适配层 (D010 REST CRUD + RPC, D013 无版本前缀)
// 已知后端契约缺口 (不改后端, 降级处理): 无环境枚举端点 (降级 [激活环境]),
// 无文件夹枚举端点 (降级 [] 平铺树); execute/run 流式在 ISSUE-04/05 接入.
import { ApiError, request, requestJson, type HttpDeps } from "../api/http";
import { eventsFromResponse } from "../api/sse";
import type {
  ApiServices,
  CollectionConfigData,
  EnvironmentData,
  ExecuteEvent,
  ExecuteRequest,
  HistoryEntry,
  ItemData,
  RunEvent,
} from "./types";

function folderQuery(folder?: string): string {
  return folder ? `?folder=${encodeURIComponent(folder)}` : "";
}

export function createHttpServices(deps: HttpDeps = {}): ApiServices {
  const get = <T>(path: string) => requestJson<T>(path, {}, deps);
  const put = <T>(path: string, json: unknown) =>
    requestJson<T>(path, { method: "PUT", json }, deps);
  const post = <T>(path: string, json?: unknown) =>
    requestJson<T>(path, { method: "POST", json }, deps);
  const del = (path: string) => requestJson<void>(path, { method: "DELETE" }, deps);

  const services: ApiServices = {
    listCollections: async () => (await get<{ collections: string[] }>("/collections")).collections,
    listItems: async (collection, folder) =>
      (
        await get<{ items: ({ slug: string } & ItemData)[] }>(
          `/collections/${encodeURIComponent(collection)}/items${folderQuery(folder)}`,
        )
      ).items.map(({ slug, ...item }) => ({ slug, folder: folder ?? "", item: item as ItemData })),
    // 契约缺口: 后端无文件夹枚举端点 → 平铺树降级
    listFolders: async () => [],
    getItem: (collection, slug, folder) =>
      get<ItemData>(
        `/collections/${encodeURIComponent(collection)}/items/${encodeURIComponent(slug)}${folderQuery(folder)}`,
      ),
    putItem: (collection, slug, item, folder) =>
      put<ItemData>(
        `/collections/${encodeURIComponent(collection)}/items/${encodeURIComponent(slug)}${folderQuery(folder)}`,
        item,
      ),
    deleteItem: (collection, slug, folder) =>
      del(
        `/collections/${encodeURIComponent(collection)}/items/${encodeURIComponent(slug)}${folderQuery(folder)}`,
      ),
    getCollectionConfig: (collection) =>
      get<CollectionConfigData>(`/collections/${encodeURIComponent(collection)}/collection`),
    putCollectionConfig: (collection, config) =>
      put<CollectionConfigData>(
        `/collections/${encodeURIComponent(collection)}/collection`,
        config,
      ),
    // 契约缺口: 后端无环境枚举端点 → 降级 [激活环境]
    listEnvironments: async () => {
      try {
        const payload = await get<{ environments: string[] }>("/environments");
        return payload.environments;
      } catch (exc) {
        if (exc instanceof ApiError && exc.status === 404) {
          const active = await services.getActiveEnvironment();
          return active ? [active] : [];
        }
        throw exc;
      }
    },
    getEnvironment: (name) => get<EnvironmentData>(`/environments/${encodeURIComponent(name)}`),
    putEnvironment: (name, vars) =>
      put<EnvironmentData>(`/environments/${encodeURIComponent(name)}`, { vars }),
    getActiveEnvironment: async () =>
      (await get<{ active_environment: string | null }>("/state")).active_environment,
    setActiveEnvironment: async (name) => {
      await put("/state", { active_environment: name });
    },
    // POST /execute + Accept 协商 SSE (M3 D007); token 走 header (M3 D004)
    execute(req: ExecuteRequest): AsyncIterable<ExecuteEvent> {
      return (async function* () {
        const resp = await request(
          "/execute",
          {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
            body: JSON.stringify(req),
          },
          deps,
        );
        if (!resp.ok) {
          let detail = resp.statusText;
          try {
            detail = JSON.stringify(((await resp.json()) as { detail?: unknown }).detail ?? resp.statusText);
          } catch {
            // 保留 statusText
          }
          throw new ApiError(resp.status, `执行失败 ${resp.status}: ${detail}`);
        }
        yield* eventsFromResponse(resp);
      })();
    },
    runCollection: (): AsyncIterable<RunEvent> => {
      throw new Error("run 流式接线属 ISSUE-05");
    },
    listHistory: (collection, slug, folder) =>
      get<{ entries: HistoryEntry[] }>(
        `/history/${encodeURIComponent(collection)}/${encodeURIComponent(slug)}${folderQuery(folder)}`,
      ).then((p) => p.entries),
    gitSync: async () => {
      await post("/git/sync");
    },
  };
  return services;
}
