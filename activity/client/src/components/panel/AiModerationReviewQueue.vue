<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useActivityStore } from "../../stores/activity.store";
import type { AiModerationAction, AiModerationReviewItem } from "../../types/activity.types";

const activity = useActivityStore();
const page = ref<"queue" | "audit">("queue");
const status = ref<"OPEN" | "RESOLVED">("OPEN");
const queueOffset = ref(0);
const auditOffset = ref(0);
const editing = ref<AiModerationReviewItem | null>(null);
const feedback = ref("");
const actions: AiModerationAction[] = ["IGNORE", "LOG", "REVIEW", "WARN", "DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"];
const queue = computed(() => activity.aiModeratorReviews);
const audit = computed(() => activity.aiModeratorReviewAudit);

onMounted(() => reloadQueue());

async function reloadQueue(offset = queueOffset.value) {
  queueOffset.value = Math.max(0, offset);
  try { await activity.loadAiModeratorReviews(status.value, queueOffset.value); feedback.value = ""; }
  catch (error) { feedback.value = error instanceof Error ? error.message : "Unable to load review queue"; }
}
async function reloadAudit(offset = auditOffset.value) {
  auditOffset.value = Math.max(0, offset);
  try { await activity.loadAiModeratorReviewAudit(auditOffset.value); feedback.value = ""; }
  catch (error) { feedback.value = error instanceof Error ? error.message : "Unable to load review history"; }
}
function open(item: AiModerationReviewItem) { editing.value = { ...item, labels: [...item.labels] }; feedback.value = ""; }
async function save() {
  if (!editing.value) return;
  try { await activity.saveAiModeratorReview(editing.value); feedback.value = "Decision saved"; await reloadQueue(); }
  catch (error) { feedback.value = error instanceof Error ? error.message : "Unable to save decision"; }
}
async function switchPage(value: "queue" | "audit") { page.value = value; if (value === "audit") await reloadAudit(); else await reloadQueue(); }
</script>

<template>
  <div class="ai-moderation-workspace review-queue">
    <div class="ai-moderation-section-copy"><div><span class="ai-moderation-kicker">TRUSTED MODERATION</span><h3>Review queue</h3><p>Correct model decisions before they become part of the moderation dataset.</p></div></div>
    <nav class="review-subnav"><button :class="{ active: page === 'queue' }" type="button" @click="switchPage('queue')">Queue</button><button :class="{ active: page === 'audit' }" type="button" @click="switchPage('audit')">Review log</button></nav>
    <p v-if="feedback" class="form-status">{{ feedback }}</p>
    <template v-if="page === 'queue'">
      <div class="review-toolbar"><label>Status <select v-model="status" @change="reloadQueue(0)"><option value="OPEN">Open</option><option value="RESOLVED">Resolved</option></select></label><span>{{ queue?.total ?? 0 }} decisions</span></div>
      <div v-if="queue?.items.length" class="review-list"><article v-for="item in queue.items" :key="item.id" class="review-card"><header><strong>#{{ item.id }} · {{ item.action }}</strong><span>{{ item.risk_score }}/100 · severity {{ item.severity }}</span></header><p class="review-message">{{ item.message_text }}</p><small>Labels: {{ item.labels.join(', ') || 'SAFE' }} · Message {{ item.message_id }}</small><button class="ghost-button" type="button" @click="open(item)">Edit decision</button></article></div>
      <div v-else class="ai-empty-state"><span>No review decisions on this page.</span></div>
      <div class="form-actions"><button class="ghost-button" :disabled="queueOffset === 0" type="button" @click="reloadQueue(queueOffset - 20)">Previous</button><button class="ghost-button" :disabled="!queue || queueOffset + queue.limit >= queue.total" type="button" @click="reloadQueue(queueOffset + 20)">Next</button></div>
      <form v-if="editing" class="review-editor" @submit.prevent="save"><h4>Edit decision #{{ editing.id }}</h4><label>Message<textarea v-model.trim="editing.message_text" maxlength="8000" required /></label><div class="ai-policy-controls"><label>Risk <input v-model.number="editing.risk_score" type="number" min="0" max="100" step="0.1" /></label><label>Severity <input v-model.number="editing.severity" type="number" min="0" max="5" /></label><label>Action <select v-model="editing.action"><option v-for="action in actions" :key="action" :value="action">{{ action }}</option></select></label><label>Status <select v-model="editing.status"><option value="OPEN">Open</option><option value="RESOLVED">Resolved</option></select></label></div><div class="form-actions"><button class="primary-button" type="submit">Save correction</button><button class="ghost-button" type="button" @click="editing = null">Close</button></div></form>
    </template>
    <template v-else><div v-if="audit?.items.length" class="review-list"><article v-for="entry in audit.items" :key="entry.id" class="review-card"><header><strong>{{ entry.action }} · review #{{ entry.review_item_id }}</strong><span>{{ new Date(entry.created_at).toLocaleString() }}</span></header><p>Moderator: {{ entry.actor_id }} · message {{ entry.message_id }}</p><small>Before: {{ JSON.stringify(entry.before_json) }}<br />After: {{ JSON.stringify(entry.after_json) }}</small></article></div><div v-else class="ai-empty-state"><span>No review history yet.</span></div><div class="form-actions"><button class="ghost-button" :disabled="auditOffset === 0" type="button" @click="reloadAudit(auditOffset - 20)">Previous</button><button class="ghost-button" :disabled="!audit || auditOffset + audit.limit >= audit.total" type="button" @click="reloadAudit(auditOffset + 20)">Next</button></div></template>
  </div>
</template>
