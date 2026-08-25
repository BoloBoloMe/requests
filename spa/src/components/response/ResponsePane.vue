<script setup lang="ts">
// 响应查看器 (ISSUE-04, 原型变体 B .resp): 头行 + 三 tab (Body/Headers/日志)
// 数据源: store.send() 累积的 SSE 事件 (meta/chunk/done) + 历史转录 (Headers/日志)
import { computed } from "vue";
import { useStore } from "../../stores/app";
import JsonTree from "./JsonTree.vue";
import ResponseHeader from "./ResponseHeader.vue";
import { buildLogLines } from "./logLines";

const store = useStore();
const resp = computed(() => store.state.response);

const TABS = ["Body", "Headers", "日志"] as const;

/** Body: 尝试 JSON 解析 → 树; 失败降级裸文本 (RES-02) */
const bodyJson = computed(() => {
  const text = resp.value?.bodyText ?? "";
  if (!text) return { ok: false as const, value: null };
  try {
    return { ok: true as const, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false as const, value: null };
  }
});

const headers = computed(() => resp.value?.history?.response?.headers ?? []);

/** 日志转录: 变量按当前环境解析 (集合 vars < 环境 merged, M2 D012); 不脱敏 (M5 决策 5) */
const logLines = computed(() => {
  const history = resp.value?.history;
  if (!history) return [];
  return buildLogLines(history, { ...store.state.collectionVars, ...store.state.envVars });
});

const showTabs = computed(() => resp.value?.done != null);
</script>

<template>
  <div class="resp">
    <div v-if="store.state.sending" class="r-hd">
      <span class="dim" style="font-size: 12px"><span class="spin">◌</span> 发送中…</span>
    </div>
    <ResponseHeader
      v-else-if="resp?.done"
      :done="resp.done"
      :body-bytes="resp.bodyBytes"
    />
    <div v-else class="r-hd">
      <span class="dim" style="font-size: 12px">尚未发送 — 点「发送」或从树上 ▶ 运行</span>
    </div>
    <div v-if="showTabs" class="tabs">
      <span
        v-for="tab in TABS"
        :key="tab"
        :class="{ on: store.state.responseTab === tab }"
        @click="store.state.responseTab = tab"
        >{{ tab }}</span
      >
    </div>
    <div v-if="showTabs" class="r-body">
      <template v-if="store.state.responseTab === 'Body'">
        <JsonTree v-if="bodyJson.ok" :key="resp?.done?.timestamp" :data="bodyJson.value" />
        <pre v-else class="rawtext">{{ resp?.bodyText || "(空响应体)" }}</pre>
      </template>
      <div v-else-if="store.state.responseTab === 'Headers'" class="json">
        <div v-for="(h, i) in headers" :key="i">
          <span class="k">{{ h.key }}</span
          >: {{ h.value }}
        </div>
        <div v-if="headers.length === 0" class="dim">(无历史转录, 响应头不可得)</div>
      </div>
      <div v-else class="json">
        <div
          v-for="(line, i) in logLines"
          :key="i"
          :class="line.dir === 'out' ? 'log-out' : line.dir === 'in' ? 'log-in' : 'log-meta'"
        >
          {{ line.text }}
        </div>
        <div v-if="logLines.length === 0" class="dim">(无历史转录)</div>
      </div>
    </div>
  </div>
</template>
