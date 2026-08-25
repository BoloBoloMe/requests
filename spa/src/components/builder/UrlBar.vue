<script setup lang="ts">
// URL 栏 (M5 决策 3): 方法徽章着色 + {{var}} 高亮 + 解析预览行 (随环境即时变)
// 编辑: 聚焦切换为输入框, 失焦回高亮展示态
import { computed, ref } from "vue";
import { useStore } from "../../stores/app";
import { resolvePreview, splitVars } from "../../util/vars";

const props = defineProps<{ url: string; method: string }>();
const emit = defineEmits<{ "update:url": [string]; "update:method": [string]; send: [] }>();

const store = useStore();
const editing = ref(false);
const draft = ref("");

const METHODS = ["GET", "POST", "PUT", "DELETE"];

const segments = computed(() => splitVars(props.url));

// 变量优先级 (M2 D012): 集合 vars < 环境 merged vars (secrets 已并入)
const previewVars = computed(() => ({ ...store.state.collectionVars, ...store.state.envVars }));
const preview = computed(() => resolvePreview(props.url, previewVars.value));

function startEdit(): void {
  draft.value = props.url;
  editing.value = true;
}

function commitEdit(): void {
  editing.value = false;
  if (draft.value !== props.url) emit("update:url", draft.value);
}

const methodClass = computed(() =>
  props.method.toLowerCase() === "delete" ? "del" : props.method.toLowerCase(),
);
</script>

<template>
  <div class="urlbar">
    <select
      class="msel"
      :class="methodClass"
      :value="method"
      @change="emit('update:method', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="m in METHODS" :key="m" :value="m" :selected="m === method">{{ m }}</option>
    </select>
    <input
      v-if="editing"
      class="urlin"
      v-model="draft"
      autofocus
      @blur="commitEdit"
      @keydown.enter="commitEdit"
    />
    <div v-else class="urlin" @click="startEdit">
      <template v-for="(seg, i) in segments" :key="i">
        <span v-if="seg.isVar" class="var">{{ seg.text }}</span>
        <template v-else>{{ seg.text }}</template>
      </template>
    </div>
    <button class="btn primary send" @click="emit('send')">发送</button>
  </div>
  <div class="resolved">→ {{ preview }}</div>
</template>
