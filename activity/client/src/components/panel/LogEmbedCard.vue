<script setup lang="ts">
import type { LogEmbed } from "../../utils/logPresentation";

defineProps<{
  embed: LogEmbed;
}>();
</script>

<template>
  <div class="log-embed-card" :style="embed.color ? { '--log-embed-accent': embed.color } : undefined">
    <div v-if="embed.title" class="log-embed-title">{{ embed.title }}</div>
    <p v-if="embed.content" class="log-embed-content">{{ embed.content }}</p>
    <p v-if="embed.description" class="log-embed-description">{{ embed.description }}</p>
    <div v-if="embed.before || embed.after" class="log-embed-diff">
      <div v-if="embed.before"><span>{{ $t("logs.detail.before") }}</span><code>{{ embed.before }}</code></div>
      <div v-if="embed.after"><span>{{ $t("logs.detail.after") }}</span><code>{{ embed.after }}</code></div>
    </div>
    <dl v-if="embed.fields.length" class="log-embed-fields">
      <div v-for="field in embed.fields" :key="`${field.name}-${field.value}`" :class="{ inline: field.inline }">
        <dt>{{ field.name }}</dt>
        <dd>{{ field.value }}</dd>
      </div>
    </dl>
    <footer v-if="embed.footer">{{ embed.footer }}</footer>
  </div>
</template>
