import { defineStore } from "pinia";
import { DiscordSDK } from "@discord/embedded-app-sdk";
import type { CommandResponse } from "@discord/embedded-app-sdk";
import {
  createActivityAccessRole,
  exchangeDiscordCode,
  createDevBlogPost,
  deleteActivityAccessRole,
  deleteCreatorAlertSource,
  deleteVoiceRoom,
  getActivityAudit,
  getAiModeratorSettings,
  getAiModeratorMetrics,
  getAiModeratorReviews,
  getAiModeratorReviewAudit,
  getMediaPolicy,
  getActivityDashboard,
  getActivityHealth,
  getActivityRoles,
  getActivitySession,
  getAccessControlData,
  getBotSettings,
  getChannelPurposes,
  getCreatorAlertSources,
  getDevBlogPosts,
  getDiscordChannels,
  getDiscordMembers,
  getDiscordRoles,
  getIntegrations,
  getLogActors,
  getLogs,
  getRolePanelsData,
  getServerStats,
  getVoiceRooms,
  getWelcomeConfig,
  previewCreatorAlert,
  resetWelcomeConfig,
  saveActivityRole,
  saveAiModeratorChannels,
  saveAiModeratorPolicy,
  saveAiModeratorReview,
  saveMediaPolicy,
  resetMediaPolicy,
  simulateAiModerator,
  saveActivityAccessRoleModules,
  saveActivitySyncedRoleAssignments,
  saveChannelPurpose,
  saveCreatorAlertSource,
  saveWelcomeConfig,
  searchUserStats,
  syncActivityRoles,
  testWelcomeConfig,
  updateVoiceRoom,
} from "../api/activity.api";
import { ApiError } from "../api/client";
import {
  administratorPermissions,
  healthSignals as mockHealthSignals,
  mockIntegrations,
  mockWelcome,
} from "./mock-data";
import type {
  ActivityHealth,
    AiModeratorSettings,
    AiModeratorMetrics,
  AiModerationReviewPage,
  AiModerationReviewAuditPage,
  AiModerationReviewItem,
  AiModerationSimulation,
  EffectiveMediaPolicy,
  ActivityAccessRole,
  ActivityAuditPage,
  ActivityDashboardResponse,
  ActivitySession,
  ActivityRolePurpose,
  ActivitySyncedRole,
  AccessLevel,
  AccessDeniedDetail,
  BotSettingsPayload,
  ChannelPurpose,
  CreatorAlertSource,
  DevBlogDraft,
  DiscordChannel,
  DiscordMember,
  DiscordRole,
  HealthSignal,
  LogActor,
  LogsPayload,
  ModuleKey,
  PanelSession,
  PermissionLevel,
  ServerStatsPayload,
  Theme,
  WelcomeConfig,
  VoiceRoom,
} from "../types/activity.types";
import { t } from "../i18n";

type Auth = CommandResponse<"authenticate">;

type State = {
  booted: boolean;
  loading: boolean;
  error: string | null;
  accessError: AccessDeniedDetail | null;
  mode: "local" | "discord";
  theme: Theme;
  token: string | null;
  session: PanelSession | null;
  welcome: WelcomeConfig;
  healthSignals: HealthSignal[];
  botLatencyMs: number | null;
  healthLoading: boolean;
  healthError: string | null;
  lastHealthRefresh: number;
  moduleLoading: boolean;
  moduleError: string | null;
  loadedModules: Partial<Record<ModuleKey, boolean>>;
  textChannels: DiscordChannel[];
  voiceChannels: DiscordChannel[];
  members: DiscordMember[];
  roles: DiscordRole[];
  channelPurposes: Partial<Record<ChannelPurpose, string>>;
  activityRoles: Partial<Record<ActivityRolePurpose, string>>;
  devBlogPosts: Array<Record<string, unknown>>;
  creatorSources: CreatorAlertSource[];
  creatorPreview: Record<string, unknown> | null;
  voiceRooms: VoiceRoom[];
  serverStats: ServerStatsPayload | null;
  userStatsResults: Array<Record<string, unknown>>;
  logs: LogsPayload | null;
  logActors: LogActor[];
  auditPage: ActivityAuditPage | null;
  dashboard: ActivityDashboardResponse | null;
  accessRoles: ActivityAccessRole[];
  syncedRoles: ActivitySyncedRole[];
  botSettings: BotSettingsPayload | null;
  integrations: Record<string, unknown> | null;
    aiModerator: AiModeratorSettings | null;
    aiModeratorMetrics: AiModeratorMetrics | null;
    aiModeratorReviews: AiModerationReviewPage | null;
    aiModeratorReviewAudit: AiModerationReviewAuditPage | null;
    aiModeratorSimulation: AiModerationSimulation | null;
    mediaPolicy: EffectiveMediaPolicy | null;
  discordSdk: DiscordSDK | null;
  auth: Auth | null;
};

export const useActivityStore = defineStore("activity", {
  state: (): State => ({
    booted: false,
    loading: false,
    error: null,
    accessError: null,
    mode: "local",
    theme: "dark",
    token: null,
    session: null,
    welcome: mockWelcome,
    healthSignals: mockHealthSignals,
    botLatencyMs: null,
    healthLoading: false,
    healthError: null,
    lastHealthRefresh: 0,
    moduleLoading: false,
    moduleError: null,
    loadedModules: {},
    textChannels: [],
    voiceChannels: [],
    members: [],
    roles: [],
    channelPurposes: {},
    activityRoles: {},
    devBlogPosts: [],
    creatorSources: [],
    creatorPreview: null,
    voiceRooms: [],
    serverStats: null,
    userStatsResults: [],
    logs: null,
    logActors: [],
    auditPage: null,
    dashboard: null,
    accessRoles: [],
    syncedRoles: [],
    botSettings: null,
    integrations: mockIntegrations,
      aiModerator: null,
      aiModeratorMetrics: null,
      aiModeratorReviews: null,
      aiModeratorReviewAudit: null,
      mediaPolicy: null,
      aiModeratorSimulation: null,
    discordSdk: null,
    auth: null,
  }),

  getters: {
    isAdmin: (state) => state.session?.access_level === "administrator",
    displayName: (state) =>
      state.session?.user.global_name || state.session?.user.username || "Omni user",
    availableModules: (state) => state.session?.available_modules ?? [],
  },

  actions: {
    async boot() {
      if (this.booted || this.loading) return;

      this.loading = true;
      this.error = null;
      this.accessError = null;

      try {
        if (!isDiscordActivityLaunch()) {
          this.rejectBrowserLaunch();
          return;
        }

        await this.bootDiscordActivity();
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error);
        if (error instanceof ApiError && error.status === 403) {
          this.accessError = normalizeAccessError(error.detail);
          this.session = null;
        }
      } finally {
        this.loading = false;
        this.booted = true;
      }
    },

    rejectBrowserLaunch() {
      this.mode = "local";
      this.token = null;
      this.auth = null;
      this.discordSdk = null;
      this.session = null;
      this.accessError = {
        code: "discord_activity_required",
        message: t("access.activity_only"),
        can_sync_roles: false,
      };
      this.error = this.accessError.message;
    },

    async bootDiscordActivity() {
      const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
      if (!clientId) {
        throw new Error("VITE_DISCORD_CLIENT_ID is required for Discord Activity launch.");
      }

      this.mode = "discord";
      const discordSdk = new DiscordSDK(clientId);
      this.discordSdk = discordSdk;
      await discordSdk.ready();

      const { code } = await discordSdk.commands.authorize({
        client_id: clientId,
        response_type: "code",
        state: "",
        prompt: "none",
        scope: ["identify", "guilds", "applications.commands"],
      });

      const token = await exchangeDiscordCode(code);
      this.token = token.access_token;
      this.auth = await discordSdk.commands.authenticate({
        access_token: token.access_token,
      });

      if (!this.auth) {
        throw new Error(t("access.authentication_failed"));
      }

      if (!discordSdk.guildId) {
        this.session = null;
        this.accessError = {
          code: "guild_required",
          message: t("access.guild_required"),
          can_sync_roles: false,
        };
        return;
      }

      const activitySession = await getActivitySession(discordSdk.guildId, token.access_token);
      this.session = toPanelSession(activitySession);
      this.accessError = null;

      if (this.session.is_admin) {
        this.welcome = await getWelcomeConfig(discordSdk.guildId, token.access_token);
      }

      await this.loadReferenceData();
      // The sidebar needs the backend-owned trusted-review flag before the
      // user opens any module, otherwise Review would appear only after a
      // detour through AI Moderator.
      if (this.can("ai-moderator")) {
        this.aiModerator = await getAiModeratorSettings(discordSdk.guildId, token.access_token);
      }
      await this.refreshHealth(true);
    },

    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
    },

    can(module: ModuleKey, level: PermissionLevel = "view") {
      const permission = this.session?.permissions[module] ?? "disabled";
      return permissionRank(permission) >= permissionRank(level);
    },

    async saveWelcome(next: WelcomeConfig) {
      const payload = this.session ? { ...next, guild_id: this.session.guild_id } : next;
      if (!this.token || this.mode === "local") {
        this.welcome = payload;
        return;
      }

      try {
        this.welcome = await saveWelcomeConfig(payload, this.token);
        this.moduleError = null;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async resetWelcome() {
      if (!this.session) return;

      if (!this.token || this.mode === "local") {
        this.welcome = { ...mockWelcome, guild_id: this.session.guild_id || mockWelcome.guild_id };
        return;
      }

      try {
        this.welcome = await resetWelcomeConfig(this.session.guild_id, this.token);
        this.moduleError = null;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async testWelcome() {
      if (!this.session || !this.token || this.mode === "local") return null;
      try {
        const result = await testWelcomeConfig(this.session.guild_id, this.token);
        this.moduleError = null;
        return result;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async refreshHealth(force = false) {
      if (!this.session) {
        this.lastHealthRefresh = Date.now();
        this.applyPreviewHealth();
        return;
      }
      if (!this.can("health")) return;

      const now = Date.now();
      if (!force && now - this.lastHealthRefresh < 10_000) {
        return;
      }

      if (!this.token || this.mode === "local") {
        this.lastHealthRefresh = now;
        this.applyPreviewHealth();
        return;
      }

      this.healthLoading = true;
      this.healthError = null;

      try {
        const health = await getActivityHealth(this.session.guild_id, this.token);
        this.applyHealth(health);
        this.lastHealthRefresh = Date.now();
      } catch (error) {
        this.healthError = error instanceof Error ? error.message : String(error);
      } finally {
        this.healthLoading = false;
      }
    },

    applyHealth(health: ActivityHealth) {
      this.healthSignals = health.signals;
      this.botLatencyMs = health.bot_latency_ms;
    },

    applyPreviewHealth() {
      // Preview intentionally exposes no fabricated latency; real measurements require a Discord session.
      this.healthSignals = mockHealthSignals.map((signal) => ({ ...signal, latency_ms: null }));
      this.botLatencyMs = null;
    },

    async loadReferenceData() {
      if (!this.session || !this.token || this.mode === "local") return;
      // Channel and member directories are administrative/statistical data.
      // Do not fetch them merely because a user can open the Activity.
      if (!this.isAdmin) return;
      const guildId = this.session.guild_id;
      const [textChannels, voiceChannels, members, channelPurposes] = await Promise.all([
        getDiscordChannels(guildId, this.token, "text"),
        getDiscordChannels(guildId, this.token, "voice"),
        getDiscordMembers(guildId, this.token),
        getChannelPurposes(guildId, this.token),
      ]);
      this.textChannels = textChannels;
      this.voiceChannels = voiceChannels;
      this.members = members;
      this.channelPurposes = channelPurposes;

      if (this.isAdmin) {
        const [roles, activityRoles] = await Promise.all([
          getDiscordRoles(guildId, this.token),
          getActivityRoles(guildId, this.token),
        ]);
        this.roles = roles;
        this.activityRoles = activityRoles;
      }
    },

    async loadModuleData(module: ModuleKey) {
      if (!this.session) {
        if (module === "integrations") this.integrations = mockIntegrations;
        if (module === "health") await this.refreshHealth(true);
        if (module === "integrations" || module === "health") this.loadedModules[module] = true;
        return;
      }
      if (!this.can(module)) return;
      if (!this.token || this.mode === "local") return;

      this.moduleLoading = true;
      this.moduleError = null;
      try {
        const guildId = this.session.guild_id;
        if (module === "dashboard") {
          await Promise.all([
            this.loadDashboard(),
            getServerStats(guildId, this.token).then((stats) => {
              this.serverStats = stats;
            }),
          ]);
        } else if (module === "welcome") {
          this.welcome = await getWelcomeConfig(guildId, this.token);
        } else if (module === "access") {
          await this.loadAccessControl();
        } else if (module === "role-panels") {
          await this.loadRolePanels();
        } else if (module === "dev-blog") {
          this.devBlogPosts = await getDevBlogPosts(guildId, this.token);
        } else if (module === "creator-alerts") {
          this.creatorSources = await getCreatorAlertSources(guildId, this.token);
        } else if (module === "voice-rooms") {
          this.voiceRooms = await getVoiceRooms(guildId, this.token);
        } else if (module === "server-stats") {
          this.serverStats = await getServerStats(guildId, this.token);
        } else if (module === "logs") {
          this.logs = await getLogs(guildId, this.token);
          this.logActors = await getLogActors(guildId, this.token);
        } else if (module === "bot-settings") {
          const settings = await getBotSettings(guildId, this.token);
          this.botSettings = settings;
          this.textChannels = settings.channels;
          this.roles = settings.roles;
          this.activityRoles = settings.activity_roles;
          this.channelPurposes = settings.channel_purposes;
        } else if (module === "ai-moderator") {
          [this.aiModerator, this.mediaPolicy] = await Promise.all([
            getAiModeratorSettings(guildId, this.token), getMediaPolicy(guildId, this.token),
          ]);
        } else if (module === "ai-review") {
          this.aiModerator = await getAiModeratorSettings(guildId, this.token);
        } else if (module === "integrations") {
          this.integrations = await getIntegrations(guildId, this.token);
        } else if (module === "health") {
          await this.refreshHealth(true);
        }
        this.loadedModules[module] = true;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        this.loadedModules[module] = false;
      } finally {
        this.moduleLoading = false;
      }
    },

    async saveActivityRolePurpose(purpose: ActivityRolePurpose, roleId: string) {
      if (!this.session || !this.token || this.mode === "local") {
        this.activityRoles[purpose] = roleId;
        return;
      }
      this.activityRoles = await saveActivityRole(this.session.guild_id, this.token, purpose, roleId);
    },

    async saveChannelPurposeValue(purpose: ChannelPurpose, channelId: string) {
      if (!this.session || !this.token || this.mode === "local") {
        this.channelPurposes[purpose] = channelId;
        return;
      }
      try {
        this.channelPurposes = await saveChannelPurpose(this.session.guild_id, this.token, purpose, channelId);
        this.moduleError = null;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async saveAiModeratorChannelValues(channelIds: string[]) {
      if (!this.session || !this.token || this.mode === "local") return;
      this.aiModerator = await saveAiModeratorChannels(this.session.guild_id, this.token, channelIds);
    },

    async saveAiModeratorPolicyValue(policy: Record<string, unknown>) {
      if (!this.session || !this.token || this.mode === "local") return;
      this.aiModerator = await saveAiModeratorPolicy(this.session.guild_id, this.token, policy);
    },
    async reloadMediaPolicy() {
      if (!this.session || !this.token || this.mode === "local") return;
      this.mediaPolicy = await getMediaPolicy(this.session.guild_id, this.token);
    },
    async saveMediaPolicyValue(media: EffectiveMediaPolicy["media"], expectedRevision: number) {
      if (!this.session || !this.token || this.mode === "local") return;
      await saveMediaPolicy(this.session.guild_id, this.token, expectedRevision, media);
      const verified = await getMediaPolicy(this.session.guild_id, this.token);
      if (verified.source !== "DATABASE" || verified.revision <= expectedRevision) {
        throw new Error("Saved media policy could not be verified");
      }
      this.mediaPolicy = verified;
    },
    async resetMediaPolicyValue(expectedRevision: number) {
      if (!this.session || !this.token || this.mode === "local") return;
      await resetMediaPolicy(this.session.guild_id, this.token, expectedRevision);
      const verified = await getMediaPolicy(this.session.guild_id, this.token);
      if (verified.source !== "YAML_DEFAULT") throw new Error("Media policy reset could not be verified");
      this.mediaPolicy = verified;
    },
    async loadAiModeratorMetrics() {
      if (!this.session || !this.token || this.mode === "local") return;
      this.aiModeratorMetrics = await getAiModeratorMetrics(this.session.guild_id, this.token);
    },
    async loadAiModeratorReviews(status: "OPEN" | "RESOLVED" = "OPEN", offset = 0) {
      if (!this.session || !this.token || this.mode === "local") return;
      this.aiModeratorReviews = await getAiModeratorReviews(this.session.guild_id, this.token, status, offset);
    },
    async loadAiModeratorReviewAudit(offset = 0) {
      if (!this.session || !this.token || this.mode === "local") return;
      this.aiModeratorReviewAudit = await getAiModeratorReviewAudit(this.session.guild_id, this.token, offset);
    },
    async saveAiModeratorReview(item: AiModerationReviewItem) {
      if (!this.session || !this.token || this.mode === "local") return;
      await saveAiModeratorReview(this.session.guild_id, this.token, item);
    },
    async simulateAiModerator(messageText: string) {
      if (!this.session || !this.token || this.mode === "local") return;
      this.aiModeratorSimulation = await simulateAiModerator(this.session.guild_id, this.token, messageText);
    },

    async createDevBlog(draft: Omit<DevBlogDraft, "guild_id">) {
      if (!this.session || !this.token) return;
      await createDevBlogPost({ ...draft, guild_id: this.session.guild_id }, this.token);
      await this.loadModuleData("dev-blog");
    },

    async saveCreatorSource(source: Omit<CreatorAlertSource, "guild_id">) {
      if (!this.session || !this.token) return;
      await saveCreatorAlertSource({ ...source, guild_id: this.session.guild_id }, this.token);
      await this.loadModuleData("creator-alerts");
    },

    async deleteCreatorSource(sourceId: number) {
      if (!this.session || !this.token) return;
      await deleteCreatorAlertSource(this.session.guild_id, sourceId, this.token);
      await this.loadModuleData("creator-alerts");
    },

    async previewCreatorSource(source: Omit<CreatorAlertSource, "guild_id">) {
      if (!this.session || !this.token) return;
      this.creatorPreview = await previewCreatorAlert({ ...source, guild_id: this.session.guild_id }, this.token);
    },

    async updateVoice(channelId: string, payload: Record<string, unknown>) {
      if (!this.session || !this.token) return;
      try {
        await updateVoiceRoom(this.session.guild_id, this.token, channelId, payload);
        await this.loadModuleData("voice-rooms");
        this.moduleError = null;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async deleteVoice(channelId: string) {
      if (!this.session || !this.token) return;
      try {
        await deleteVoiceRoom(this.session.guild_id, this.token, channelId);
        await this.loadModuleData("voice-rooms");
        this.moduleError = null;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async searchStatsUsers(query: string) {
      if (!this.session || !this.token || !query.trim()) {
        this.userStatsResults = [];
        return;
      }
      try {
        this.userStatsResults = await searchUserStats(this.session.guild_id, this.token, query.trim());
        this.moduleError = null;
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
        throw error;
      }
    },

    async loadLogs(source = "all", eventType = "", query = "") {
      if (!this.session || !this.token || this.mode === "local") return;
      this.logs = await getLogs(this.session.guild_id, this.token, source, eventType, query);
      if (!this.logActors.length) {
        this.logActors = await getLogActors(this.session.guild_id, this.token);
      }
    },

    async loadDashboard() {
      if (!this.session || !this.token || this.mode === "local") return;
      this.dashboard = await getActivityDashboard(this.session.guild_id, this.token);
      this.botLatencyMs = this.dashboard.metrics.bot_latency_ms;
      this.logs = {
        messages: this.logs?.messages ?? [],
        audit: this.dashboard.audit as unknown as Array<Record<string, unknown>>,
      };
    },

    async loadAuditPage(params: Record<string, string | number> = {}) {
      if (!this.session || !this.token || this.mode === "local") return;
      this.auditPage = await getActivityAudit(this.session.guild_id, this.token, {
        limit: 20,
        offset: 0,
        ...params,
      });
    },

    async loadAccessControl() {
      if (!this.session || !this.token || this.mode === "local") return;
      const data = await getAccessControlData(this.session.guild_id, this.token);
      this.accessRoles = data.access_roles;
    },

    async loadRolePanels() {
      if (!this.session || !this.token || this.mode === "local") return;
      const data = await getRolePanelsData(this.session.guild_id, this.token);
      this.accessRoles = data.access_roles;
      this.syncedRoles = data.synced_roles;
    },

    async syncRolesFromDiscord() {
      if (!this.token) return;
      const guildId = this.session?.guild_id || this.discordSdk?.guildId;
      if (!guildId || this.mode === "local") return;
      this.moduleLoading = true;
      this.moduleError = null;
      try {
        const result = await syncActivityRoles(guildId, this.token);
        this.syncedRoles = result.roles;
        const session = await getActivitySession(guildId, this.token);
        this.session = toPanelSession(session);
        this.accessError = null;
        await Promise.all([this.loadAccessControl(), this.loadDashboard()]);
      } catch (error) {
        this.moduleError = error instanceof Error ? error.message : String(error);
      } finally {
        this.moduleLoading = false;
      }
    },

    async createAccessRole(name: string) {
      if (!this.session || !this.token || this.mode === "local") return;
      await createActivityAccessRole(this.session.guild_id, this.token, name);
      await Promise.all([this.loadAccessControl(), this.loadRolePanels()]);
    },

    async deleteAccessRole(roleId: number) {
      if (!this.session || !this.token || this.mode === "local") return;
      await deleteActivityAccessRole(this.session.guild_id, this.token, roleId);
      await Promise.all([this.loadAccessControl(), this.loadRolePanels()]);
    },

    async saveAccessRoleModules(roleId: number, modules: Record<ModuleKey, PermissionLevel>) {
      if (!this.session || !this.token || this.mode === "local") return;
      const updated = await saveActivityAccessRoleModules(this.session.guild_id, this.token, roleId, modules);
      this.accessRoles = this.accessRoles.map((role) => (role.id === roleId ? updated : role));
      const session = await getActivitySession(this.session.guild_id, this.token);
      this.session = toPanelSession(session);
    },

    async saveSyncedRoleAssignments(discordRoleId: string, accessRoleIds: number[]) {
      if (!this.session || !this.token || this.mode === "local") return;
      const updated = await saveActivitySyncedRoleAssignments(this.session.guild_id, this.token, discordRoleId, accessRoleIds);
      this.syncedRoles = this.syncedRoles.map((role) => (role.role_id === discordRoleId ? updated : role));
    },
  },
});

function isDiscordActivityLaunch() {
  const params = new URLSearchParams(window.location.search);
  return params.has("frame_id") || params.has("instance_id");
}

function toPanelSession(session: ActivitySession): PanelSession {
  const accessLevel = session.access_level || resolveAccessLevel(session);
  const permissions = session.permissions || resolvePermissions(accessLevel);

  return {
    ...session,
    access_level: accessLevel,
    activity_roles: session.activity_roles || [accessLevel],
    permissions,
    available_modules: session.available_modules || Object.entries(permissions)
      .filter(([, permission]) => permission !== "disabled")
      .map(([module]) => module as ModuleKey),
  };
}

function normalizeAccessError(detail: unknown): AccessDeniedDetail {
  if (detail && typeof detail === "object" && "code" in detail && "message" in detail) {
    return detail as AccessDeniedDetail;
  }
  return {
    code: "access_denied",
    message: typeof detail === "string" ? detail : "Activity access is denied.",
    can_sync_roles: false,
  };
}

function resolveAccessLevel(session: ActivitySession): AccessLevel {
  if (session.is_admin) return "administrator";
  if (session.access.is_developer) return "developer";
  if (session.access.is_streamer) return "creator";
  return "ordinary";
}

function resolvePermissions(level: AccessLevel): Record<ModuleKey, PermissionLevel> {
  if (level === "administrator") return administratorPermissions;

  const permissions = emptyPermissions();
  permissions.dashboard = "view";
  permissions.health = "view";

  if (level === "developer") {
    permissions["dev-blog"] = "publish";
  }

  if (level === "creator") {
    permissions["creator-alerts"] = "edit";
  }

  if (level === "moderator") {
    permissions["ai-moderator"] = "view";
    permissions.logs = "view";
  }

  return permissions;
}

function emptyPermissions(): Record<ModuleKey, PermissionLevel> {
  return {
    dashboard: "disabled",
    access: "disabled",
    welcome: "disabled",
    "role-panels": "disabled",
    "creator-alerts": "disabled",
    "dev-blog": "disabled",
    "ai-moderator": "disabled",
    "ai-review": "disabled",
    logs: "disabled",
    "server-stats": "disabled",
    "voice-rooms": "disabled",
    "bot-settings": "disabled",
    integrations: "disabled",
    health: "disabled",
  };
}

function permissionRank(permission: PermissionLevel) {
  return {
    disabled: 0,
    view: 1,
    edit: 2,
    publish: 3,
    manage: 4,
  }[permission];
}
