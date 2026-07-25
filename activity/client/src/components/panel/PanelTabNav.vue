<script setup lang="ts">
type PanelTab = {
  key: string;
  label: string;
};

defineProps<{
  tabs: PanelTab[];
  modelValue: string;
  ariaLabel: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
}>();
</script>

<template>
  <nav class="panel-tab-nav" role="tablist" :aria-label="ariaLabel">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      :class="{ active: modelValue === tab.key }"
      type="button"
      role="tab"
      :aria-selected="modelValue === tab.key"
      @click="emit('update:modelValue', tab.key)"
    >
      <span>{{ tab.label }}</span>
    </button>
  </nav>
</template>
