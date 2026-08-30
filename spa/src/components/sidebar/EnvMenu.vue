<script setup lang="ts">
// 环境胶囊 + 下拉 (M5 决策 1): 点击弹下拉, 切换即全局换环境 (写适配层激活状态)
// G2: 下拉尾部加「管理环境」入口, 弹 EnvEditor 管理弹层 (CRUD+激活切换)
import { ref } from "vue";
import { useStore } from "../../stores/app";
import EnvEditor from "./EnvEditor.vue";

const store = useStore();
const open = ref(false);
const managing = ref(false);

// 环境指示点颜色: 按名散列取调色板 (激活语义色仅限状态表达, M5 决策 4)
const DOT_COLORS = ["var(--ok)", "var(--warn)", "var(--accent)", "#7b4a94"];
function dotColor(name: string | null): string {
  if (!name) return "var(--dim)";
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) % 997;
  return DOT_COLORS[h % DOT_COLORS.length];
}

async function choose(name: string): Promise<void> {
  open.value = false;
  await store.setActiveEnv(name);
}

function startManage(): void {
  open.value = false;
  managing.value = true;
}
</script>

<template>
  <div class="envwrap">
    <div class="env" @click="open = !open">
      <span class="dot" :style="{ background: dotColor(store.state.activeEnv) }"></span>
      <span>{{ store.state.activeEnv ?? "无环境" }}</span>
      <span class="caret">▾</span>
    </div>
    <div v-if="open" class="envmenu">
      <div
        v-for="name in store.state.envs"
        :key="name"
        :data-env="name"
        @click="choose(name)"
      >
        <span class="dot" :style="{ background: dotColor(name) }"></span>
        {{ name }}
        <span v-if="name === store.state.activeEnv" style="margin-left: auto">✓</span>
      </div>
      <div data-manage-env @click="startManage">⚙ 管理环境…</div>
    </div>
    <EnvEditor v-if="managing" @close="managing = false" />
  </div>
</template>
