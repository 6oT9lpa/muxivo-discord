<script setup lang="ts">
import { CircleAlert, CircleCheck, CircleX, Gauge, RefreshCw } from "@lucide/vue";
import { computed, nextTick, ref } from "vue";
import { useActivityStore } from "../../stores/activity.store";
import { t } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";

const activity = useActivityStore();
const activeSignal = ref<string | null>(null);
const operationalCount = computed(() => activity.healthSignals.filter((signal) => signal.status === "operational").length);

async function refreshHealth(signalName?: string) {
  activeSignal.value = null;
  await nextTick();
  activeSignal.value = signalName || "all";
  clientLogger.info("health_status_refresh_requested", { signal: signalName || "all" });
  try {
    await activity.refreshHealth(true);
  } finally {
    window.setTimeout(() => {
      activeSignal.value = null;
    }, 620);
  }
}

function signalName(name: string) {
  const keys: Record<string, string> = {
    "Bot latency": "health.bot_latency",
    PostgreSQL: "health.postgresql",
    "Muxivo Core": "health.muxivo_core",
    "AI Classifier": "health.ai_classifier",
    "Stream platform polling": "health.stream_polling",
    "Stream Checker": "health.stream_checker",
  };
  return keys[name] ? t(keys[name]) : name;
}

function signalValue(name: string, value: string, latency?: number | null) {
  if (value === "Unavailable") return t("dashboard.unavailable");
  if (name === "Stream platform polling" && latency !== null && latency !== undefined) return t("health.every_seconds", { seconds: latency });
  return value;
}

function signalMetric(name: string, latency?: number | null) {
  // Latency appears only when it came from an authenticated, real health probe.
  if (latency === null || latency === undefined) return null;
  if (name === "Stream platform polling") return t("health.every_seconds", { seconds: latency });
  return t("health.ping", { value: latency });
}

function statusIcon(status: "operational" | "degraded" | "offline") {
  return status === "operational" ? CircleCheck : status === "degraded" ? CircleAlert : CircleX;
}
</script>

<template>
  <section class="health-status-panel panel-section">
    <header class="health-status-hero">
      <div>
        <span>{{ $t("module.health") }}</span>
        <h2>{{ $t("health.heading") }}</h2>
        <p>{{ $t("health.description") }}</p>
      </div>
      <div class="health-status-summary"><span class="health-live-dot" /><strong>{{ $t("health.operational_count", { count: operationalCount }) }}</strong><small>{{ $t("health.updated_now") }}</small></div>
    </header>

    <div class="health-grid health-status-grid">
      <button
        v-for="signal in activity.healthSignals"
        :key="signal.name"
        type="button"
        :class="['health-card', signal.status, { refreshing: activity.healthLoading, 'is-selected': activeSignal === signal.name || activeSignal === 'all' }]"
        @click="refreshHealth(signal.name)"
      >
        <div class="health-card-head"><span class="health-status-icon"><component :is="statusIcon(signal.status)" :size="19" /></span><small>{{ activity.healthLoading ? $t("health.refreshing") : $t(`health.${signal.status}`) }}</small></div>
        <span>{{ signalName(signal.name) }}</span>
        <strong>{{ signalValue(signal.name, signal.value, signal.latency_ms) }}</strong>
        <footer>
          <span v-if="signalMetric(signal.name, signal.latency_ms)" class="health-card-metric"><Gauge :size="14" />{{ signalMetric(signal.name, signal.latency_ms) }}</span>
          <span class="health-card-refresh"><RefreshCw :size="14" /><small>{{ $t("health.refresh_signal") }}</small></span>
        </footer>
      </button>
    </div>
  </section>
</template>
