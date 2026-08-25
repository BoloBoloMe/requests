<script setup lang="ts">
// 集合变量编辑器 (M5 决策 3): kv 表加行/删行/改, 保存经适配层写 _collection.yaml
import { ref } from "vue";
import { useServices } from "../../services";
import { useStore } from "../../stores/app";

const emit = defineEmits<{ close: [] }>();
const store = useStore();
const services = useServices();

interface Row {
  key: string;
  value: string;
}

// 编辑态: 从 store 集合变量拷贝 (kv 值按字符串, M2 D002)
const rows = ref<Row[]>(
  Object.entries(store.state.collectionVars).map(([key, value]) => ({ key, value })),
);
const addKey = ref("");
const addValue = ref("");

function commitAddRow(): void {
  if (!addKey.value) return;
  rows.value.push({ key: addKey.value, value: addValue.value });
  addKey.value = "";
  addValue.value = "";
}

function removeRow(index: number): void {
  rows.value.splice(index, 1);
}

async function save(): Promise<void> {
  if (!store.state.collection) return;
  // 读出完整配置再整体写回 (defaults 不动, D010 PUT 即整体替换)
  const config = await services.getCollectionConfig(store.state.collection);
  config.vars = Object.fromEntries(
    rows.value.filter((r) => r.key).map((r) => [r.key, r.value]),
  );
  await services.putCollectionConfig(store.state.collection, config);
  store.state.collectionVars = config.vars;
  emit("close");
}
</script>

<template>
  <div class="varmodal">
    <div style="font-weight: 600; font-size: 12.5px; margin-bottom: 6px">集合变量</div>
    <div v-for="(row, i) in rows" :key="i" class="kv">
      <input v-model="row.key" placeholder="key" />
      <input v-model="row.value" placeholder="value" />
      <span class="x" @click="removeRow(i)">×</span>
    </div>
    <div class="kv add">
      <input
        v-model="addKey"
        placeholder="key"
        @keydown.enter="commitAddRow"
      />
      <input v-model="addValue" placeholder="value" @keydown.enter="commitAddRow" />
      <span class="x">＋</span>
    </div>
    <div style="display: flex; gap: 6px; margin-top: 8px; justify-content: flex-end">
      <button class="btn" @click="emit('close')">取消</button>
      <button class="btn primary" @click="save">保存</button>
    </div>
  </div>
</template>
