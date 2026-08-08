<script setup lang="ts">
import { Moon, Sun } from "@lucide/vue";
import { useActivityStore } from "../../stores/activity.store";
import AnimatedNavLink from "./AnimatedNavLink.vue";
import LanguageSwitcher from "./LanguageSwitcher.vue";

const activity = useActivityStore();
</script>

<template>
  <header class="app-header">
    <RouterLink class="wordmark" to="/" :aria-label="$t('header.home')">
      <img class="wordmark-logo" src="/muxivo-logo.png" alt="" />
      <span>
        <span class="wordmark-main">MUXIVO</span>
        <span class="wordmark-sub">{{ $t("header.discord_bot") }}</span>
      </span>
    </RouterLink>

    <nav class="public-nav" :aria-label="$t('header.primary_navigation')">
      <AnimatedNavLink to="/" :label="$t('header.we_are_muxivo')" />
      <AnimatedNavLink to="/about" :label="$t('header.get_to_know_us')" />
    </nav>

    <div class="header-actions">
      <LanguageSwitcher />
      <button class="icon-button" type="button" :title="$t('common.theme.toggle')" :aria-label="$t('common.theme.toggle')" @click="activity.toggleTheme()">
        <Sun v-if="activity.theme === 'dark'" :size="18" />
        <Moon v-else :size="18" />
      </button>
      <RouterLink class="panel-cta" to="/panel">
        {{ $t("header.see_panel") }}
      </RouterLink>
    </div>
  </header>
</template>
