<script setup lang="ts">
// 响应头行 (RES-01, 原型 .r-hd): 状态徽章 (ok/warn/err) + 元信息 (ms/KB/时刻) + 断言计数胶囊
import { computed } from "vue";
import type { DoneEvent } from "../../services/types";

const props = defineProps<{
  done: DoneEvent;
  /** 响应体字节数 (chunk 累积) */
  bodyBytes: number;
  /** 完成时刻 (缺省读 done.timestamp) */
  receivedAt?: Date;
}>();

const STATUS_TEXT: Record<number, string> = {
  200: "200 OK",
  201: "201 Created",
  204: "204 No Content",
  301: "301 Moved",
  302: "302 Found",
  400: "400 Bad Request",
  401: "401 Unauthorized",
  403: "403 Forbidden",
  404: "404 Not Found",
  422: "422 Unprocessable",
  500: "500 Server Error",
  502: "502 Bad Gateway",
  503: "503 Unavailable",
};

const statusClass = computed(() => {
  const s = props.done.status;
  if (typeof s !== "number") return "err"; // assert_failed / null (传输失败)
  if (s < 300) return "ok";
  if (s < 500) return "warn";
  return "err";
});

const statusText = computed(() => {
  const s = props.done.status;
  if (s === "assert_failed") return "断言失败";
  if (s === null) return props.done.error?.code ?? "传输失败";
  return STATUS_TEXT[s] ?? String(s);
});

const kb = computed(() => (props.bodyBytes / 1024).toFixed(1));

const timeText = computed(() => {
  const d = props.receivedAt ?? new Date(props.done.timestamp);
  return Number.isNaN(d.getTime()) ? "" : d.toTimeString().slice(0, 8);
});

const passed = computed(() => props.done.assertions.filter((a) => a.ok).length);
const assertClass = computed(() =>
  props.done.assertions.some((a) => !a.ok) ? "bad" : "ok",
);
</script>

<template>
  <div class="r-hd">
    <span class="status" :class="statusClass">{{ statusText }}</span>
    <span class="meta"
      ><span
        ><b>{{ done.duration_ms }}</b> ms</span
      ><span
        ><b>{{ kb }}</b> KB</span
      ><span>{{ timeText }}</span></span
    >
    <span v-if="done.assertions.length > 0" class="asserts" :class="assertClass"
      >断言 {{ passed }}/{{ done.assertions.length }} {{ assertClass === "ok" ? "✓" : "✗" }}</span
    >
  </div>
</template>
