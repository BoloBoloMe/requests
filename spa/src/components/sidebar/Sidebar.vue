<script setup lang="ts">
// 侧栏 (ISSUE-02): 集合菜单 (切换/新建集合) + 环境胶囊 + 新建/集合变量按钮 + 集合树 + git 行 (ISSUE-05)
import { useStore } from "../../stores/app";
import CollectionMenu from "./CollectionMenu.vue";
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
      <div class="collwrap">
        <CollectionMenu />
      </div>
      <div class="envrow">
        <EnvMenu />
        <button
          class="iconbtn"
          title="新建请求"
          :disabled="!store.state.collection"
          @click="store.createItem('')"
        >
          ＋
        </button>
        <!-- 集合级运行 (RUN-01): 根集合无树头行, 入口放侧栏头; 运行中禁用 -->
        <button
          class="iconbtn"
          title="运行集合"
          :disabled="!store.state.collection || store.state.running"
          @click="store.run()"
        >
          ▶
        </button>
        <button class="iconbtn" title="集合变量" @click="showVars = !showVars">⚙</button>
      </div>
      <div style="position: relative">
        <VarEditor v-if="showVars" @close="showVars = false" />
      </div>
    </div>
    <div class="tree">
      <FolderTree v-if="store.state.root" :node="store.state.root" :root="true" />
      <div v-else-if="store.state.collections.length === 0" class="empty-hint">
        暂无集合, 点上方集合名新建
      </div>
    </div>
    <GitRow />
  </div>
</template>
