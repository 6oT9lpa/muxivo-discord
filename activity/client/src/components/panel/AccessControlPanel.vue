<script setup lang="ts">
import { computed, ref } from "vue";
import { Check, Layers3, Plus, ShieldCheck, X } from "@lucide/vue";
import RevealOnScroll from "../common/RevealOnScroll.vue";
import { useActivityStore } from "../../stores/activity.store";
import { accessConfigurableModules, moduleLabel } from "../../stores/mock-data";
import type { ModuleKey, PermissionLevel } from "../../types/activity.types";

const activity = useActivityStore();
const newRoleName = ref("");
const savingRoleId = ref<number | null>(null);
const visibleModules = computed(() => accessConfigurableModules);
const visibleRoles = computed(() => activity.accessRoles);
const customRoleCount = computed(() => visibleRoles.value.filter((role) => !role.is_builtin).length);

async function addRole() {
  const name = newRoleName.value.trim();
  if (!name) return;
  await activity.createAccessRole(name);
  newRoleName.value = "";
}

async function deleteRole(roleId: number) {
  await activity.deleteAccessRole(roleId);
}

async function saveRoleAccess(roleId: number, modules: Record<ModuleKey, PermissionLevel>) {
  savingRoleId.value = roleId;
  try {
    await activity.saveAccessRoleModules(roleId, modules);
  } finally {
    savingRoleId.value = null;
  }
}

function accessValue(permission: PermissionLevel) {
  return permission === "disabled" ? "deny" : "access";
}

function setAccessValue(roleId: number, modules: Record<ModuleKey, PermissionLevel>, module: ModuleKey, value: string) {
  modules[module] = value === "access" ? "view" : "disabled";
  void saveRoleAccess(roleId, modules);
}

function enabledModuleCount(modules: Record<ModuleKey, PermissionLevel>) {
  return visibleModules.value.filter((module) => modules[module] !== "disabled").length;
}
</script>

<template>
  <RevealOnScroll tag="section" class="panel-section module-intro">
    <div class="section-heading">
      <span>{{ $t("module.access") }}</span>
      <h2>{{ $t("access.heading") }}</h2>
      <div>
        <p>{{ $t("access.description") }}</p>
      </div>
    </div>
  </RevealOnScroll>

  <section class="panel-section access-command-panel">
    <div class="access-command-copy"><span>{{ $t("access.role_catalog") }}</span><strong>{{ $t("access.role_count", { count: visibleRoles.length, custom: customRoleCount }) }}</strong><small>{{ $t("access.role_catalog_help") }}</small></div>
    <form class="access-role-toolbar" @submit.prevent="addRole">
      <input v-model="newRoleName" maxlength="48" :placeholder="$t('access.unique_role')" />
      <button class="primary-button" type="submit" :disabled="!newRoleName.trim() || activity.moduleLoading"><Plus :size="16" />{{ $t("access.add_role") }}</button>
    </form>
  </section>

  <section class="panel-section module-content-panel">
    <div class="access-role-list">
      <article v-for="role in visibleRoles" :key="role.id" class="access-role-card">
        <header>
          <div class="access-role-identity">
            <span class="access-role-icon"><ShieldCheck :size="18" /></span>
            <div><strong>{{ role.name }}</strong><span>{{ role.is_builtin ? $t("access.universal") : $t("access.custom") }} · {{ savingRoleId === role.id ? $t("access.saving") : $t("access.saved") }}</span></div>
          </div>
          <div class="access-role-summary"><Layers3 :size="15" /><strong>{{ enabledModuleCount(role.modules) }}/{{ visibleModules.length }}</strong><span>{{ $t("access.tabs_granted") }}</span></div>
          <button v-if="!role.is_builtin" class="icon-button danger" type="button" :title="$t('access.delete_role')" :aria-label="$t('access.delete_role')" @click="deleteRole(role.id)"><X :size="16" /></button>
        </header>
        <div class="access-module-grid">
          <label v-for="module in visibleModules" :key="`${role.id}-${module}`" :class="{ granted: role.modules[module] !== 'disabled' }">
            <span><Check v-if="role.modules[module] !== 'disabled'" :size="14" /><span>{{ moduleLabel(module) }}</span></span>
            <select
              :value="accessValue(role.modules[module])"
              :disabled="role.slug === 'administrator'"
              @change="setAccessValue(role.id, role.modules, module, ($event.target as HTMLSelectElement).value)"
            >
              <option value="access">{{ $t("access.allow") }}</option>
              <option value="deny">{{ $t("access.deny") }}</option>
            </select>
          </label>
        </div>
      </article>
    </div>
  </section>
</template>
