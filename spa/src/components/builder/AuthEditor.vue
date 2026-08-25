<script setup lang="ts">
// Auth 编辑器 (M5 决策 3): 继承集合默认 / 覆盖 (Basic/Bearer/API Key/Digest) / 无认证
// 模型 (与后端 Engine 一致, M1 D003): null=继承, {type:"none"}=无认证, {type,...}=覆盖
import { computed } from "vue";
import type { Auth } from "../../services/types";

const props = defineProps<{ auth: Auth }>();
const emit = defineEmits<{ "update:auth": [Auth] }>();

type Mode = "inherit" | "override" | "none";

const mode = computed<Mode>(() => {
  if (props.auth === null) return "inherit";
  const type = props.auth?.type;
  if (type === "none" || type === undefined || type === null) return "none";
  return "override";
});

const overrideType = computed(() =>
  mode.value === "override" ? String(props.auth?.type ?? "bearer") : "bearer",
);

function setMode(next: Mode): void {
  if (next === "inherit") emit("update:auth", null);
  else if (next === "none") emit("update:auth", { type: "none" });
  else emit("update:auth", { type: overrideType.value });
}

function setType(type: string): void {
  // 切换类型: 丢弃旧类型字段, 保留 type (字段含义随类型变, M1 D003)
  emit("update:auth", { type });
}

function setField(field: string, value: string): void {
  emit("update:auth", { ...(props.auth ?? {}), type: overrideType.value, [field]: value });
}

const field = (name: string) => String((props.auth as Record<string, unknown> | null)?.[name] ?? "");
</script>

<template>
  <div class="authbox">
    <div class="opt">
      <input
        type="radio"
        name="auth"
        value="inherit"
        :checked="mode === 'inherit'"
        @change="setMode('inherit')"
      />
      <span>继承集合默认</span>
    </div>
    <div class="inh">Authorization 等默认值取自集合配置 (M2 D010)</div>
    <div class="opt">
      <input
        type="radio"
        name="auth"
        value="override"
        :checked="mode === 'override'"
        @change="setMode('override')"
      />
      <span>覆盖:</span>
      <select
        v-if="mode === 'override'"
        class="authtype"
        :value="overrideType"
        @change="setType(($event.target as HTMLSelectElement).value)"
      >
        <option value="basic">Basic</option>
        <option value="bearer">Bearer</option>
        <option value="apikey">API Key</option>
        <option value="digest">Digest</option>
      </select>
      <template v-else>Basic / Bearer / API Key / Digest</template>
    </div>
    <template v-if="mode === 'override'">
      <div v-if="overrideType === 'basic' || overrideType === 'digest'" class="opt">
        <input
          data-field="username"
          placeholder="username"
          :value="field('username')"
          @input="setField('username', ($event.target as HTMLInputElement).value)"
        />
        <input
          data-field="password"
          type="password"
          placeholder="password"
          :value="field('password')"
          @input="setField('password', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <div v-else-if="overrideType === 'bearer'" class="opt">
        <input
          data-field="token"
          placeholder="token (可用 {{var}})"
          :value="field('token')"
          @input="setField('token', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <div v-else-if="overrideType === 'apikey'" class="opt">
        <input
          data-field="key"
          placeholder="key (头/参数名)"
          :value="field('key')"
          @input="setField('key', ($event.target as HTMLInputElement).value)"
        />
        <input
          data-field="value"
          placeholder="value"
          :value="field('value')"
          @input="setField('value', ($event.target as HTMLInputElement).value)"
        />
        <select
          data-field="in"
          :value="field('in') || 'header'"
          @change="setField('in', ($event.target as HTMLSelectElement).value)"
        >
          <option value="header">header</option>
          <option value="query">query</option>
        </select>
      </div>
    </template>
    <div class="opt">
      <input
        type="radio"
        name="auth"
        value="none"
        :checked="mode === 'none'"
        @change="setMode('none')"
      />
      <span>无认证</span>
    </div>
  </div>
</template>
