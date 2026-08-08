<script setup lang="ts">
import {
  Activity,
  BellRing,
  Bot,
  ChartNoAxesCombined,
  ClipboardCheck,
  FileText,
  HeartPulse,
  LayoutDashboard,
  LockKeyhole,
  MessageSquareText,
  PanelsTopLeft,
  RadioTower,
  Settings,
  ShieldCheck,
  UsersRound,
  Volume2,
} from "@lucide/vue";
import { computed } from "vue";
import type { ModuleKey, PanelModule } from "../../types/activity.types";

const props = defineProps<{
  modules: PanelModule[];
  activeModule: ModuleKey;
  showCategories?: boolean;
}>();

const systemModuleKeys = new Set<ModuleKey>(["integrations", "health"]);
const categoryOrder = ["workspace", "configuration", "review", "insights", "system"] as const;
const categoryByModule: Record<ModuleKey, (typeof categoryOrder)[number]> = {
  dashboard: "workspace",
  access: "workspace",
  welcome: "configuration",
  "role-panels": "configuration",
  "creator-alerts": "configuration",
  "dev-blog": "configuration",
  "muxivo-core": "configuration",
  "ai-review": "review",
  "voice-rooms": "configuration",
  "bot-settings": "configuration",
  logs: "insights",
  "server-stats": "insights",
  integrations: "system",
  health: "system",
};
const navigationGroups = computed(() => {
  if (!props.showCategories) return [{ key: "all", modules: props.modules }];
  return categoryOrder
    .map((key) => ({ key, modules: props.modules.filter((module) => categoryByModule[module.key] === key) }))
    .filter((group) => group.modules.length > 0);
});

const icons = {
  dashboard: LayoutDashboard,
  access: ShieldCheck,
  welcome: MessageSquareText,
  "role-panels": PanelsTopLeft,
  "creator-alerts": BellRing,
  "dev-blog": FileText,
  "muxivo-core": Bot,
  "ai-review": ClipboardCheck,
  logs: Activity,
  "server-stats": ChartNoAxesCombined,
  "voice-rooms": Volume2,
  "bot-settings": Settings,
  integrations: RadioTower,
  health: HeartPulse,
};
</script>

<template>
  <aside class="panel-sidebar">
    <RouterLink class="panel-brand" to="/">
      <img class="panel-brand-logo" src="/muxivo-logo.png" alt="" />
      <strong>MUXIVO</strong>
      <span>{{ $t("panel.activity") }}</span>
    </RouterLink>

    <nav class="panel-nav" :aria-label="$t('panel.modules')">
      <template v-for="(group, index) in navigationGroups" :key="group.key">
        <div v-if="showCategories && index > 0" class="panel-nav-divider" />
        <span v-if="showCategories" class="panel-nav-group-label">{{ $t(`panel.group.${group.key}`) }}</span>
        <RouterLink
          v-for="module in group.modules"
          :key="module.key"
          :class="['panel-nav-item', { 'is-system': systemModuleKeys.has(module.key), locked: module.permission === 'disabled', active: activeModule === module.key }]"
          :to="module.permission === 'disabled' ? '/no-access' : `/panel/${module.key}`"
        >
          <component :is="module.permission === 'disabled' ? LockKeyhole : icons[module.key]" :size="17" />
          <span>{{ module.title }}</span>
        </RouterLink>
      </template>
    </nav>
  </aside>
</template>
