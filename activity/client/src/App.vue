<script setup lang="ts">
import { onMounted } from "vue";
import { useActivityStore } from "./stores/activity.store";
import AppHeader from "./components/common/AppHeader.vue";
import PublicFooter from "./components/common/PublicFooter.vue";
import LoadingState from "./components/common/LoadingState.vue";
import { consoleUrl } from "./utils/consoleUrl";
import { isDiscordActivityLaunch } from "./utils/launchContext";

const activity = useActivityStore();
const browserConsoleUrl = isDiscordActivityLaunch(window.location.search) ? null : consoleUrl();

onMounted(() => {
  if (browserConsoleUrl) {
    window.location.replace(browserConsoleUrl);
    return;
  }
  void activity.boot();
});
</script>

<template>
  <LoadingState
    v-if="browserConsoleUrl"
    :title="$t('app.starting')"
    :text="$t('app.preparing')"
  />
  <div v-else :class="['muxivo-app', `theme-${activity.theme}`]">
    <LoadingState v-if="activity.loading && !activity.booted" :title="$t('app.starting')" :text="$t('app.preparing')" />
    <main v-else-if="activity.error" class="startup-error" role="alert">
      <div>
        <span>{{ $t('app.connection_issue_eyebrow') }}</span>
        <h1>{{ $t('app.connection_issue_title') }}</h1>
        <p>{{ activity.error }}</p>
        <button class="primary-button" type="button" @click="activity.retryBoot()">{{ $t('app.retry_launch') }}</button>
      </div>
    </main>
    <template v-else>
      <AppHeader v-if="!$route.path.startsWith('/panel')" />
      <RouterView />
      <PublicFooter v-if="!$route.path.startsWith('/panel')" />
    </template>
  </div>
</template>
