<script setup lang="ts">
// CodeEditor: CodeMirror 6 封装 (direction-a Q1-3 选型; v-model 双向绑定 + 语言高亮)
// EditorView 由组件生命周期持有, 避免 tab 切换重挂丢状态 (外部值变更做最小替换)
import { Compartment, EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{ value: string; language?: "json" | "python" | "text"; readOnly?: boolean }>(),
  { language: "text", readOnly: false },
);
const emit = defineEmits<{ "update:value": [string] }>();

const host = ref<HTMLElement>();
let view: EditorView | null = null;
const languageCompartment = new Compartment();

function languageExtension() {
  if (props.language === "json") return json();
  if (props.language === "python") return python();
  return [];
}

defineOptions({ name: "CodeEditor" });

onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.value,
      extensions: [
        lineNumbers(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        languageCompartment.of(languageExtension()),
        EditorView.editable.of(!props.readOnly),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit("update:value", update.state.doc.toString());
        }),
        EditorView.theme({
          "&": { maxHeight: "260px", fontFamily: "var(--mono)" },
          ".cm-scroller": { overflow: "auto" },
        }),
      ],
    }),
  });
});

// 外部值变更 (如切换条目) → 全量替换文档, 避免与本地编辑回环
watch(
  () => props.value,
  (next) => {
    if (view && next !== view.state.doc.toString()) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: next } });
    }
  },
);

watch(
  () => props.language,
  () => {
    view?.dispatch({ effects: languageCompartment.reconfigure(languageExtension()) });
  },
);

onBeforeUnmount(() => {
  view?.destroy();
  view = null;
});
</script>

<template>
  <div ref="host" class="codeeditor"></div>
</template>
