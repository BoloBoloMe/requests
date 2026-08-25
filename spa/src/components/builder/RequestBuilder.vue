<script setup lang="ts">
// 请求构建器组装 (ISSUE-03, M5 决策 3): URL 栏 + 五 tab (Params/Headers/Body/Auth/断言)
// 数据源为 store 草稿 (选中条目联动 ISSUE-02), 写回经 services 适配层 (saveDraft)
import { computed, watch } from "vue";
import { useStore } from "../../stores/app";
import type { Body } from "../../services/types";
import UrlBar from "./UrlBar.vue";
import KvEditor from "./KvEditor.vue";
import AuthEditor from "./AuthEditor.vue";
import AssertionEditor from "./AssertionEditor.vue";
import CodeEditor from "./CodeEditor.vue";

const store = useStore();
const draft = computed(() => store.state.draft);

const TABS = ["Params", "Headers", "Body", "Auth", "断言"] as const;

/** tab 计数胶囊: Params/Headers 计行数, 断言计条数; 0 不显示 (原型 .tabs .n) */
function tabCount(tab: string): number {
  const d = draft.value;
  if (!d) return 0;
  if (tab === "Params") return d.params.length;
  if (tab === "Headers") return d.headers.length;
  if (tab === "断言") return d.assert.length;
  return 0;
}

const BODY_TYPES: Body["type"][] = ["none", "json", "text"];

function setBodyType(type: Body["type"]): void {
  if (!draft.value) return;
  draft.value.body = { ...draft.value.body, type };
}

function setBodyText(text: string): void {
  if (!draft.value) return;
  draft.value.body = { ...draft.value.body, type: draft.value.body.type, text };
}

function send(): void {
  // 经 store 消费 /execute SSE (ISSUE-04 接线); 发送中态由 store 维护
  void store.send();
}

// 切换选中条目: 重置 tab 到 Params, 避免草稿与 tab 错位
watch(
  () => store.state.selected,
  () => {
    store.state.builderTab = "Params";
  },
);
</script>

<template>
  <div class="reqpane col">
    <template v-if="draft">
      <UrlBar
        :url="draft.url"
        :method="draft.method"
        @update:url="draft.url = $event"
        @update:method="draft.method = $event"
        @send="send"
      />
      <div class="tabs">
        <span
          v-for="tab in TABS"
          :key="tab"
          :class="{ on: store.state.builderTab === tab }"
          @click="store.state.builderTab = tab"
          >{{ tab }}<b v-if="tabCount(tab) > 0" class="n">{{ tabCount(tab) }}</b></span
        >
      </div>
      <div class="kvwrap">
        <KvEditor
          v-if="store.state.builderTab === 'Params'"
          :rows="draft.params"
          @update:rows="draft.params = $event"
        />
        <KvEditor
          v-else-if="store.state.builderTab === 'Headers'"
          :rows="draft.headers"
          @update:rows="draft.headers = $event"
        />
        <template v-else-if="store.state.builderTab === 'Body'">
          <div style="margin-bottom: 8px; display: flex; gap: 6px; align-items: center">
            <span style="font-size: 11.5px; color: var(--dim)">类型</span>
            <select
              class="bodytype"
              :value="draft.body.type"
              @change="setBodyType(($event.target as HTMLSelectElement).value as Body['type'])"
            >
              <option v-for="t in BODY_TYPES" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div v-if="draft.body.type === 'none'" style="color: var(--dim); font-size: 12px">
            此请求无请求体
          </div>
          <CodeEditor
            v-else
            :value="draft.body.text ?? ''"
            :language="draft.body.type === 'json' ? 'json' : 'text'"
            @update:value="setBodyText"
          />
        </template>
        <AuthEditor
          v-else-if="store.state.builderTab === 'Auth'"
          :auth="draft.auth"
          @update:auth="draft.auth = $event"
        />
        <AssertionEditor
          v-else-if="store.state.builderTab === '断言'"
          :assertions="draft.assert"
          @update:assertions="draft.assert = $event"
        />
      </div>
      <div style="padding: 8px 16px; display: flex; gap: 8px">
        <button class="btn primary" data-action="save" @click="store.saveDraft()">保存</button>
      </div>
    </template>
    <div v-else style="padding: 24px; color: var(--dim); font-size: 12.5px">
      在左侧集合树选择请求条目
    </div>
  </div>
</template>
