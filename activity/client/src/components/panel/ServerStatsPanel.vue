<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useActivityStore } from "../../stores/activity.store";
import StatCard from "./StatCard.vue";
import PanelTabNav from "./PanelTabNav.vue";
import { t } from "../../i18n";

type StatsTab = "summary" | "chart" | "users" | "channels";

const activity = useActivityStore();
const activeTab = ref<StatsTab>("summary");
const userSearch = ref("");
let searchTimer: number | undefined;
const tabs = computed<Array<{ key: StatsTab; label: string }>>(() => [
  { key: "summary", label: t("stats.total") },
  { key: "chart", label: t("stats.chart") },
  { key: "users", label: t("stats.users") },
  { key: "channels", label: t("stats.channels") },
]);
const dailyStats = computed(() => activity.serverStats?.daily?.slice(-30) || []);
const maxDaily = computed(() => Math.max(1, ...dailyStats.value.map((row) => row.count)));
const summaryCards = computed(() => {
  const summary = activity.serverStats?.summary || {};
  return [
    ["current_member_count", "stats.current_members"],
    ["total_messages", "stats.total_messages"],
    ["active_users", "stats.active_users"],
    ["active_channels", "stats.active_channels"],
    ["voice_total_voice_minutes", "stats.voice_minutes"],
    ["voice_voice_users", "stats.voice_users"],
    ["joins", "stats.joins"],
    ["leaves", "stats.leaves"],
    ["net_member_growth", "stats.net_growth"],
    ["moderation_events", "stats.moderation_events"],
    ["dau", "DAU"],
    ["wau", "WAU"],
    ["mau", "MAU"],
    ["messages_per_active_user", "Messages / active user"],
    ["joins_24h", "Joins · 24h"],
    ["joins_7d", "Joins · 7d"],
    ["joins_30d", "Joins · 30d"],
    ["leaves_24h", "Leaves · 24h"],
    ["leaves_7d", "Leaves · 7d"],
    ["leaves_30d", "Leaves · 30d"],
    ["period_days", "stats.period_days"],
  ].map(([key, label]) => ({ key, label: t(label), value: formatRecordValue(summary[key]), delta: t(key === "period_days" ? "stats.selected_range" : "stats.tracked_activity"), tone: "neutral" as const }));
});

async function searchStatsUsers() { await activity.searchStatsUsers(userSearch.value); }
function selectUser(row: Record<string, unknown>) { const member = row.member as Record<string, unknown> | undefined; userSearch.value = String(member?.display_name || member?.username || ""); }
function formatRecordValue(value: unknown) { if (value === null || value === undefined || value === "") return "-"; return typeof value === "object" ? JSON.stringify(value) : String(value); }
function formatMinutes(value: unknown) { const minutes = Number(value || 0); if (!Number.isFinite(minutes)) return "-"; const hours = Math.floor(minutes / 60); return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`; }
function nestedValue(row: Record<string, unknown>, key: string, nestedKey: string) { const nested = row[key]; return !nested || typeof nested !== "object" ? "-" : formatRecordValue((nested as Record<string, unknown>)[nestedKey]); }
function statValue(row: Record<string, unknown>, key: string) { const stats = row.stats; return !stats || typeof stats !== "object" ? "-" : formatRecordValue((stats as Record<string, unknown>)[key]); }

watch(userSearch, (value) => {
  if (searchTimer) window.clearTimeout(searchTimer);
  if (value.trim().length < 2) { activity.userStatsResults = []; return; }
  searchTimer = window.setTimeout(() => { void searchStatsUsers(); }, 250);
});
</script>

<template>
  <section class="panel-section module-intro">
    <div class="section-heading">
      <span>{{ $t("module.server-stats") }}</span>
      <h2>{{ $t("stats.heading") }}</h2>
      <div><p>{{ $t("stats.description") }}</p></div>
    </div>
  </section>

  <section class="panel-section module-tabs-panel"><PanelTabNav v-model="activeTab" :tabs="tabs" :aria-label="$t('module.server-stats')" /></section>

  <section v-if="activeTab === 'summary'" class="panel-section module-content-panel stats-summary-panel">
    <p v-if="activity.serverStats?.summary?.membership_history_since" class="field-note">
      {{ $t("stats.membership_history_since", { value: activity.serverStats.summary.membership_history_since }) }}
    </p>
    <div class="stats-grid"><StatCard v-for="metric in summaryCards" :key="metric.key" :metric="metric" /></div>
  </section>

  <section v-else-if="activeTab === 'chart'" class="panel-section module-content-panel stats-chart-panel">
    <div class="section-heading"><span>{{ $t("stats.chart") }}</span><h2>{{ $t("stats.chart_heading") }}</h2></div>
    <div class="stats-daily"><div v-for="point in dailyStats" :key="point.date" class="stats-day"><span :style="{ height: `${Math.max(4, (point.count / maxDaily) * 100)}%` }"></span><small>{{ point.date.slice(5) }}</small></div></div>
  </section>

  <section v-else-if="activeTab === 'users'" class="panel-section module-content-panel stats-search-panel">
    <form class="module-toolbar" @submit.prevent="searchStatsUsers"><input v-model="userSearch" :placeholder="$t('stats.search_user')" aria-label="Search by name, username, or Discord ID" /><button class="primary-button" type="submit">{{ $t("common.search") }}</button></form>
    <p class="field-note">Search by display name, username, or full/partial Discord ID.</p>
    <div v-if="activity.userStatsResults.length" class="user-suggestion-list"><button v-for="row in activity.userStatsResults" :key="nestedValue(row, 'member', 'id')" type="button" @click="selectUser(row)">{{ nestedValue(row, "member", "display_name") }}</button></div>
    <div class="record-list user-stat-list"><article v-for="row in activity.userStatsResults" :key="nestedValue(row, 'member', 'id')"><strong>{{ nestedValue(row, "member", "display_name") }}</strong><span>ID: {{ nestedValue(row, "member", "id") }}</span><span>{{ $t("stats.messages", { value: statValue(row, "messages_count") }) }}</span><span>7d: {{ statValue(row, "messages_7d") }} · 30d: {{ statValue(row, "messages_30d") }} · active days: {{ statValue(row, "active_days_30d") }}</span><span>{{ $t("stats.voice_minutes_value", { value: formatMinutes((row.stats as Record<string, unknown>)?.voice_minutes) }) }}</span><span>{{ $t("stats.warnings", { value: statValue(row, "warnings_count") }) }} · timeouts: {{ statValue(row, "timeouts_count") }} · kicks: {{ statValue(row, "kicks_count") }} · bans: {{ statValue(row, "bans_count") }}</span><span>AI flags: {{ statValue(row, "ai_flags") }} · moderator overrides: {{ statValue(row, "moderator_overrides") }}</span><span>Joined: {{ statValue(row, "first_joined_at") }} · joins: {{ statValue(row, "join_count") }}</span><span>{{ $t("stats.last_message", { value: statValue(row, "last_message") }) }}</span></article></div>
    <p v-if="!activity.userStatsResults.length && userSearch.trim().length >= 2" class="field-note">No matching members were found.</p>
  </section>

  <section v-else class="panel-section module-content-panel stats-channel-panel">
    <div class="section-heading"><span>{{ $t("common.channels") }}</span><h2>{{ $t("stats.top_channels") }}</h2></div>
    <div class="record-list compact-list channel-stat-list"><article v-for="channel in (activity.serverStats?.channels || [])" :key="String(channel.channel_id)"><strong>#{{ channel.channel_name }}</strong><span>{{ $t("stats.message_count", { value: formatRecordValue(channel.messages) }) }}</span></article></div>
  </section>
</template>
