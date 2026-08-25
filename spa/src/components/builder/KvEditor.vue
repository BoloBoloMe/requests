<script setup lang="ts">
// kv 行编辑器 (Params/Headers 共用, M5 决策 3):
// 无边框输入悬停显框 + 描述列, 末行回车增行, 行可删 (×); disabled 行置灰
import { ref } from "vue";
import type { KV } from "../../services/types";

const props = defineProps<{ rows: KV[] }>();
const emit = defineEmits<{ "update:rows": [KV[]] }>();

const addKey = ref("");
const addValue = ref("");

function patchRow(index: number, patch: Partial<KV>): void {
  const next = props.rows.map((r, i) => (i === index ? { ...r, ...patch } : r));
  emit("update:rows", next);
}

function removeRow(index: number): void {
  emit(
    "update:rows",
    props.rows.filter((_, i) => i !== index),
  );
}

function commitAddRow(): void {
  if (!addKey.value && !addValue.value) return;
  emit("update:rows", [...props.rows, { key: addKey.value, value: addValue.value }]);
  addKey.value = "";
  addValue.value = "";
}
</script>

<template>
  <div>
    <div v-for="(row, i) in rows" :key="i" class="kv" :style="row.disabled ? 'opacity:.5' : ''">
      <input
        :value="row.key"
        placeholder="key"
        @input="patchRow(i, { key: ($event.target as HTMLInputElement).value })"
      />
      <input
        :value="row.value"
        placeholder="value"
        @input="patchRow(i, { value: ($event.target as HTMLInputElement).value })"
        @keydown.enter="commitAddRow"
      />
      <span class="desc">
        <input
          :value="row.desc ?? ''"
          placeholder="描述"
          @input="patchRow(i, { desc: ($event.target as HTMLInputElement).value })"
        />
      </span>
      <span class="x" @click="removeRow(i)">×</span>
    </div>
    <div class="kv add">
      <input v-model="addKey" placeholder="key" @keydown.enter="commitAddRow" />
      <input v-model="addValue" placeholder="value" @keydown.enter="commitAddRow" />
      <span class="desc"></span>
      <span class="x" @click="commitAddRow">＋</span>
    </div>
  </div>
</template>
