<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { ChevronDown, Search, X } from "@lucide/vue";

export type SearchableSelectorOption = {
  id: string;
  label: string;
  search: string;
};

const props = withDefaults(defineProps<{
  options: SearchableSelectorOption[];
  triggerLabel: string;
  searchPlaceholder: string;
  emptyLabel: string;
  ariaLabel: string;
  limit?: number;
}>(), { limit: 25 });

const emit = defineEmits<{
  select: [id: string];
}>();

const isOpen = ref(false);
const query = ref("");
const input = ref<HTMLInputElement | null>(null);
const matches = computed(() => {
  const normalized = query.value.trim().toLocaleLowerCase();
  return props.options
    .filter((option) => option.search.toLocaleLowerCase().includes(normalized))
    .slice(0, props.limit);
});

async function open() {
  isOpen.value = true;
  await nextTick();
  input.value?.focus();
}

function close() {
  query.value = "";
  isOpen.value = false;
}

function select(option: SearchableSelectorOption) {
  emit("select", option.id);
  close();
}
</script>

<template>
  <div class="searchable-selector" @keydown.esc="close">
    <button v-if="!isOpen" class="searchable-selector-trigger" type="button" :aria-label="ariaLabel" @click="open">
      <span>{{ triggerLabel }}</span><ChevronDown :size="15" />
    </button>
    <div v-else class="searchable-selector-popover">
      <div class="searchable-selector-search"><Search :size="15" /><input ref="input" v-model="query" type="search" :placeholder="searchPlaceholder" /><button type="button" :aria-label="ariaLabel" @click="close"><X :size="15" /></button></div>
      <div class="searchable-selector-options" role="listbox" :aria-label="ariaLabel">
        <button v-for="option in matches" :key="option.id" type="button" role="option" @click="select(option)"><span>{{ option.label }}</span><small>{{ option.id }}</small></button>
        <p v-if="!matches.length">{{ emptyLabel }}</p>
      </div>
    </div>
  </div>
</template>
