<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useActivityStore } from "../../stores/activity.store";
import { t, useI18n } from "../../i18n";
import { logDetailRows, logEventTitle, parseLogEmbed } from "../../utils/logPresentation";
import LogEmbedCard from "./LogEmbedCard.vue";
import DiscordMentionText from "./DiscordMentionText.vue";

const activity = useActivityStore();
const { locale } = useI18n();
const logQuery = ref("");
const actorQuery = ref("");
const dateFrom = ref("");
const dateTo = ref("");
const source = ref("all");
const page = ref(0);
const pageSize = 20;
const totalPages = computed(() => Math.max(1, Math.ceil((activity.auditPage?.total ?? 0) / pageSize)));
const streamCount = computed(() => combinedRows.value.length);
const auditCount = computed(() => activity.auditPage?.total ?? 0);
const sourceOptions = computed(() => ["all", "moderator", "welcome", "message", "channel", "activity"].map((key) => ({ value: key === "message" ? "messages" : key, label: t(`logs.${key}`) })));
const combinedRows = computed(() => [
  ...(activity.logs?.audit || []).map((row) => ({ ...row, source: "audit" })),
  ...(activity.logs?.messages || []).map((row) => ({ ...row, source: "message" })),
]);

async function loadAudit() {
  await activity.loadLogs(source.value, "", logQuery.value);
  await activity.loadAuditPage({
    q: logQuery.value,
    actor: actorQuery.value,
    date_from: dateFrom.value,
    date_to: dateTo.value,
    limit: pageSize,
    offset: page.value * pageSize,
  });
}

async function applyFilters() {
  page.value = 0;
  await loadAudit();
}

async function goPage(delta: number) {
  page.value = Math.min(Math.max(page.value + delta, 0), totalPages.value - 1);
  await loadAudit();
}

function actorLabel(row: Record<string, unknown>) {
  return String(row.actor_name || row.author_name || row.actor_id || row.author_id || t("logs.system"));
}

function timeLabel(value: unknown) {
  const raw = String(value || "");
  if (!raw) return t("dashboard.recent");
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString(locale.value === "ru" ? "ru-RU" : "en-US");
}

function embedFor(row: Record<string, unknown>) {
  return parseLogEmbed(row.details ?? row.content);
}

onMounted(() => {
  void loadAudit();
});
</script>

<template>
  <section class="panel-section module-intro">
    <div class="section-heading">
      <span>{{ $t("module.logs") }}</span>
      <h2>{{ $t("logs.heading") }}</h2>
      <div>
        <p>{{ $t("logs.description") }}</p>
      </div>
    </div>
  </section>

  <section class="panel-section logs-filter-panel">
    <form class="module-toolbar" @submit.prevent="applyFilters">
      <input v-model="logQuery" :placeholder="$t('logs.search')" />
      <select v-model="actorQuery">
        <option value="">{{ $t("logs.all_users") }}</option>
        <option v-for="actor in activity.logActors" :key="actor.id" :value="actor.id">
          {{ actor.name }} ({{ actor.id }})
        </option>
      </select>
      <select v-model="source">
        <option v-for="option in sourceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <input v-model="dateFrom" type="datetime-local" />
      <input v-model="dateTo" type="datetime-local" />
      <button class="primary-button" type="submit">{{ $t("logs.apply") }}</button>
    </form>
  </section>

  <section class="panel-section module-content-panel logs-content-panel">
    <header class="logs-content-header">
      <div><span>{{ $t("logs.stream_eyebrow") }}</span><h3>{{ $t("logs.stream_heading") }}</h3><p>{{ $t("logs.stream_description") }}</p></div>
      <div class="logs-count"><span class="health-live-dot" /><strong>{{ $t("logs.stream_count", { count: streamCount }) }}</strong><small>{{ $t("logs.live") }}</small></div>
    </header>
    <div v-if="combinedRows.length" class="record-list compact-list log-feed-list">
      <article v-for="row in combinedRows" :key="`log-${row.source}-${row.id}`" class="log-record">
          <strong>{{ logEventTitle(row.event_type) }}</strong>
          <span>{{ actorLabel(row) }}</span>
          <LogEmbedCard v-if="embedFor(row)" :embed="embedFor(row)!" />
          <dl v-if="!embedFor(row)" class="log-detail-list">
          <div v-for="detail in logDetailRows(row)" :key="detail.key">
            <dt>{{ detail.label }}</dt>
            <dd><DiscordMentionText :text="detail.value" /></dd>
          </div>
        </dl>
        <small>{{ timeLabel(row.created_at) }}</small>
      </article>
    </div>

    <header class="logs-content-header audit-history-header">
      <div><span>{{ $t("logs.history_eyebrow") }}</span><h3>{{ $t("logs.history_heading") }}</h3></div>
      <strong>{{ auditCount }}</strong>
    </header>
    <div v-if="activity.auditPage?.items?.length" class="record-list log-feed-list">
      <article v-for="row in activity.auditPage?.items || []" :key="`audit-${row.id}`" class="log-record">
          <strong>{{ logEventTitle(row.event_type) }}</strong>
          <span>{{ actorLabel(row as unknown as Record<string, unknown>) }}</span>
          <LogEmbedCard v-if="embedFor(row as unknown as Record<string, unknown>)" :embed="embedFor(row as unknown as Record<string, unknown>)!" />
          <dl v-if="!embedFor(row as unknown as Record<string, unknown>)" class="log-detail-list">
          <div v-for="detail in logDetailRows(row as unknown as Record<string, unknown>)" :key="detail.key">
            <dt>{{ detail.label }}</dt>
            <dd><DiscordMentionText :text="detail.value" /></dd>
          </div>
        </dl>
        <small>{{ timeLabel(row.created_at) }}</small>
      </article>
    </div>
    <p v-else class="logs-empty-state">{{ $t("logs.empty") }}</p>
    <div class="pagination-row">
      <button class="ghost-button compact" type="button" :disabled="page === 0" @click="goPage(-1)">{{ $t("logs.previous") }}</button>
      <span>{{ page + 1 }} / {{ totalPages }}</span>
      <button class="ghost-button compact" type="button" :disabled="page + 1 >= totalPages" @click="goPage(1)">{{ $t("logs.next") }}</button>
    </div>
  </section>
</template>
