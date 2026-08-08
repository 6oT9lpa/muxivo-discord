<script setup lang="ts">
import { reactive, watch } from "vue";
import { useActivityStore } from "../../stores/activity.store";
import type { WelcomeConfig } from "../../types/activity.types";
import DiscordEmbedPreview from "./DiscordEmbedPreview.vue";
import { t } from "../../i18n";

const activity = useActivityStore();
const welcomeDraft = reactive<WelcomeConfig>({ ...activity.welcome });
const saving = reactive({ value: false, message: "" });

watch(
  () => activity.welcome,
  (next) => Object.assign(welcomeDraft, next),
  { deep: true },
);

async function saveWelcome() {
  saving.value = true;
  saving.message = t("common.saving");
  try {
    await activity.saveWelcome({ ...welcomeDraft });
    saving.message = t("common.saved");
  } catch (error) {
    saving.message = error instanceof Error ? error.message : t("welcome.save_failed");
  } finally {
    saving.value = false;
  }
}

async function resetWelcome() {
  try {
    await activity.resetWelcome();
    Object.assign(welcomeDraft, activity.welcome);
    saving.message = t("welcome.reset_complete");
  } catch (error) {
    saving.message = error instanceof Error ? error.message : t("welcome.reset_failed");
  }
}

async function testWelcome() {
  saving.value = true;
  saving.message = t("welcome.sending_test");
  try {
    await activity.testWelcome();
    saving.message = t("welcome.test_sent");
  } catch (error) {
    saving.message = error instanceof Error ? error.message : t("welcome.test_failed");
  } finally {
    saving.value = false;
  }
}

function colorToHex(value: number) {
  return `#${value.toString(16).padStart(6, "0").slice(-6)}`;
}

function setColor(value: string) {
  welcomeDraft.color = parseInt(value.replace("#", ""), 16);
}
</script>

<template>
  <section class="editor-grid preview-editor-grid">
    <form class="control-surface" @submit.prevent="saveWelcome">
      <div class="section-heading">
        <span>{{ $t("module.welcome") }}</span>
        <h2>{{ $t("welcome.heading") }}</h2>
        <div>
          <p>{{ $t("welcome.description") }}</p>
        </div>
      </div>

      <label>
        {{ $t("welcome.title") }}
        <input v-model="welcomeDraft.title" maxlength="256" />
      </label>

      <label>
        {{ $t("welcome.message") }}
        <textarea v-model="welcomeDraft.description" rows="7" maxlength="2000" />
      </label>

      <div class="form-grid">
        <label>
          {{ $t("welcome.color") }}
          <input type="color" :value="colorToHex(welcomeDraft.color)" @input="setColor(($event.target as HTMLInputElement).value)" />
        </label>
        <label>
          {{ $t("welcome.rules_channel") }}
          <select v-model="welcomeDraft.rules_channel_id">
            <option :value="null">{{ $t("welcome.not_selected") }}</option>
            <option v-for="channel in activity.textChannels" :key="channel.id" :value="channel.id">
              #{{ channel.name }}
            </option>
          </select>
        </label>
        <label>
          {{ $t("welcome.roles_channel") }}
          <select v-model="welcomeDraft.roles_channel_id">
            <option :value="null">{{ $t("welcome.not_selected") }}</option>
            <option v-for="channel in activity.textChannels" :key="channel.id" :value="channel.id">
              #{{ channel.name }}
            </option>
          </select>
        </label>
        <label>
          {{ $t("welcome.footer") }}
          <input v-model="welcomeDraft.footer_text" placeholder="Muxivo DS Activity" />
        </label>
        <label>
          {{ $t("welcome.thumbnail_url") }}
          <input v-model="welcomeDraft.thumbnail_url" maxlength="2048" placeholder="https://..." />
        </label>
        <label>
          {{ $t("welcome.footer_icon_url") }}
          <input v-model="welcomeDraft.footer_icon_url" maxlength="2048" placeholder="https://..." />
        </label>
      </div>

      <div class="variable-row">
        <span>{user}</span>
        <span>{server}</span>
        <span>{member_count}</span>
        <span>{joined_at}</span>
        <span>{channel.ID}</span>
        <span>{role.ID}</span>
        <span>{user.ID}</span>
      </div>

      <div class="form-actions">
        <button class="primary-button" type="submit" :disabled="saving.value">{{ $t("common.save") }}</button>
        <button class="ghost-button" type="button" @click="resetWelcome">{{ $t("common.reset") }}</button>
        <button class="ghost-button" type="button" :disabled="saving.value" @click="testWelcome">{{ $t("common.test") }}</button>
        <small>{{ saving.message }}</small>
      </div>
    </form>

    <DiscordEmbedPreview class="sticky-preview" :config="welcomeDraft" />
  </section>
</template>
