<script setup lang="ts">
// git 行 (RUN-02, M5 决策 2 单同步): ⎇ main ↑N dirty / … 同步中 / ✓ 已同步 / 失败原样输出
// 契约缺口: D010 仅 POST /git/sync, 无状态端点 — branch 静态 main, ahead 数不可得仅显 ↑
import { computed } from "vue";
import { useStore } from "../../stores/app";

const store = useStore();
const git = computed(() => store.state.git);
</script>

<template>
  <div class="git">
    <span style="font-size: 12px">⎇</span><span class="branch">main</span>
    <span v-if="git.state === 'dirty'" class="up">↑</span>
    <span v-else-if="git.state === 'syncing'" class="up spin">…</span>
    <span v-else-if="git.state === 'synced'" class="synced">✓ 已同步</span>
    <span v-else class="git-err" style="font-size: 11px; color: var(--bad); word-break: break-all">{{ git.error }}</span>
    <button
      class="btn"
      data-action="sync"
      style="margin-left: auto"
      :disabled="git.state === 'syncing'"
      @click="store.syncGit()"
    >
      {{ git.state === "syncing" ? "同步中" : "同步" }}
    </button>
  </div>
</template>
