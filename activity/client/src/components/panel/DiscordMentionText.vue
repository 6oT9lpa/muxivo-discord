<script setup lang="ts">
import { computed } from "vue";

type TextToken =
  | { kind: "text"; value: string }
  | { kind: "mention"; value: string; userId: string };

const props = defineProps<{
  text: string;
}>();

const tokens = computed<TextToken[]>(() => {
  const result: TextToken[] = [];
  const pattern = /<@!?(\d+)>\s*\(`?([^`)]*?)`?\s+ID:\s*\1\)|<@!?(\d+)>/g;
  let cursor = 0;

  for (const match of props.text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > cursor) result.push({ kind: "text", value: props.text.slice(cursor, index) });
    const userId = match[1] ?? match[3];
    const username = match[2]?.trim();
    result.push({ kind: "mention", value: `@${username || userId}`, userId });
    cursor = index + match[0].length;
  }

  if (cursor < props.text.length) result.push({ kind: "text", value: props.text.slice(cursor) });
  return result.length ? result : [{ kind: "text", value: props.text }];
});
</script>

<template>
  <template v-for="(token, index) in tokens" :key="index">
    <span v-if="token.kind === 'mention'" class="discord-mention" :title="token.userId">{{ token.value }}</span>
    <template v-else>{{ token.value }}</template>
  </template>
</template>
