<script setup lang="ts">
// 集合树文件夹节点 (递归): 折叠/展开, 条目渲染 (方法徽章 + runner 三态徽标)
// 拖拽排序在 ISSUE-02 TS-003 接入; 运行按钮/红字明细属 ISSUE-05 (M5 决策 3)
import { computed } from "vue";
import draggable from "vuedraggable";
import { useStore, type FolderNode, type ItemRunResult } from "../../stores/app";
import type { ItemEntry } from "../../services/types";

const props = defineProps<{ node: FolderNode; root?: boolean }>();
const store = useStore();

const shortMethod = (m: string) => (m.toUpperCase() === "DELETE" ? "DEL" : m.toUpperCase());
const methodClass = (m: string) =>
  m.toLowerCase() === "delete" ? "del" : m.toLowerCase();

function isSelected(entry: ItemEntry): boolean {
  const sel = store.state.selected;
  return sel?.slug === entry.slug && sel.folder === entry.folder;
}

// 拖拽重排 (vuedraggable): 同文件夹内排序变更 → 提交新顺序到适配层
const dragItems = computed<ItemEntry[]>({
  get: () => props.node.items,
  set: (v) => {
    props.node.items = v;
  },
});

function onDragEnd(): void {
  const slugs = dragItems.value.map((i) => i.slug);
  void store.reorderItems(props.node.path, slugs);
}

// --- runner 内联 (ISSUE-05) ---

function runResultOf(entry: ItemEntry): ItemRunResult | undefined {
  return store.state.runResults[entry.slug];
}

function stClass(entry: ItemEntry): string {
  const r = runResultOf(entry);
  if (!r) return "st none";
  return r.status === "running" ? "st run" : r.status === "passed" ? "st ok" : "st bad";
}

function stText(entry: ItemEntry): string {
  const r = runResultOf(entry);
  if (!r) return "·";
  return r.status === "running" ? "◌" : r.status === "passed" ? "✓" : "✗";
}

/** 文件夹头计数徽章: 有失败显失败数 ✗ (红), 否则有通过显通过数 ✓ (绿), 否则条目数 */
const folderBadge = computed(() => {
  if (store.state.running) return { text: "◌", cls: "count spin" };
  const results = props.node.items.map((i) => store.state.runResults[i.slug]?.status);
  const fail = results.filter((s) => s === "failed").length;
  const pass = results.filter((s) => s === "passed").length;
  if (fail > 0) return { text: `${fail}✗`, cls: "count", color: "var(--bad)" };
  if (pass > 0) return { text: `${pass}✓`, cls: "count", color: "var(--ok)" };
  return { text: String(props.node.items.length), cls: "count" };
});

/** 失败红字明细: 首条失败断言 target/why/实际值 (断言定义 target 或 python 行) */
function failNote(entry: ItemEntry): string | null {
  const r = runResultOf(entry);
  if (!r || r.status !== "failed" || !r.firstFailure) return r?.status === "failed" ? "✗ 运行失败" : null;
  const { result } = r.firstFailure;
  const target = result.assertion.target ?? "python";
  const actual = JSON.stringify(result.actual);
  return `✗ ${target} ${result.message}, 实际 ${actual}`;
}

function onRunFolder(): void {
  store.run();
}

function onFailNoteClick(entry: ItemEntry): void {
  void store.jumpToFailure(entry);
}
</script>

<template>
  <div class="folder">
    <div v-if="!root" class="f-hd" @click="store.toggleFolder(node)">
      <span class="grip">⠿</span>
      <span class="arrow" :class="{ shut: !node.open }">▾</span>
      {{ node.name }}
      <span :class="folderBadge.cls" :style="folderBadge.color ? `color:${folderBadge.color}` : ''">{{ folderBadge.text }}</span>
      <button class="run" title="运行此文件夹" @click.stop="onRunFolder">▶</button>
    </div>
    <div v-if="root || node.open" :class="root ? undefined : 'f-kids'">
      <draggable
        v-model="dragItems"
        item-key="slug"
        handle=".grip"
        :animation="120"
        @end="onDragEnd"
      >
        <template #item="{ element }">
          <div>
            <div class="req" :class="{ sel: isSelected(element) }" @click="store.selectItem(element)">
              <span :class="stClass(element)">{{ stText(element) }}</span>
              <span class="m" :class="methodClass(element.item.method)">{{ shortMethod(element.item.method) }}</span>
              {{ element.item.name }}
              <span class="grip">⠿</span>
              <span
                class="x del"
                title="删除请求"
                @click.stop="store.deleteItem(element)"
              >×</span>
            </div>
            <div
              v-if="failNote(element) && (root || node.open)"
              class="failnote"
              @click.stop="onFailNoteClick(element)"
            >
              {{ failNote(element) }}
            </div>
          </div>
        </template>
      </draggable>
      <FolderTree v-for="sub in node.folders" :key="sub.path" :node="sub" />
    </div>
  </div>
</template>
