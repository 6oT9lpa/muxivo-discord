<script setup lang="ts">
import { Bot, LockKeyhole, ShieldCheck } from "@lucide/vue";

defineProps<{
  title?: string;
  text?: string;
  actionLabel?: string;
  busy?: boolean;
  guidance?: boolean;
}>();

defineEmits<{
  action: [];
}>();
</script>

<template>
  <section :class="['no-access-state', { 'is-guided': guidance }]">
    <div class="access-state-shell">
      <div class="access-state-glow" aria-hidden="true" />
      <div class="access-state-visual" aria-hidden="true">
        <span class="access-state-orbit orbit-one" />
        <span class="access-state-orbit orbit-two" />
        <div class="state-icon"><LockKeyhole :size="24" /></div>
      </div>
      <div class="access-state-copy">
        <span v-if="guidance" class="access-state-kicker"><ShieldCheck :size="15" /> {{ $t("access.gateway") }}</span>
        <h2>{{ title || $t("access.no_module") }}</h2>
        <p>{{ text || $t("access.admin_can_grant") }}</p>
      </div>

      <div v-if="guidance" class="access-guide" :aria-label="$t('access.guide_aria')">
        <article class="access-guide-step">
          <span>01</span>
          <Bot :size="18" />
          <div><strong>{{ $t("access.step_open_title") }}</strong><p>{{ $t("access.step_open_text") }}</p></div>
        </article>
        <article class="access-guide-step">
          <span>02</span>
          <ShieldCheck :size="18" />
          <div><strong>{{ $t("access.step_server_title") }}</strong><p>{{ $t("access.step_server_text") }}</p></div>
        </article>
        <article class="access-guide-step">
          <span>03</span>
          <LockKeyhole :size="18" />
          <div><strong>{{ $t("access.step_return_title") }}</strong><p>{{ $t("access.step_return_text") }}</p></div>
        </article>
      </div>

      <div class="access-state-actions">
        <button v-if="actionLabel" class="primary-button" type="button" :disabled="busy" @click="$emit('action')">
          {{ busy ? $t("access.syncing") : actionLabel }}
        </button>
        <RouterLink class="secondary-link" to="/">{{ $t("access.back_to_muxivo") }}</RouterLink>
      </div>
    </div>
  </section>
</template>
