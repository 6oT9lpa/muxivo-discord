<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RefreshCcw, ShieldAlert } from "@lucide/vue";
import RevealOnScroll from "../common/RevealOnScroll.vue";
import { useActivityStore } from "../../stores/activity.store";
import type { ActivityRolePurpose, AiModerationPolicy, ChannelPurpose } from "../../types/activity.types";
import { t } from "../../i18n";

type BotSettingsTab = "general" | "channels" | "roles" | "ai_moderator";

const activity = useActivityStore();
const activeTab = ref<BotSettingsTab>("general");
const status = ref("");
const tabs = computed<Array<{ key: BotSettingsTab; label: string }>>(() => ["general", "channels", "roles", "ai_moderator"].map((key) => ({ key: key as BotSettingsTab, label: t(`settings.${key}`) })));
const channelPurposeKeys: ChannelPurpose[] = ["welcome", "member_log", "mod_log", "message_log", "channel_log", "stream_announce", "dev_blog", "ai_moderation_log"];
const channelPurposes = computed(() => channelPurposeKeys.map((key) => ({ key, label: t(`settings.channel.${key}`) })));
const rolePurposeKeys: ActivityRolePurpose[] = ["activity_admin", "activity_streamer", "activity_developer", "ping_stream", "ping_dev"];
const rolePurposes = computed(() => rolePurposeKeys.map((key) => ({ key, label: t(`settings.role.${key}`) })));
const subscriptionTier = computed(() => activity.botSettings?.subscription_tier || "free");
const runtimeRows = computed(() => [
  [t("settings.presence_rotation"), t(activity.botSettings?.activity_rotation_enabled ? "common.enabled" : "common.disabled")],
  [t("settings.rotation_interval"), t("settings.seconds", { value: activity.botSettings?.activity_rotation_interval_seconds || "-" })],
  [t("settings.message_retention"), t("settings.days", { value: activity.botSettings?.retention?.message_log_retention_days || "-" })],
  [t("settings.punishment_retention"), t("settings.days", { value: activity.botSettings?.retention?.punishment_retention_days || "-" })],
]);
const enforcement = reactive<Pick<AiModerationPolicy, "enforcement_mode" | "limited_min_confidence" | "beta_enforcement_acknowledged" | "allow_automated_timeout" | "allow_automated_kick" | "allow_automated_ban" | "test_mode">>({
  enforcement_mode: "SHADOW", limited_min_confidence: 0.95, beta_enforcement_acknowledged: false,
  allow_automated_timeout: false, allow_automated_kick: false, allow_automated_ban: false, test_mode: false,
});
const elevatedEnabled = computed(() => enforcement.enforcement_mode === "ELEVATED" && enforcement.beta_enforcement_acknowledged);
const simulationText = ref("");

// The beta controls edit the same server policy as the AI module, so rehydrate
// them whenever the asynchronous settings request finishes or is refreshed.
watch(() => activity.aiModerator?.policy, (policy) => {
  if (!policy) return;
  Object.assign(enforcement, {
    enforcement_mode: policy.enforcement_mode ?? "SHADOW", limited_min_confidence: policy.limited_min_confidence ?? 0.95,
    beta_enforcement_acknowledged: policy.beta_enforcement_acknowledged ?? false, allow_automated_timeout: policy.allow_automated_timeout ?? false,
    allow_automated_kick: policy.allow_automated_kick ?? false, allow_automated_ban: policy.allow_automated_ban ?? false,
    test_mode: policy.test_mode ?? false,
  });
}, { immediate: true });

// Bot Settings owns the beta controls but the policy endpoint belongs to AI Moderator.
onMounted(() => { void activity.loadModuleData("ai-moderator"); });

async function saveChannel(purpose: ChannelPurpose, value: string) { if (!value) return; try { await activity.saveChannelPurposeValue(purpose, value); status.value = t("settings.channel_saved"); } catch { status.value = t("settings.channel_failed"); } }
async function saveRole(purpose: ActivityRolePurpose, value: string) { if (!value) return; try { await activity.saveActivityRolePurpose(purpose, value); status.value = t("settings.role_saved"); } catch { status.value = t("settings.role_failed"); } }
async function toggleWelcome(value: boolean) { try { await activity.saveWelcome({ ...activity.welcome, is_enabled: value }); status.value = t("settings.welcome_saved"); } catch { status.value = t("settings.welcome_failed"); } }
async function saveEnforcement() {
  if (!activity.aiModerator) { status.value = t("settings.ai_moderator_unavailable"); return; }
  try { await activity.saveAiModeratorPolicyValue({ ...activity.aiModerator.policy, ...enforcement }); status.value = t("settings.ai_moderator_saved"); }
  catch { status.value = t("settings.ai_moderator_failed"); }
}
async function runSimulation() {
  if (!simulationText.value.trim()) { status.value = "Enter a message to simulate."; return; }
  try { await activity.simulateAiModerator(simulationText.value.trim()); status.value = "Simulation complete. No Discord action or dataset event was created."; }
  catch (error) { status.value = error instanceof Error ? error.message : "Simulation failed"; }
}
</script>

<template>
  <RevealOnScroll tag="section" class="panel-section module-intro"><div class="section-heading"><span>{{ $t("module.bot-settings") }}</span><h2>{{ $t("settings.heading") }}</h2><div><p>{{ $t("settings.description") }}</p></div></div></RevealOnScroll>
  <RevealOnScroll tag="section" class="panel-section module-tabs-panel" :delay="35"><nav class="ai-moderation-nav" :aria-label="$t('module.bot-settings')"><button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button></nav></RevealOnScroll>
  <RevealOnScroll tag="section" class="panel-section module-content-panel" :delay="60">
    <div v-if="activeTab === 'general'" class="settings-list">
      <article><strong>{{ $t("settings.subscription") }}</strong><span :class="['subscription-tier', subscriptionTier]">{{ subscriptionTier }}</span><small>{{ $t("settings.plans") }}</small></article>
      <article><strong>{{ $t("settings.welcome_toggle") }}</strong><label class="toggle-row"><input type="checkbox" :checked="activity.welcome.is_enabled" @change="toggleWelcome(($event.target as HTMLInputElement).checked)" /><span>{{ $t(activity.welcome.is_enabled ? "common.enabled" : "common.disabled") }}</span></label></article>
      <article v-for="[label, value] in runtimeRows" :key="label"><strong>{{ label }}</strong><span>{{ value }}</span></article>
    </div>
    <div v-else-if="activeTab === 'channels'" class="settings-list"><article v-for="purpose in channelPurposes" :key="purpose.key"><strong>{{ purpose.label }}</strong><select v-model="activity.channelPurposes[purpose.key]" @change="saveChannel(purpose.key, activity.channelPurposes[purpose.key] || '')"><option value="">{{ $t("settings.select_channel") }}</option><option v-for="channel in activity.textChannels" :key="channel.id" :value="channel.id">#{{ channel.name }}</option></select></article><article v-if="activity.textChannels.length === 0"><strong>{{ $t("settings.no_channels") }}</strong><span>{{ $t("settings.no_channels_text") }}</span></article></div>
    <div v-else-if="activeTab === 'roles'" class="settings-roles-workspace"><header class="module-content-header"><div><h3>{{ $t("settings.roles") }}</h3><p>{{ $t("settings.roles_sync_description") }}</p></div><button class="ghost-button" type="button" :disabled="activity.moduleLoading" @click="activity.syncRolesFromDiscord"><RefreshCcw :size="16" /> {{ $t("settings.sync_roles") }}</button></header><div class="settings-list"><article v-for="purpose in rolePurposes" :key="purpose.key"><strong>{{ purpose.label }}</strong><select v-model="activity.activityRoles[purpose.key]" @change="saveRole(purpose.key, activity.activityRoles[purpose.key] || '')"><option value="">{{ $t("settings.select_role") }}</option><option v-for="role in activity.roles" :key="role.id" :value="role.id">{{ role.name }}</option></select></article><article v-if="activity.roles.length === 0"><strong>{{ $t("settings.no_roles") }}</strong><span>{{ $t("settings.no_roles_text") }}</span></article></div></div>
    <div v-else class="ai-beta-workspace">
      <div class="ai-beta-warning" role="alert"><ShieldAlert :size="28" /><div><span>{{ $t("settings.ai_beta_eyebrow") }}</span><h3>{{ $t("settings.ai_beta_warning_title") }}</h3><p>{{ $t("settings.ai_beta_warning_text") }}</p></div></div>
      <section class="ai-beta-card"><header><div><span class="ai-moderation-kicker">{{ $t("settings.ai_beta_controls") }}</span><h3>{{ $t("settings.ai_beta_heading") }}</h3><p>{{ $t("settings.ai_beta_help") }}</p></div></header><div class="ai-beta-fields"><label><span>{{ $t("settings.ai_mode") }}</span><select v-model="enforcement.enforcement_mode"><option value="SHADOW">{{ $t("settings.ai_mode_shadow") }}</option><option value="LIMITED">{{ $t("settings.ai_mode_limited") }}</option><option value="ELEVATED">{{ $t("settings.ai_mode_elevated") }}</option></select></label><label><span>{{ $t("settings.ai_confidence") }}</span><input v-model.number="enforcement.limited_min_confidence" type="number" min="0.8" max="1" step="0.01" /></label></div></section>
      <section class="ai-beta-card"><header><div><span class="ai-moderation-kicker">{{ $t("settings.ai_beta_permissions") }}</span><h3>{{ $t("settings.ai_beta_permissions_title") }}</h3><p>{{ $t("settings.ai_beta_permissions_help") }}</p></div></header><div class="ai-beta-toggle-list"><label class="ai-beta-toggle"><span><strong>{{ $t("settings.ai_acknowledge") }}</strong><small>{{ $t("settings.ai_acknowledge_help") }}</small></span><button type="button" class="ai-beta-switch" :class="{ 'is-on': enforcement.beta_enforcement_acknowledged }" role="switch" :aria-checked="enforcement.beta_enforcement_acknowledged" @click="enforcement.beta_enforcement_acknowledged = !enforcement.beta_enforcement_acknowledged"><i /></button></label><label v-for="item in [['allow_automated_timeout', 'settings.ai_timeout'], ['allow_automated_kick', 'settings.ai_kick'], ['allow_automated_ban', 'settings.ai_ban']] as const" :key="item[0]" class="ai-beta-toggle" :class="{ disabled: !elevatedEnabled }"><span><strong>{{ $t(item[1]) }}</strong><small>{{ $t('settings.ai_requires_elevated') }}</small></span><button type="button" class="ai-beta-switch" :class="{ 'is-on': enforcement[item[0]] }" role="switch" :aria-checked="enforcement[item[0]]" :disabled="!elevatedEnabled" @click="enforcement[item[0]] = !enforcement[item[0]]"><i /></button></label></div></section>
      <section class="ai-beta-card"><header><div><span class="ai-moderation-kicker">TEST MODE</span><h3>Simulation only</h3><p>Classify a test message using the current policy. It never deletes a Discord message, issues a punishment, or creates a Dataset Collector event.</p></div></header><div class="ai-beta-toggle-list"><label class="ai-beta-toggle"><span><strong>Enable AI moderator test mode</strong><small>All automatic Discord actions are suppressed while this switch is enabled.</small></span><button type="button" class="ai-beta-switch" :class="{ 'is-on': enforcement.test_mode }" role="switch" :aria-checked="enforcement.test_mode" @click="enforcement.test_mode = !enforcement.test_mode"><i /></button></label></div><div class="ai-simulation"><label><span>Test message</span><textarea v-model="simulationText" maxlength="8000" placeholder="Enter a message for the AI moderator" /></label><button class="ghost-button" type="button" :disabled="!enforcement.test_mode || activity.moduleLoading" @click="runSimulation">Run simulation</button><div v-if="activity.aiModeratorSimulation" class="ai-simulation-result"><strong>{{ activity.aiModeratorSimulation.primary_label }} · {{ activity.aiModeratorSimulation.risk_score }}/100</strong><span>Model: {{ activity.aiModeratorSimulation.model_action }} · Policy: {{ activity.aiModeratorSimulation.policy_action }}</span><small>Plan: {{ activity.aiModeratorSimulation.execution_plan.join(' → ') || 'IGNORE' }} · {{ activity.aiModeratorSimulation.latency_ms }} ms</small></div></div></section>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="saveEnforcement">{{ $t("settings.ai_save") }}</button></div>
    </div>
    <small v-if="status" class="ai-moderation-status" role="status">{{ status }}</small>
  </RevealOnScroll>
</template>
