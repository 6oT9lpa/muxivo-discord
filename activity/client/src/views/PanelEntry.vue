<script setup lang="ts">
import { X } from "@lucide/vue";
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AccessControlPanel from "../components/panel/AccessControlPanel.vue";
import AiModeratorPanel from "../components/panel/AiModeratorPanel.vue";
import AiModerationReviewQueue from "../components/panel/AiModerationReviewQueue.vue";
import BotSettingsPanel from "../components/panel/BotSettingsPanel.vue";
import CreatorAlertsPanel from "../components/panel/CreatorAlertsPanel.vue";
import DashboardPanel from "../components/panel/DashboardPanel.vue";
import DevBlogPanel from "../components/panel/DevBlogPanel.vue";
import HealthStatusPanel from "../components/panel/HealthStatusPanel.vue";
import IntegrationsPanel from "../components/panel/IntegrationsPanel.vue";
import LogsPanel from "../components/panel/LogsPanel.vue";
import PanelSidebar from "../components/panel/PanelSidebar.vue";
import PanelTopbar from "../components/panel/PanelTopbar.vue";
import RolePanelsPanel from "../components/panel/RolePanelsPanel.vue";
import ServerStatsPanel from "../components/panel/ServerStatsPanel.vue";
import VoiceRoomsPanel from "../components/panel/VoiceRoomsPanel.vue";
import WelcomeModulePanel from "../components/panel/WelcomeModulePanel.vue";
import LoadingDots from "../components/common/LoadingDots.vue";
import NoAccessState from "../components/common/NoAccessState.vue";
import { useActivityStore } from "../stores/activity.store";
import { t } from "../i18n";
import { buildModules, moduleDescription, moduleLabel, moduleOrder } from "../stores/mock-data";
import type { ModuleKey, PanelModule } from "../types/activity.types";

const route = useRoute();
const router = useRouter();
const activity = useActivityStore();

const previewSystemModules = computed<PanelModule[]>(() => (["integrations", "health"] as const).map((key) => ({
  key,
  title: moduleLabel(key),
  eyebrow: t("panel.preview"),
  description: moduleDescription(key),
  permission: "view",
  status: key === "health" ? "online" : "configured",
})));
const modules = computed(() =>
  activity.session
    ? [
      ...buildModules(activity.session).filter((module) => module.permission !== "disabled"),
      ...(activity.aiModerator?.review_access ? [{
        key: "ai-review" as const,
        title: moduleLabel("ai-review"),
        eyebrow: t("ai.review.eyebrow"),
        description: t("module.ai-review.description"),
        permission: "view" as const,
        status: "configured" as const,
      }] : []),
    ]
    : previewSystemModules.value,
);
const activeModule = computed<ModuleKey>(() => {
  const raw = route.params.module;
  const candidate = Array.isArray(raw) ? raw[0] : raw;
  return moduleOrder.includes(candidate as ModuleKey) || candidate === "ai-review" ? (candidate as ModuleKey) : "dashboard";
});

const activeTitle = computed(() => moduleLabel(activeModule.value));
const subtitle = computed(() =>
  activity.session
    ? t("panel.connected_as", { name: activity.displayName })
    : t("panel.discord_required"),
);
const sessionStateTitle = computed(() => {
  if (activity.accessError) return t("panel.access_denied");
  if (activity.error) return t("panel.session_failed");
  return t("panel.session_loading");
});
const sessionStateText = computed(() =>
  activity.accessError?.message || activity.error || t("panel.preparing_workspace"),
);
const sessionActionLabel = computed(() => {
  if (activity.accessError?.can_sync_roles) return t("panel.sync_roles");
  if (activity.error) return t("common.retry");
  return undefined;
});
const activeModuleLoaded = computed(() => Boolean(activity.loadedModules[activeModule.value]));
const activeModulePending = computed(() => activity.moduleLoading && !activeModuleLoaded.value);
const activeModuleFailed = computed(() => Boolean(activity.moduleError && !activeModuleLoaded.value));
const isPreviewSystemModule = computed(() => !activity.session && ["integrations", "health"].includes(activeModule.value));
const canOpenActiveModule = computed(() => activeModule.value === "ai-review"
  ? Boolean(activity.aiModerator?.review_access)
  : activity.can(activeModule.value));
const visibleError = computed(() =>
  isPreviewSystemModule.value ? activity.moduleError || activity.healthError : activity.moduleError || activity.healthError || activity.error,
);

function clearVisibleError() {
  activity.moduleError = null;
  activity.healthError = null;
  activity.error = null;
}

async function handleSessionAction() {
  if (activity.accessError?.can_sync_roles) {
    await activity.syncRolesFromDiscord();
    return;
  }
  activity.booted = false;
  await activity.boot();
}

async function retryActiveModule() {
  await activity.loadModuleData(activeModule.value);
}

watch(
  () => activeModule.value,
  async (module) => {
    // Review is deliberately not an Activity-RBAC permission. It is exposed
    // only after the backend confirms the trusted Labeling access gate.
    if (activity.session && module === "ai-review" && !activity.aiModerator) {
      await activity.loadModuleData("muxivo-core");
    }
    if (activity.session && !canOpenActiveModule.value) {
      void router.replace("/no-access");
      return;
    }
    void activity.loadModuleData(module);
  },
  { immediate: true },
);
</script>

<template>
  <main :class="['panel-page', { 'is-session-gated': !activity.session }]">
    <PanelSidebar :modules="modules" :active-module="activeModule" :show-categories="Boolean(activity.session)" />

    <section :class="['panel-workspace', { 'is-session-gated': !activity.session }]">
      <PanelTopbar :title="activeTitle" :subtitle="subtitle" />
      <div v-if="visibleError && !activeModuleFailed" class="activity-error-banner" role="alert">
        <div>
          <strong>{{ $t("common.request_failed") }}</strong>
          <span>{{ visibleError }}</span>
        </div>
        <button class="icon-button" type="button" :aria-label="$t('common.dismiss_error')" @click="clearVisibleError"><X :size="18" /></button>
      </div>

      <div v-if="!activity.session && !isPreviewSystemModule" class="panel-content panel-access-content">
        <NoAccessState
          :title="sessionStateTitle"
          :text="sessionStateText"
          :action-label="sessionActionLabel"
          :busy="activity.moduleLoading || activity.loading"
          :guidance="Boolean(activity.accessError)"
          @action="handleSessionAction"
        />
      </div>

      <div v-else-if="activeModulePending" class="panel-content module-loading-state">
        <LoadingDots :label="$t('common.loading_module', { module: activeTitle })" />
        <h2>{{ activeTitle }}</h2>
        <p>{{ $t("common.loading_module_data") }}</p>
      </div>

      <div v-else-if="activeModuleFailed" class="panel-content">
        <NoAccessState
          :title="$t('common.module_failed')"
          :text="activity.moduleError || $t('common.module_load_failed')"
          :action-label="$t('common.retry')"
          :busy="activity.moduleLoading"
          @action="retryActiveModule"
        />
      </div>

      <div v-else class="panel-content">
        <DashboardPanel v-if="activeModule === 'dashboard'" :modules="modules" :active-module="activeModule" />
        <AccessControlPanel v-else-if="activeModule === 'access'" />
        <WelcomeModulePanel v-else-if="activeModule === 'welcome'" />
        <RolePanelsPanel v-else-if="activeModule === 'role-panels'" />
        <CreatorAlertsPanel v-else-if="activeModule === 'creator-alerts'" />
        <AiModeratorPanel v-else-if="activeModule === 'muxivo-core'" />
        <AiModerationReviewQueue v-else-if="activeModule === 'ai-review'" />
        <DevBlogPanel v-else-if="activeModule === 'dev-blog'" />
        <VoiceRoomsPanel v-else-if="activeModule === 'voice-rooms'" />
        <ServerStatsPanel v-else-if="activeModule === 'server-stats'" />
        <LogsPanel v-else-if="activeModule === 'logs'" />
        <BotSettingsPanel v-else-if="activeModule === 'bot-settings'" />
        <IntegrationsPanel v-else-if="activeModule === 'integrations'" />
        <HealthStatusPanel v-else-if="activeModule === 'health'" />

        <section v-else class="panel-section">
          <div class="section-heading">
            <span>{{ $t("panel.module_workspace") }}</span>
            <h2>{{ $t("panel.scaffolded", { module: activeTitle }) }}</h2>
            <div>
              <p>
                {{ $t("panel.scaffold_description") }}
              </p>
            </div>
          </div>
          <div class="empty-module">
            <strong>{{ activeTitle }}</strong>
            <span>{{ $t("panel.ready_for_api") }}</span>
          </div>
        </section>
      </div>
    </section>
  </main>
</template>
