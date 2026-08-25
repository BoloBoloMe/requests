<script setup lang="ts">
// 侧栏 (ISSUE-02): 集合名 + 环境胶囊 + 新建/集合变量按钮 + 集合树 + git 行 (ISSUE-05)
import { useStore } from "../../stores/app";
import EnvMenu from "./EnvMenu.vue";
import VarEditor from "./VarEditor.vue";
import FolderTree from "./FolderTree.vue";
import GitRow from "./GitRow.vue";
import { ref } from "vue";

const store = useStore();
const showVars = ref(false);

function methodClass(method: string): string {
  return method.toLowerCase() === "delete" ? "del" : method.toLowerCase();
}

defineExpose({ methodClass });
</script>

<template>
  <div class="side">
    <div class="side-hd">
      <div class="name">{{ store.state.collection ?? "api-client" }}</div>
      <div class="envrow">
        <EnvMenu />
        <button class="iconbtn" title="新建请求" @click="store.createItem('')">＋</button>
        <button class="iconbtn" title="集合变量" @click="showVars = !showVars">⚙</button>
      </div>
      <div style="position: relative">
        <VarEditor v-if="showVars" @close="showVars = false" />
      </div>
    </div>
    <div class="tree">
      <FolderTree v-if="store.state.root" :node="store.state.root" :root="true" />
    </div>
    <GitRow />
  </div>
</template>
