<script setup lang="ts">
import { onMounted } from "vue";
import { useActivityStore } from "./stores/activity.store";
import AppHeader from "./components/common/AppHeader.vue";
import PublicFooter from "./components/common/PublicFooter.vue";
import LoadingState from "./components/common/LoadingState.vue";

const activity = useActivityStore();

onMounted(() => {
  void activity.boot();
});
</script>

<template>
  <div :class="['muxivo-app', `theme-${activity.theme}`]">
    <LoadingState v-if="activity.loading && !activity.booted" :title="$t('app.starting')" :text="$t('app.preparing')" />
    <template v-else>
      <AppHeader v-if="!$route.path.startsWith('/panel')" />
      <RouterView />
      <PublicFooter v-if="!$route.path.startsWith('/panel')" />
    </template>
  </div>
</template>
