<script setup lang="ts">
// JsonTree: JSON 折叠树 (RES-02, 原型 .json/.fold/.ln)
// 行号列 + 折叠记号 (▾/▸, 状态按路径键记录) + 键/字符串/数字/布尔着色 (k/s/n/b)
import { computed, reactive } from "vue";

const props = defineProps<{ data: unknown }>();

interface Token {
  cls?: "k" | "s" | "n" | "b";
  text: string;
}
interface Line {
  depth: number;
  tokens: Token[];
  /** 可折叠节点的路径键与展开态 */
  fold?: { path: string; open: boolean };
}

/** 折叠状态: 路径键集合 (组件实例内持有, 切换数据不串态由调用方 key 控制) */
const collapsed = reactive(new Set<string>());

function scalarTokens(value: unknown): Token[] {
  if (typeof value === "string") return [{ cls: "s", text: JSON.stringify(value) }];
  if (typeof value === "number") return [{ cls: "n", text: String(value) }];
  if (typeof value === "boolean" || value === null) return [{ cls: "b", text: String(value) }];
  return [{ text: String(value) }];
}

function buildLines(value: unknown, path: string, depth: number, lines: Line[]): void {
  if (value === null || typeof value !== "object") {
    lines.push({ depth, tokens: scalarTokens(value) });
    return;
  }
  const isArray = Array.isArray(value);
  const entries: [string, unknown][] = isArray
    ? (value as unknown[]).map((v, i) => [String(i), v])
    : Object.entries(value as Record<string, unknown>);
  const openBrace = isArray ? "[" : "{";
  const closeBrace = isArray ? "]" : "}";
  const open = !collapsed.has(path);

  if (!open) {
    lines.push({
      depth,
      fold: { path, open: false },
      tokens: [
        { text: `${openBrace} ` },
        { cls: "b", text: "…" },
        { text: ` ${closeBrace}` },
      ],
    });
    return;
  }
  lines.push({ depth, fold: { path, open: true }, tokens: [{ text: openBrace }] });
  entries.forEach(([key, val], i) => {
    const childPath = path ? `${path}.${key}` : key;
    const comma = i < entries.length - 1 ? "," : "";
    const keyToken: Token | null = isArray ? null : { cls: "k", text: `${JSON.stringify(key)}: ` };
    if (val !== null && typeof val === "object") {
      const childLines: Line[] = [];
      buildLines(val, childPath, 0, childLines);
      // 首行并入键行, 后续行按 depth+1 缩进
      const [first, ...rest] = childLines;
      lines.push({
        depth: depth + 1,
        fold: first.fold,
        tokens: [...(keyToken ? [keyToken] : []), ...first.tokens, { text: comma }],
      });
      for (const l of rest) lines.push({ ...l, depth: l.depth + depth + 1 });
    } else {
      lines.push({
        depth: depth + 1,
        tokens: [...(keyToken ? [keyToken] : []), ...scalarTokens(val), { text: comma }],
      });
    }
  });
  lines.push({ depth, tokens: [{ text: closeBrace }] });
}

const lines = computed<Line[]>(() => {
  const out: Line[] = [];
  buildLines(props.data, "", 0, out);
  return out;
});

function toggle(path: string): void {
  if (collapsed.has(path)) collapsed.delete(path);
  else collapsed.add(path);
}
</script>

<template>
  <div class="json">
    <div v-for="(line, i) in lines" :key="i" :style="{ paddingLeft: `${line.depth * 14}px` }">
      <span class="ln">{{ i + 1 }}</span>
      <span
        v-if="line.fold"
        class="fold"
        :data-path="line.fold.path"
        @click="toggle(line.fold.path)"
        >{{ line.fold.open ? "▾" : "▸" }}</span
      >
      <span v-else class="fold" style="visibility: hidden">·</span>
      <span v-for="(tok, j) in line.tokens" :key="j" :class="tok.cls">{{ tok.text }}</span>
    </div>
  </div>
</template>
