<script setup lang="ts">
// 环境管理弹层 (G2): 列表/新建/改名/编辑 vars+secrets/删除/设为激活
// 数据仍落 environments/*.yaml (+ .secrets.yaml, gitignored), 经适配层 CRUD.
import { ref, watch } from "vue";
import { useServices } from "../../services";
import { useStore } from "../../stores/app";
import type { EnvironmentData } from "../../services/types";

const emit = defineEmits<{ close: [] }>();
const store = useStore();
const services = useServices();

interface Row {
  key: string;
  value: string;
}

const selected = ref<string | null>(store.state.activeEnv ?? store.state.envs[0] ?? null);
const envName = ref("");
const varRows = ref<Row[]>([]);
const secretRows = ref<Row[]>([]);
const creating = ref(false);
const newName = ref("");
const newVarKey = ref("");
const newVarValue = ref("");
const newSecretKey = ref("");
const newSecretValue = ref("");
const error = ref("");
const busy = ref(false);

function rowsOf(vars: Record<string, string>): Row[] {
  return Object.entries(vars).map(([key, value]) => ({ key, value }));
}

function toMap(rows: Row[]): Record<string, string> {
  return Object.fromEntries(rows.filter((r) => r.key).map((r) => [r.key, r.value]));
}

/** 装载环境到编辑区 (vars/secrets 拷贝为行) */
async function loadEditor(name: string): Promise<void> {
  const env: EnvironmentData = await services.getEnvironment(name);
  envName.value = name;
  varRows.value = rowsOf(env.vars);
  secretRows.value = rowsOf(env.secrets);
  error.value = "";
}

watch(
  selected,
  (name) => {
    if (name) void loadEditor(name);
  },
  { immediate: true },
);

function addVarRow(): void {
  if (!newVarKey.value) return;
  varRows.value.push({ key: newVarKey.value, value: newVarValue.value });
  newVarKey.value = "";
  newVarValue.value = "";
}

function addSecretRow(): void {
  if (!newSecretKey.value) return;
  secretRows.value.push({ key: newSecretKey.value, value: newSecretValue.value });
  newSecretKey.value = "";
  newSecretValue.value = "";
}

async function submitCreate(): Promise<void> {
  const name = newName.value.trim();
  if (!name || busy.value) return;
  error.value = "";
  busy.value = true;
  try {
    await store.createEnvironment(name);
    newName.value = "";
    creating.value = false;
    selected.value = name;
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}

function cancelCreate(): void {
  creating.value = false;
  newName.value = "";
  error.value = "";
}

/** 保存: vars/secrets 整体替换写; 名称变动即改名 (写新删旧, 激活态联动) */
async function save(): Promise<void> {
  if (!selected.value || busy.value) return;
  const target = envName.value.trim();
  if (!target) {
    error.value = "环境名不能为空";
    return;
  }
  error.value = "";
  busy.value = true;
  try {
    await store.saveEnvironment(
      selected.value,
      toMap(varRows.value),
      toMap(secretRows.value),
      target,
    );
    selected.value = target;
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}

/** 删除当前环境 (激活态若是它则后端归空, 本地同步) */
async function remove(): Promise<void> {
  if (!selected.value || busy.value) return;
  error.value = "";
  busy.value = true;
  try {
    await store.removeEnvironment(selected.value);
    selected.value = store.state.envs[0] ?? null;
    if (!selected.value) {
      envName.value = "";
      varRows.value = [];
      secretRows.value = [];
    }
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}

/** 设为激活 (写后端激活状态 + 刷新变量视图) */
async function activate(): Promise<void> {
  if (!selected.value || busy.value) return;
  error.value = "";
  busy.value = true;
  try {
    await store.setActiveEnv(selected.value);
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="enveditor" @click.stop>
    <div class="ee-head">
      <span>环境管理</span>
      <span class="x" data-env-close @click="emit('close')">×</span>
    </div>
    <div class="ee-body">
      <div class="ee-list">
        <div
          v-for="name in store.state.envs"
          :key="name"
          :data-env-item="name"
          :class="{ on: name === selected }"
          @click="selected = name"
        >
          <span class="ee-name">{{ name }}</span>
          <span v-if="name === store.state.activeEnv" class="check">✓</span>
        </div>
        <div v-if="!creating" data-env-new @click="creating = true">＋ 新建环境</div>
        <div v-else class="ee-form">
          <input
            v-model="newName"
            placeholder="环境名"
            data-env-new-name
            @keydown.enter="submitCreate"
            @keydown.esc="cancelCreate"
          />
          <button class="btn primary" data-env-new-submit :disabled="busy" @click="submitCreate">
            建
          </button>
          <button class="btn" data-env-new-cancel @click="cancelCreate">×</button>
        </div>
        <div v-if="error && creating" class="ee-error">{{ error }}</div>
      </div>
      <div class="ee-edit">
        <template v-if="selected">
          <div class="ee-field">
            <label>名称</label>
            <input v-model="envName" data-env-name placeholder="环境名" />
          </div>
          <div class="ee-sec">变量 <span class="ee-hint">environments/*.yaml</span></div>
          <div class="ee-kv">
            <div v-for="(row, i) in varRows" :key="'v' + i" class="kv">
              <input v-model="row.key" placeholder="key" />
              <input v-model="row.value" placeholder="value" />
              <span class="x" @click="varRows.splice(i, 1)">×</span>
            </div>
            <div class="kv add">
              <input
                v-model="newVarKey"
                placeholder="key"
                data-env-var-key
                @keydown.enter="addVarRow"
              />
              <input v-model="newVarValue" placeholder="value" @keydown.enter="addVarRow" />
              <span class="x">＋</span>
            </div>
          </div>
          <div class="ee-sec">Secrets <span class="ee-hint">gitignored, 合并优先级最高</span></div>
          <div class="ee-kv">
            <div v-for="(row, i) in secretRows" :key="'s' + i" class="kv">
              <input v-model="row.key" placeholder="key" />
              <input v-model="row.value" placeholder="value" />
              <span class="x" @click="secretRows.splice(i, 1)">×</span>
            </div>
            <div class="kv add">
              <input
                v-model="newSecretKey"
                placeholder="key"
                data-env-secret-key
                @keydown.enter="addSecretRow"
              />
              <input v-model="newSecretValue" placeholder="value" @keydown.enter="addSecretRow" />
              <span class="x">＋</span>
            </div>
          </div>
        </template>
        <div v-else class="ee-empty">左侧选择或新建环境</div>
        <div v-if="error && !creating" class="ee-error" data-env-error>{{ error }}</div>
      </div>
    </div>
    <div class="ee-foot">
      <button class="btn" data-env-activate :disabled="!selected || busy" @click="activate">
        设为激活
      </button>
      <button class="btn danger" data-env-delete :disabled="!selected || busy" @click="remove">
        删除
      </button>
      <span style="flex: 1"></span>
      <button class="btn" data-env-cancel @click="emit('close')">取消</button>
      <button class="btn primary" data-env-save :disabled="!selected || busy" @click="save">
        保存
      </button>
    </div>
  </div>
</template>
