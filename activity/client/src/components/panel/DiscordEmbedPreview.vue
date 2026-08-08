<script setup lang="ts">
import type { WelcomeConfig } from "../../types/activity.types";
import { t } from "../../i18n";
import AuthenticatedImage from "../common/AuthenticatedImage.vue";

const props = defineProps<{
  config: WelcomeConfig;
}>();

function hexColor(color: number) {
  return `#${color.toString(16).padStart(6, "0").slice(-6)}`;
}

function previewText(value: string) {
  return value
    .replaceAll("{user}", `@${t("welcome.preview_user")}`)
    .replaceAll("{username}", t("welcome.preview_user"))
    .replaceAll("{server}", t("welcome.preview_server"))
    .replaceAll("{guild}", t("welcome.preview_server"))
    .replaceAll("{member_count}", "1,248")
    .replaceAll("{joined_at}", t("welcome.preview_today"))
    .replaceAll("{rules}", "#rules")
    .replaceAll("{roles}", "#roles")
    .replace(/\{channel\.(\d{15,25})\}/g, "#$1")
    .replace(/\{role\.(\d{15,25})\}/g, "@role-$1")
    .replace(/\{user\.(\d{15,25})\}/g, "@user-$1");
}
</script>

<template>
  <article class="discord-preview" :style="{ borderColor: hexColor(props.config.color) }">
    <div class="discord-preview-header">
      <span>{{ $t("welcome.preview") }}</span>
      <strong>{{ $t(config.is_enabled ? "common.enabled" : "common.disabled") }}</strong>
    </div>
    <h3>{{ previewText(config.title) }}</h3>
    <p>{{ previewText(config.description) }}</p>
    <div class="preview-media" :class="{ 'has-image': config.thumbnail_url }">
      <AuthenticatedImage
        v-if="config.thumbnail_url"
        :src="config.thumbnail_url"
        :alt="$t('welcome.preview_image_alt')"
      />
      <span v-else>{{ $t("welcome.thumbnail_area") }}</span>
    </div>
    <footer>
      <span>{{ previewText(config.footer_text || "Muxivo DS Activity") }}</span>
      <AuthenticatedImage
        v-if="config.footer_icon_url"
        class="preview-footer-icon"
        :src="config.footer_icon_url"
        :alt="$t('welcome.preview_footer_icon_alt')"
      />
      <span v-else>{{ hexColor(config.color) }}</span>
    </footer>
  </article>
</template>
