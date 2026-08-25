<script setup lang="ts">
// 断言编辑器 (M6 决策 1 双形态, ADR 0006):
// 结构化行 (target jmespath / op 比较符 / expect JSON 值) + Python 逃生舱 (CodeMirror 6)
// SPA 仅编辑与展示表单结构, 求值归后端 Assert (M3 D008)
import { inject } from "vue";
import type { Assertion } from "../../services/types";
import { STORE_KEY } from "../../stores/app";
import CodeEditor from "./CodeEditor.vue";

// 失败行定位 (ISSUE-05): store 可选注入 (独立组件测试无 store 时不高亮)
const store = inject(STORE_KEY, null);

const props = defineProps<{ assertions: Assertion[] }>();
const emit = defineEmits<{ "update:assertions": [Assertion[]] }>();

// op 集与后端 assertions.py OPS 对齐
const OPS = ["eq", "ne", "lt", "lte", "gt", "gte", "contains", "not_contains", "matches", "exists"];

function patch(index: number, p: Partial<Assertion>): void {
  emit(
    "update:assertions",
    props.assertions.map((a, i) => (i === index ? { ...a, ...p } : a)),
  );
}

function remove(index: number): void {
  emit(
    "update:assertions",
    props.assertions.filter((_, i) => i !== index),
  );
}

/** expect 按 JSON 解析输入 (数字/字符串/布尔/对象), 解析失败按原字符串 (与后端 DSL 宽容读法一致) */
function setExpect(index: number, raw: string): void {
  let value: unknown = raw;
  try {
    value = JSON.parse(raw);
  } catch {
    // 非 JSON 字面量按字符串
  }
  patch(index, { expect: value });
}

function expectText(a: Assertion): string {
  return a.expect === undefined ? "" : JSON.stringify(a.expect);
}

function addStructured(): void {
  emit("update:assertions", [...props.assertions, { target: "status", op: "eq", expect: 200 }]);
}

function addPython(): void {
  emit("update:assertions", [...props.assertions, { python: "assert response.status == 200" }]);
}
</script>

<template>
  <div class="alist">
    <div v-for="(a, i) in assertions" :key="i" class="row" :class="{ hl: store?.state.assertionHighlight === i }">
      <template v-if="a.python !== undefined">
        <span class="py">python</span>
        <div style="flex: 1">
          <CodeEditor
            :value="a.python"
            language="python"
            @update:value="patch(i, { python: $event })"
          />
        </div>
      </template>
      <template v-else>
        <input
          data-f="target"
          placeholder="target (status / body.<jmespath> / header.<名> / elapsed_ms)"
          :value="a.target ?? ''"
          @input="patch(i, { target: ($event.target as HTMLInputElement).value })"
        />
        <select
          data-f="op"
          :value="a.op ?? 'eq'"
          @change="patch(i, { op: ($event.target as HTMLSelectElement).value })"
        >
          <option v-for="op in OPS" :key="op" :value="op">{{ op }}</option>
        </select>
        <input
          v-if="a.op !== 'exists'"
          data-f="expect"
          placeholder="expect (JSON 值)"
          :value="expectText(a)"
          @input="setExpect(i, ($event.target as HTMLInputElement).value)"
        />
      </template>
      <span class="x" @click="remove(i)">×</span>
    </div>
    <div style="margin-top: 8px; display: flex; gap: 6px">
      <button class="btn" data-add="structured" @click="addStructured">＋ 结构化断言</button>
      <button class="btn" data-add="python" @click="addPython">＋ Python 断言</button>
    </div>
  </div>
</template>
