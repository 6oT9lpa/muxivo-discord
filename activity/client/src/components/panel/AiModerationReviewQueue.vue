<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ClipboardCheck, Clock3, PencilLine, ShieldCheck } from "@lucide/vue";
import { useActivityStore } from "../../stores/activity.store";
import type { AiModerationAction, AiModerationReviewItem } from "../../types/activity.types";
import { t, useI18n } from "../../i18n";
import PanelTabNav from "./PanelTabNav.vue";

const activity = useActivityStore();
const { locale } = useI18n();
const page = ref<"queue" | "audit">("queue");
const status = ref<"OPEN" | "RESOLVED">("OPEN");
const queueOffset = ref(0);
const auditOffset = ref(0);
const editing = ref<AiModerationReviewItem | null>(null);
const feedback = ref("");
const actions: AiModerationAction[] = ["IGNORE", "LOG", "REVIEW", "WARN", "DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"];
const queue = computed(() => activity.aiModeratorReviews);
const audit = computed(() => activity.aiModeratorReviewAudit);
const tabs = computed(() => [
  { key: "queue", label: t("review.queue") },
  { key: "audit", label: t("review.audit") },
]);

onMounted(() => void reloadQueue());

async function reloadQueue(offset = queueOffset.value) {
  queueOffset.value = Math.max(0, offset);
  try { await activity.loadAiModeratorReviews(status.value, queueOffset.value); feedback.value = ""; }
  catch (error) { feedback.value = error instanceof Error ? error.message : t("review.queue_load_failed"); }
}

async function reloadAudit(offset = auditOffset.value) {
  auditOffset.value = Math.max(0, offset);
  try { await activity.loadAiModeratorReviewAudit(auditOffset.value); feedback.value = ""; }
  catch (error) { feedback.value = error instanceof Error ? error.message : t("review.audit_load_failed"); }
}

function open(item: AiModerationReviewItem) {
  editing.value = { ...item, labels: [...item.labels] };
  feedback.value = "";
}

async function save() {
  if (!editing.value) return;
  try {
    await activity.saveAiModeratorReview(editing.value);
    feedback.value = t("review.saved");
    await reloadQueue();
  } catch (error) {
    feedback.value = error instanceof Error ? error.message : t("review.save_failed");
  }
}

async function switchPage(value: string) {
  const nextPage = value as "queue" | "audit";
  page.value = nextPage;
  if (nextPage === "audit") await reloadAudit();
  else await reloadQueue();
}

function itemLabels(item: AiModerationReviewItem) {
  return item.labels.join(", ") || t("review.safe");
}

function timeLabel(value: string) {
  return new Date(value).toLocaleString(locale.value === "ru" ? "ru-RU" : "en-US");
}
</script>

<template>
  <div class="review-workspace">
    <header class="review-hero">
      <div><span>{{ $t("review.eyebrow") }}</span><h3>{{ $t("review.heading") }}</h3><p>{{ $t("review.description") }}</p></div>
      <div class="review-hero-status"><ShieldCheck :size="17" /><strong>{{ queue?.total ?? 0 }}</strong><small>{{ $t("review.open_decisions") }}</small></div>
    </header>

    <PanelTabNav :model-value="page" :tabs="tabs" :aria-label="$t('review.heading')" @update:model-value="switchPage" />
    <p v-if="feedback" class="form-status">{{ feedback }}</p>

    <template v-if="page === 'queue'">
      <div class="review-toolbar"><label><span>{{ $t("review.status") }}</span><select v-model="status" @change="reloadQueue(0)"><option value="OPEN">{{ $t("review.open") }}</option><option value="RESOLVED">{{ $t("review.resolved") }}</option></select></label><span>{{ $t("review.decision_count", { count: queue?.total ?? 0 }) }}</span></div>
      <div v-if="queue?.items.length" class="review-list">
        <article v-for="item in queue.items" :key="item.id" class="review-card">
          <header><span class="review-card-icon"><ClipboardCheck :size="17" /></span><div><strong>{{ $t("review.decision", { id: item.id, action: item.action }) }}</strong><span>{{ $t("review.risk_severity", { risk: item.risk_score, severity: item.severity }) }}</span></div><button class="icon-button" type="button" :aria-label="$t('review.edit_decision')" :title="$t('review.edit_decision')" @click="open(item)"><PencilLine :size="16" /></button></header>
          <p class="review-message">{{ item.message_text }}</p>
          <footer><span>{{ $t("review.labels", { labels: itemLabels(item) }) }}</span><span>{{ $t("review.message", { id: item.message_id }) }}</span></footer>
        </article>
      </div>
      <div v-else class="ai-empty-state"><ClipboardCheck :size="22" /><span>{{ $t("review.empty_queue") }}</span></div>
      <div class="form-actions"><button class="ghost-button" :disabled="queueOffset === 0" type="button" @click="reloadQueue(queueOffset - 20)">{{ $t("logs.previous") }}</button><button class="ghost-button" :disabled="!queue || queueOffset + queue.limit >= queue.total" type="button" @click="reloadQueue(queueOffset + 20)">{{ $t("logs.next") }}</button></div>

      <form v-if="editing" class="review-editor" @submit.prevent="save">
        <header><div><span>{{ $t("review.editing") }}</span><h4>{{ $t("review.decision", { id: editing.id, action: editing.action }) }}</h4></div><button class="ghost-button compact" type="button" @click="editing = null">{{ $t("review.close") }}</button></header>
        <label><span>{{ $t("review.message_label") }}</span><textarea v-model.trim="editing.message_text" maxlength="8000" required /></label>
        <div class="ai-policy-controls"><label><span>{{ $t("review.risk") }}</span><input v-model.number="editing.risk_score" type="number" min="0" max="100" step="0.1" /></label><label><span>{{ $t("review.severity") }}</span><input v-model.number="editing.severity" type="number" min="0" max="5" /></label><label><span>{{ $t("review.action") }}</span><select v-model="editing.action"><option v-for="action in actions" :key="action" :value="action">{{ action }}</option></select></label><label><span>{{ $t("review.status") }}</span><select v-model="editing.status"><option value="OPEN">{{ $t("review.open") }}</option><option value="RESOLVED">{{ $t("review.resolved") }}</option></select></label></div>
        <div class="form-actions"><button class="primary-button" type="submit">{{ $t("review.save") }}</button></div>
      </form>
    </template>

    <template v-else>
      <div v-if="audit?.items.length" class="review-list">
        <article v-for="entry in audit.items" :key="entry.id" class="review-card review-audit-card">
          <header><span class="review-card-icon"><Clock3 :size="17" /></span><div><strong>{{ $t("review.audit_entry", { id: entry.review_item_id, action: entry.action }) }}</strong><span>{{ timeLabel(entry.created_at) }}</span></div></header>
          <p>{{ $t("review.moderator_message", { moderator: entry.actor_id, message: entry.message_id }) }}</p>
          <div class="review-change-grid"><div><span>{{ $t("logs.detail.before") }}</span><code>{{ JSON.stringify(entry.before_json) }}</code></div><div><span>{{ $t("logs.detail.after") }}</span><code>{{ JSON.stringify(entry.after_json) }}</code></div></div>
        </article>
      </div>
      <div v-else class="ai-empty-state"><Clock3 :size="22" /><span>{{ $t("review.empty_audit") }}</span></div>
      <div class="form-actions"><button class="ghost-button" :disabled="auditOffset === 0" type="button" @click="reloadAudit(auditOffset - 20)">{{ $t("logs.previous") }}</button><button class="ghost-button" :disabled="!audit || auditOffset + audit.limit >= audit.total" type="button" @click="reloadAudit(auditOffset + 20)">{{ $t("logs.next") }}</button></div>
    </template>
  </div>
</template>
