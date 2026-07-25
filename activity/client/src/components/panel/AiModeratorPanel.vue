<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Check, Hash, Plus, ShieldCheck, Trash2 } from "@lucide/vue";
import RevealOnScroll from "../common/RevealOnScroll.vue";
import { useActivityStore } from "../../stores/activity.store";
import type { AiModerationAction, AiModerationLabelPolicy, AiModerationPolicy } from "../../types/activity.types";
import { t } from "../../i18n";

type AiModeratorTab = "channels" | "policy" | "blacklist" | "domains" | "exceptions" | "actions" | "risk" | "metrics";

type LabelDefinition = {
  key: string;
  titleKey: string;
  descriptionKey: string;
  defaultPolicy: AiModerationLabelPolicy;
};

const activity = useActivityStore();
const activeTab = ref<AiModeratorTab>("channels");
const selectedChannels = ref<string[]>([]);
const blacklistDraft = ref("");
const domainDraft = ref("");
const excludedUserDraft = ref("");
const excludedRoleDraft = ref("");
const excludedChannelDraft = ref("");
const status = ref("");
const settings = computed(() => activity.aiModerator);
const actionOptions = computed(() => (["IGNORE", "LOG", "REVIEW", "WARN", "DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"] as AiModerationAction[])
  .filter((value) => !["TIMEOUT", "KICK", "BAN"].includes(value) || (moderationPolicy.enforcement_mode === "ELEVATED" && moderationPolicy.beta_enforcement_acknowledged && ({ TIMEOUT: moderationPolicy.allow_automated_timeout, KICK: moderationPolicy.allow_automated_kick, BAN: moderationPolicy.allow_automated_ban }[value] ?? false)))
  .map((value) => ({ value, labelKey: `ai.action.${value}` })));
const actionRank: Record<AiModerationAction, number> = Object.fromEntries(
  ["IGNORE", "LOG", "REVIEW", "WARN", "DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"].map((value, index) => [value, index]),
) as Record<AiModerationAction, number>;
const labelDefinitions: LabelDefinition[] = [
  ...([
    ["SPAM", 30, "LOG", "DELETE"], ["ADVERTISEMENT", 25, "LOG", "DELETE"], ["INVITE", 20, "LOG", "DELETE"],
    ["SCAM", 55, "DELETE_WARN", "BAN"], ["TOXIC", 45, "LOG", "WARN"], ["PROFANITY", 25, "LOG", "WARN"],
    ["POLITICS_IRL", 40, "REVIEW", "REVIEW"], ["HATE", 55, "WARN", "TIMEOUT"], ["THREAT", 65, "DELETE_WARN", "BAN"],
    ["NSFW", 55, "DELETE", "TIMEOUT"], ["EVASION", 50, "WARN", "TIMEOUT"], ["FLOOD", 30, "LOG", "DELETE"],
    ["URL", 45, "REVIEW", "DELETE"], ["IMAGE_SCAM", 55, "DELETE_WARN", "BAN"],
  ] as Array<[string, number, AiModerationAction, AiModerationAction]>).map(([key, risk, min, max]) => ({
    key, titleKey: `ai.label.${key}.title`, descriptionKey: `ai.label.${key}.description`, defaultPolicy: policy(risk, min, max),
  })),
];
const tabs = computed(() => (["channels", "policy", "blacklist", "domains", "exceptions", "actions", "risk", ...(settings.value?.metrics_enabled ? ["metrics"] : [])] as AiModeratorTab[])
  .map((key) => ({ key, labelKey: `ai.tab.${key}` })));
const moderationPolicy = reactive<AiModerationPolicy>(emptyPolicy());

watch(settings, (value) => {
  selectedChannels.value = visibleSelectedChannels(value?.channels ?? []);
  Object.assign(moderationPolicy, clonePolicy(value?.policy));
}, { immediate: true });

function policy(riskThreshold: number, minAction: AiModerationAction, maxAction: AiModerationAction): AiModerationLabelPolicy {
  return { risk_threshold: riskThreshold, min_action: minAction, max_action: maxAction };
}

function emptyPolicy(): AiModerationPolicy {
  return {
    blacklist_words: [],
    allowed_domains: [],
    labels: Object.fromEntries(labelDefinitions.map((item) => [item.key, { ...item.defaultPolicy }])),
    blacklist_action: "DELETE_WARN",
    unapproved_domain_action: "REVIEW",
    context_window_days: 30,
    repeat_offender_threshold: 3,
    repeat_offender_action: "TIMEOUT",
    escalation_enabled: true,
    escalation_score_threshold: 3,
    escalation_half_life_days: 30,
    excluded_user_ids: [],
    excluded_role_ids: [],
    excluded_channel_ids: [],
    exclude_bots: true,
    test_mode: false,
    enforcement_mode: "SHADOW",
    limited_min_confidence: 0.95,
    beta_enforcement_acknowledged: false,
    allow_automated_timeout: false,
    allow_automated_kick: false,
    allow_automated_ban: false,
  };
}

function clonePolicy(source: AiModerationPolicy | undefined): AiModerationPolicy {
  const defaults = emptyPolicy();
  if (!source) return defaults;
  return {
    blacklist_words: [...source.blacklist_words],
    allowed_domains: [...source.allowed_domains],
    labels: Object.fromEntries(labelDefinitions.map((item) => [item.key, { ...source.labels[item.key] ?? item.defaultPolicy }])),
    blacklist_action: source.blacklist_action,
    unapproved_domain_action: source.unapproved_domain_action,
    context_window_days: source.context_window_days ?? 30,
    repeat_offender_threshold: source.repeat_offender_threshold ?? 3,
    repeat_offender_action: source.repeat_offender_action ?? "TIMEOUT",
    escalation_enabled: source.escalation_enabled ?? true,
    escalation_score_threshold: source.escalation_score_threshold ?? 3,
    escalation_half_life_days: source.escalation_half_life_days ?? 30,
    excluded_user_ids: [...(source.excluded_user_ids ?? [])],
    excluded_role_ids: [...(source.excluded_role_ids ?? [])],
    excluded_channel_ids: [...(source.excluded_channel_ids ?? [])],
    exclude_bots: source.exclude_bots ?? true,
    test_mode: source.test_mode ?? false,
    enforcement_mode: source.enforcement_mode ?? "SHADOW",
    limited_min_confidence: source.limited_min_confidence ?? 0.95,
    beta_enforcement_acknowledged: source.beta_enforcement_acknowledged ?? false,
    allow_automated_timeout: source.allow_automated_timeout ?? false,
    allow_automated_kick: source.allow_automated_kick ?? false,
    allow_automated_ban: source.allow_automated_ban ?? false,
  };
}

function tabLetters(label: string) {
  return Array.from(label);
}

function policyFor(label: string): AiModerationLabelPolicy {
  return moderationPolicy.labels[label];
}

function setMinimumAction(label: string, value: AiModerationAction) {
  const current = policyFor(label);
  current.min_action = value;
  if (actionRank[value] > actionRank[current.max_action]) current.max_action = value;
}

function setMaximumAction(label: string, value: AiModerationAction) {
  const current = policyFor(label);
  current.max_action = value;
  if (actionRank[value] < actionRank[current.min_action]) current.min_action = value;
}

async function saveChannels() {
  try {
    selectedChannels.value = visibleSelectedChannels(selectedChannels.value);
    await activity.saveAiModeratorChannelValues(selectedChannels.value);
    status.value = t("ai.channels_saved");
  } catch (error) {
    status.value = error instanceof Error ? error.message : t("ai.channels_failed");
  }
}

function visibleSelectedChannels(channelIds: string[]): string[] {
  const availableIds = new Set(settings.value?.available_channels.map((channel) => channel.id) ?? []);
  if (!availableIds.size) return channelIds;
  return channelIds.filter((channelId) => availableIds.has(channelId));
}

async function savePolicy(message: string) {
  try {
    await activity.saveAiModeratorPolicyValue(clonePolicy(moderationPolicy));
    status.value = message;
  } catch (error) {
    status.value = error instanceof Error ? error.message : t("ai.policy_failed");
  }
}

async function loadMetrics() {
  try { await activity.loadAiModeratorMetrics(); } catch (error) { status.value = error instanceof Error ? error.message : "Metrics are unavailable"; }
}

function addBlacklistWords() {
  const values = splitValues(blacklistDraft.value);
  moderationPolicy.blacklist_words = unique([...moderationPolicy.blacklist_words, ...values]);
  blacklistDraft.value = "";
}

function addDomains() {
  const values = splitValues(domainDraft.value).map(normalizeDomain).filter(Boolean);
  moderationPolicy.allowed_domains = unique([...moderationPolicy.allowed_domains, ...values]);
  domainDraft.value = "";
}

function splitValues(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 200);
}

function unique(values: string[]): string[] {
  return [...new Set(values.map((item) => item.toLocaleLowerCase()))].slice(0, 200);
}

function normalizeDomain(value: string): string {
  try {
    return new URL(value.includes("://") ? value : `https://${value}`).hostname.toLocaleLowerCase();
  } catch {
    return value.replace(/^www\./i, "").split("/")[0].toLocaleLowerCase();
  }
}

function removeValue(values: string[], value: string): string[] {
  return values.filter((item) => item !== value);
}

function addExcludedId(kind: "user" | "role" | "channel") {
  const draft = kind === "user" ? excludedUserDraft : kind === "role" ? excludedRoleDraft : excludedChannelDraft;
  const ids = unique(draft.value.split(",").map((value) => value.trim()).filter((value) => /^\d{1,20}$/.test(value)));
  const property = kind === "user" ? "excluded_user_ids" : kind === "role" ? "excluded_role_ids" : "excluded_channel_ids";
  moderationPolicy[property] = unique([...moderationPolicy[property], ...ids]);
  draft.value = "";
}
</script>

<template>
  <RevealOnScroll tag="section" class="panel-section module-intro">
    <div class="section-heading">
      <span>{{ $t("module.ai-moderator") }}</span>
      <h2>{{ $t("ai.heading") }}</h2>
      <div><p>{{ $t("ai.description") }}</p></div>
    </div>

  </RevealOnScroll>

  <RevealOnScroll tag="section" class="panel-section module-tabs-panel ai-moderator-tabs" :delay="35">
    <nav class="ai-moderation-nav" :aria-label="$t('ai.settings')">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key }"
        :aria-current="activeTab === tab.key ? 'page' : undefined"
        @click="activeTab = tab.key"
      >
        <span
          v-for="(letter, index) in tabLetters($t(tab.labelKey))"
          :key="`${tab.key}-${index}`"
          class="ai-moderation-nav-letter"
          :style="{ transitionDelay: `${index * 22}ms` }"
        >{{ letter === " " ? "\u00a0" : letter }}</span>
      </button>
    </nav>
  </RevealOnScroll>

  <RevealOnScroll tag="section" class="panel-section module-content-panel" :delay="60">
    <div v-if="activeTab === 'channels'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy">
        <div>
          <span class="ai-moderation-kicker">{{ $t("ai.channel_coverage") }}</span>
          <h3>{{ $t("ai.moderated_channels") }}</h3>
          <p>{{ $t("ai.channels_help") }}</p>
        </div>
        <span v-if="settings?.log_channel_id" class="ai-moderation-log-status"><Check :size="15" /> {{ $t("ai.log_connected") }}</span>
        <span v-else class="ai-moderation-log-status muted">{{ $t("ai.set_log") }}</span>
      </div>
      <div v-if="settings?.available_channels.length" class="ai-channel-grid">
        <label v-for="channel in settings.available_channels" :key="channel.id" class="ai-channel-card" :class="{ selected: selectedChannels.includes(channel.id) }">
          <input v-model="selectedChannels" type="checkbox" :value="channel.id" />
          <span class="ai-channel-icon"><Hash :size="18" /></span>
          <span class="ai-channel-copy"><strong>{{ channel.name }}</strong><small>{{ $t(selectedChannels.includes(channel.id) ? "ai.checks_enabled" : "ai.not_monitored") }}</small></span>
          <span class="ai-channel-check"><Check :size="16" /></span>
        </label>
      </div>
      <div v-else class="ai-empty-state"><Hash :size="22" /><span>{{ $t("ai.no_channels") }}</span></div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="saveChannels">{{ $t("ai.save_channels") }}</button></div>
    </div>

    <div v-else-if="activeTab === 'policy'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy">
        <div>
          <span class="ai-moderation-kicker">{{ $t("ai.server_policy") }}</span>
          <h3>{{ $t(settings?.is_default_policy ? "ai.default_policy" : "ai.custom_policy") }}</h3>
          <p>{{ $t(settings?.is_default_policy ? "ai.default_help" : "ai.custom_help") }}</p>
        </div>
        <ShieldCheck :size="32" class="ai-policy-icon" />
      </div>
      <div class="ai-policy-summary">
        <article><strong>{{ labelDefinitions.length }}</strong><span>{{ $t("ai.content_categories") }}</span></article>
        <article><strong>{{ moderationPolicy.blacklist_words.length }}</strong><span>{{ $t("ai.blocked_words_count") }}</span></article>
        <article><strong>{{ moderationPolicy.allowed_domains.length }}</strong><span>{{ $t("ai.allowed_domains_count") }}</span></article>
      </div>
      <div class="ai-policy-controls">
        <label><span>{{ $t("ai.blocked_action") }}</span><select v-model="moderationPolicy.blacklist_action"><option v-for="action in actionOptions" :key="action.value" :value="action.value">{{ $t(action.labelKey) }}</option></select></label>
        <label><span>{{ $t("ai.domain_action") }}</span><select v-model="moderationPolicy.unapproved_domain_action"><option v-for="action in actionOptions" :key="action.value" :value="action.value">{{ $t(action.labelKey) }}</option></select></label>
      </div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy($t('ai.policy_saved'))">{{ $t("ai.save_policy") }}</button></div>
    </div>

    <div v-else-if="activeTab === 'blacklist'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">{{ $t("ai.word_filter") }}</span><h3>{{ $t("ai.blocked_words") }}</h3><p>{{ $t("ai.blocked_help") }}</p></div></div>
      <div class="ai-token-input"><input v-model="blacklistDraft" maxlength="253" :placeholder="$t('ai.add_word')" @keyup.enter.prevent="addBlacklistWords" /><button class="ghost-button" type="button" @click="addBlacklistWords"><Plus :size="16" /> {{ $t("ai.add") }}</button></div>
      <div v-if="moderationPolicy.blacklist_words.length" class="ai-token-list"><span v-for="word in moderationPolicy.blacklist_words" :key="word" class="ai-token">{{ word }}<button type="button" :aria-label="$t('ai.remove_value', { value: word })" @click="moderationPolicy.blacklist_words = removeValue(moderationPolicy.blacklist_words, word)"><Trash2 :size="14" /></button></span></div>
      <div v-else class="ai-empty-state"><ShieldCheck :size="22" /><span>{{ $t("ai.no_blocked") }}</span></div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy($t('ai.blocked_saved'))">{{ $t("ai.save_blocked") }}</button></div>
    </div>

    <div v-else-if="activeTab === 'domains'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">{{ $t("ai.link_rules") }}</span><h3>{{ $t("ai.allowed_domains") }}</h3><p>{{ $t("ai.domains_help") }}</p></div></div>
      <div class="ai-token-input"><input v-model="domainDraft" maxlength="253" placeholder="example.com" @keyup.enter.prevent="addDomains" /><button class="ghost-button" type="button" @click="addDomains"><Plus :size="16" /> {{ $t("ai.add") }}</button></div>
      <div v-if="moderationPolicy.allowed_domains.length" class="ai-token-list"><span v-for="domain in moderationPolicy.allowed_domains" :key="domain" class="ai-token">{{ domain }}<button type="button" :aria-label="$t('ai.remove_value', { value: domain })" @click="moderationPolicy.allowed_domains = removeValue(moderationPolicy.allowed_domains, domain)"><Trash2 :size="14" /></button></span></div>
      <div v-else class="ai-empty-state"><Hash :size="22" /><span>{{ $t("ai.all_links_review") }}</span></div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy($t('ai.domains_saved'))">{{ $t("ai.save_domains") }}</button></div>
    </div>

    <div v-else-if="activeTab === 'exceptions'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">EXCLUSIONS</span><h3>AI moderator allowlist</h3><p>Excluded users, roles and channels are not evaluated or punished. Bot messages remain excluded by default.</p></div></div>
      <div class="ai-policy-controls"><label><span>Exclude bot messages</span><input v-model="moderationPolicy.exclude_bots" type="checkbox" /></label><label><span>Escalate repeated offences</span><input v-model="moderationPolicy.escalation_enabled" type="checkbox" /></label><label><span>Escalation score</span><input v-model.number="moderationPolicy.escalation_score_threshold" type="number" min="0.1" max="1000" step="0.1" /></label><label><span>History half-life, days</span><input v-model.number="moderationPolicy.escalation_half_life_days" type="number" min="1" max="3650" step="1" /></label></div>
      <div v-for="item in [['user', 'Users', excludedUserDraft, moderationPolicy.excluded_user_ids], ['role', 'Roles', excludedRoleDraft, moderationPolicy.excluded_role_ids], ['channel', 'Channels', excludedChannelDraft, moderationPolicy.excluded_channel_ids]] as const" :key="item[0]" class="ai-moderation-section-copy"><div><h3>{{ item[1] }}</h3><p>Discord IDs only; use comma-separated values.</p><div class="ai-token-input"><input v-model="item[2].value" inputmode="numeric" placeholder="Discord ID" @keyup.enter.prevent="addExcludedId(item[0])" /><button class="ghost-button" type="button" @click="addExcludedId(item[0])"><Plus :size="16" /> {{ $t('ai.add') }}</button></div><div v-if="item[3].length" class="ai-token-list"><span v-for="value in item[3]" :key="value" class="ai-token">{{ value }}<button type="button" :aria-label="`Remove ${value}`" @click="moderationPolicy[item[0] === 'user' ? 'excluded_user_ids' : item[0] === 'role' ? 'excluded_role_ids' : 'excluded_channel_ids'] = removeValue(item[3], value)"><Trash2 :size="14" /></button></span></div></div></div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy('AI moderator exclusions saved.')">Save exclusions</button></div>
    </div>

    <div v-else-if="activeTab === 'actions'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">{{ $t("ai.action_boundaries") }}</span><h3>{{ $t("ai.action_heading") }}</h3><p>{{ $t("ai.action_help") }}</p></div></div>
      <div class="ai-rule-list">
        <article v-for="label in labelDefinitions" :key="label.key" class="ai-rule-card"><div><strong>{{ $t(label.titleKey) }}</strong><span>{{ $t(label.descriptionKey) }}</span></div><label><span>{{ $t("ai.at_least") }}</span><select :value="policyFor(label.key).min_action" @change="setMinimumAction(label.key, ($event.target as HTMLSelectElement).value as AiModerationAction)"><option v-for="action in actionOptions" :key="action.value" :value="action.value">{{ $t(action.labelKey) }}</option></select></label><label><span>{{ $t("ai.at_most") }}</span><select :value="policyFor(label.key).max_action" @change="setMaximumAction(label.key, ($event.target as HTMLSelectElement).value as AiModerationAction)"><option v-for="action in actionOptions" :key="action.value" :value="action.value">{{ $t(action.labelKey) }}</option></select></label></article>
      </div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy($t('ai.actions_saved'))">{{ $t("ai.save_actions") }}</button></div>
    </div>

    <div v-else-if="activeTab === 'risk'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">{{ $t("ai.sensitivity") }}</span><h3>{{ $t("ai.risk_heading") }}</h3><p>{{ $t("ai.risk_help") }}</p></div></div>
      <div class="ai-risk-list">
        <label v-for="label in labelDefinitions" :key="label.key" class="ai-risk-card"><span><strong>{{ $t(label.titleKey) }}</strong><small>{{ $t(label.descriptionKey) }}</small></span><input v-model.number="policyFor(label.key).risk_threshold" type="range" min="0" max="100" step="1" /><output>{{ policyFor(label.key).risk_threshold }}</output></label>
      </div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy($t('ai.risk_saved'))">{{ $t("ai.save_risk") }}</button></div>
    </div>

    <div v-else-if="activeTab === 'enforcement'" class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">BETA ENFORCEMENT</span><h3>Limited enforcement</h3><p>Shadow mode records recommendations only. Limited mode can delete high-confidence hard-rule invite/scam cases and warn for soft violations.</p></div></div>
      <div class="settings-list">
        <article><strong>Mode</strong><select v-model="moderationPolicy.enforcement_mode"><option value="SHADOW">Shadow — no automatic punishment</option><option value="LIMITED">Limited — DELETE/WARN only</option><option value="ELEVATED">Elevated — requires explicit toggles</option></select></article>
        <article><strong>Limited confidence</strong><input v-model.number="moderationPolicy.limited_min_confidence" type="number" min="0.8" max="1" step="0.01" /></article>
        <article><strong>I accept beta responsibility</strong><input v-model="moderationPolicy.beta_enforcement_acknowledged" type="checkbox" /></article>
        <article><strong>Allow automatic timeout</strong><input v-model="moderationPolicy.allow_automated_timeout" :disabled="!moderationPolicy.beta_enforcement_acknowledged || moderationPolicy.enforcement_mode !== 'ELEVATED'" type="checkbox" /></article>
        <article><strong>Allow automatic kick</strong><input v-model="moderationPolicy.allow_automated_kick" :disabled="!moderationPolicy.beta_enforcement_acknowledged || moderationPolicy.enforcement_mode !== 'ELEVATED'" type="checkbox" /></article>
        <article><strong>Allow automatic ban</strong><input v-model="moderationPolicy.allow_automated_ban" :disabled="!moderationPolicy.beta_enforcement_acknowledged || moderationPolicy.enforcement_mode !== 'ELEVATED'" type="checkbox" /></article>
      </div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="activity.moduleLoading" @click="savePolicy('Enforcement settings saved.')">Save enforcement</button></div>
    </div>

    <div v-else class="ai-moderation-workspace">
      <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">PRIVATE METRICS</span><h3>Shadow mode quality</h3><p>Visible only after a trusted owner or ADMIN grants access via DM.</p></div><button class="ghost-button" type="button" @click="loadMetrics">Refresh</button></div>
      <div v-if="activity.aiModeratorMetrics" class="ai-policy-summary"><article><strong>{{ activity.aiModeratorMetrics.would_delete }}</strong><span>Would delete</span></article><article><strong>{{ activity.aiModeratorMetrics.review_count }}</strong><span>Sent to review</span></article><article><strong>{{ activity.aiModeratorMetrics.average_latency_ms }} ms</strong><span>Average latency</span></article><article><strong>{{ activity.aiModeratorMetrics.safe_false_positive_rate === null ? '—' : `${(activity.aiModeratorMetrics.safe_false_positive_rate * 100).toFixed(1)}%` }}</strong><span>SAFE false positives</span></article></div>
      <div v-if="activity.aiModeratorMetrics" class="settings-list"><article><strong>Frequently confused classes</strong><span>{{ activity.aiModeratorMetrics.confused_classes.map((item) => `${item.name}: ${item.count}`).join(', ') || 'No moderator corrections yet' }}</span></article><article><strong>Noisy rules</strong><span>{{ activity.aiModeratorMetrics.noisy_rules.map((item) => `${item.name}: ${item.count}`).join(', ') || 'No events yet' }}</span></article><article><strong>Moderator correction speed</strong><span>{{ activity.aiModeratorMetrics.moderator_correction_seconds === null ? '—' : `${activity.aiModeratorMetrics.moderator_correction_seconds}s` }}</span></article></div>
    </div>

    <p v-if="status" class="ai-moderation-status" role="status">{{ status }}</p>
  </RevealOnScroll>
</template>
