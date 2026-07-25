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
    ["total_messages", "stats.total_messages"],
    ["active_users", "stats.active_users"],
    ["active_channels", "stats.active_channels"],
    ["voice_total_voice_minutes", "stats.voice_minutes"],
    ["voice_voice_users", "stats.voice_users"],
    ["joins", "stats.joins"],
    ["leaves", "stats.leaves"],
    ["period_days", "stats.period_days"],
  ].map(([key, label]) => ({ key, label: t(label), value: formatRecordValue(summary[key]), delta: t(key === "period_days" ? "stats.selected_range" : "stats.tracked_activity"), tone: "neutral" as const }));
});

async function searchStatsUsers() { await activity.searchStatsUsers(userSearch.value); }
function selectUser(row: Record<string, unknown>) { const member = row.member as Record<string, unknown> | undefined; userSearch.value = String(member?.display_name || member?.username || ""); }
function formatRecordValue(value: unknown) { if (value === null || value === undefined || value === "") return "-"; return typeof value === "object" ? JSON.stringify(value) : String(value); }
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
    <div class="stats-grid"><StatCard v-for="metric in summaryCards" :key="metric.key" :metric="metric" /></div>
  </section>

  <section v-else-if="activeTab === 'chart'" class="panel-section module-content-panel stats-chart-panel">
    <div class="section-heading"><span>{{ $t("stats.chart") }}</span><h2>{{ $t("stats.chart_heading") }}</h2></div>
    <div class="stats-daily"><div v-for="point in dailyStats" :key="point.date" class="stats-day"><span :style="{ height: `${Math.max(4, (point.count / maxDaily) * 100)}%` }"></span><small>{{ point.date.slice(5) }}</small></div></div>
  </section>

  <section v-else-if="activeTab === 'users'" class="panel-section module-content-panel stats-search-panel">
    <form class="module-toolbar" @submit.prevent="searchStatsUsers"><input v-model="userSearch" :placeholder="$t('stats.search_user')" /><button class="primary-button" type="submit">{{ $t("common.search") }}</button></form>
    <div v-if="activity.userStatsResults.length" class="user-suggestion-list"><button v-for="row in activity.userStatsResults" :key="nestedValue(row, 'member', 'id')" type="button" @click="selectUser(row)">{{ nestedValue(row, "member", "display_name") }}</button></div>
    <div class="record-list user-stat-list"><article v-for="row in activity.userStatsResults" :key="nestedValue(row, 'member', 'id')"><strong>{{ nestedValue(row, "member", "display_name") }}</strong><span>{{ $t("stats.messages", { value: statValue(row, "messages_count") }) }}</span><span>{{ $t("stats.voice_minutes_value", { value: statValue(row, "voice_minutes") }) }}</span><span>{{ $t("stats.warnings", { value: statValue(row, "warnings_count") }) }}</span><span>{{ $t("stats.last_message", { value: statValue(row, "last_message") }) }}</span></article></div>
  </section>

  <section v-else class="panel-section module-content-panel stats-channel-panel">
    <div class="section-heading"><span>{{ $t("common.channels") }}</span><h2>{{ $t("stats.top_channels") }}</h2></div>
    <div class="record-list compact-list channel-stat-list"><article v-for="channel in (activity.serverStats?.channels || [])" :key="String(channel.channel_id)"><strong>#{{ channel.channel_name }}</strong><span>{{ $t("stats.message_count", { value: formatRecordValue(channel.messages) }) }}</span></article></div>
  </section>
</template>
