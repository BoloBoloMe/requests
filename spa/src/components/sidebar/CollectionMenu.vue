<script setup lang="ts">
// 集合菜单: 集合名可点击弹下拉, 列出全部集合供切换; 内联「新建集合」表单
// (隐式建集合: store.createCollection 经适配层写默认配置, 后端自动建目录)
import { ref } from "vue";
import { useStore } from "../../stores/app";

const store = useStore();
const open = ref(false);
const creating = ref(false);
const newName = ref("");
const error = ref("");

async function choose(name: string): Promise<void> {
  open.value = false;
  await store.selectCollection(name);
}

function startCreate(): void {
  creating.value = true;
  error.value = "";
}

async function submitCreate(): Promise<void> {
  const name = newName.value.trim();
  if (!name) return;
  error.value = "";
  try {
    await store.createCollection(name);
    creating.value = false;
    newName.value = "";
    open.value = false;
  } catch (exc) {
    // 名称非法/后端 422: 原样展示错误信息, 不静默
    error.value = exc instanceof Error ? exc.message : String(exc);
  }
}
</script>

<template>
  <div class="name" @click="open = !open">
    <span>{{ store.state.collection ?? "api-client" }}</span>
    <span class="caret">▾</span>
  </div>
  <div v-if="open" class="envmenu collmenu">
    <div
      v-for="name in store.state.collections"
      :key="name"
      :data-collection="name"
      @click="choose(name)"
    >
      {{ name }}
      <span v-if="name === store.state.collection" style="margin-left: auto">✓</span>
    </div>
    <div v-if="!creating" data-new-collection @click="startCreate">＋ 新建集合</div>
    <div v-else class="collform" @click.stop>
      <input v-model="newName" placeholder="集合名" @keydown.enter="submitCreate" />
      <button class="btn primary" @click="submitCreate">创建</button>
    </div>
    <div v-if="error" class="collerror">{{ error }}</div>
  </div>
</template>
