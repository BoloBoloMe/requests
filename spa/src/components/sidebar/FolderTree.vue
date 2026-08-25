<script setup lang="ts">
// 集合树文件夹节点 (递归): 折叠/展开, 条目渲染 (方法徽章 + 三态徽标占位)
// 拖拽排序与运行按钮分别在 ISSUE-02 TS-003 / ISSUE-05 接入
import { computed } from "vue";
import draggable from "vuedraggable";
import { useStore, type FolderNode } from "../../stores/app";
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
</script>

<template>
  <div class="folder">
    <div v-if="!root" class="f-hd" @click="store.toggleFolder(node)">
      <span class="grip">⠿</span>
      <span class="arrow" :class="{ shut: !node.open }">▾</span>
      {{ node.name }}
      <span class="count">{{ node.items.length }}</span>
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
          <div class="req" :class="{ sel: isSelected(element) }" @click="store.selectItem(element)">
            <span class="st none">·</span>
            <span class="m" :class="methodClass(element.item.method)">{{ shortMethod(element.item.method) }}</span>
            {{ element.item.name }}
            <span class="grip">⠿</span>
            <span
              class="x del"
              title="删除请求"
              @click.stop="store.deleteItem(element)"
            >×</span>
          </div>
        </template>
      </draggable>
      <FolderTree v-for="sub in node.folders" :key="sub.path" :node="sub" />
    </div>
  </div>
</template>
