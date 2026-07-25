import { apiRequest } from "./client";
import type {
  ActivityHealth,
  AiModeratorSettings,
  AiModeratorMetrics,
  AiModerationReviewPage,
  AiModerationReviewAuditPage,
  AiModerationReviewItem,
  AiModerationSimulation,
  ActivityAccessRole,
  ActivityAuditPage,
  ActivityDashboardResponse,
  ActivityRoleSyncResponse,
  ActivityRolePurpose,
  ActivitySession,
  ActivitySyncedRole,
  BotSettingsPayload,
  ChannelPurpose,
  CreatorAlertSource,
  DevBlogDraft,
  DiscordChannel,
  DiscordMember,
  DiscordRole,
  LogActor,
  LogsPayload,
  ServerStatsPayload,
  TokenResponse,
  VoiceRoom,
  WelcomeConfig,
} from "../types/activity.types";

export function getAiModeratorSettings(guildId: string, token: string) {
  return apiRequest<AiModeratorSettings>(`/api/ai-moderator/settings?guild_id=${guildId}`, {}, token);
}

export function getAiModeratorMetrics(guildId: string, token: string) {
  return apiRequest<AiModeratorMetrics>(`/api/ai-moderator/metrics?guild_id=${guildId}`, {}, token);
}

export function saveAiModeratorChannels(guildId: string, token: string, channelIds: string[]) {
  // Discord snowflakes exceed JavaScript's safe integer range; keep them as strings in JSON.
  return apiRequest<AiModeratorSettings>("/api/ai-moderator/channels", { method: "PUT", body: JSON.stringify({ guild_id: guildId, channel_ids: channelIds }) }, token);
}

export function saveAiModeratorPolicy(guildId: string, token: string, policy: Record<string, unknown>) {
  return apiRequest<AiModeratorSettings>("/api/ai-moderator/policy", { method: "PUT", body: JSON.stringify({ guild_id: guildId, policy }) }, token);
}

export function getAiModeratorReviews(guildId: string, token: string, status: "OPEN" | "RESOLVED", offset = 0) {
  return apiRequest<AiModerationReviewPage>(`/api/ai-moderator/reviews?guild_id=${guildId}&status=${status}&limit=20&offset=${offset}`, {}, token);
}
export function getAiModeratorReviewAudit(guildId: string, token: string, offset = 0) {
  return apiRequest<AiModerationReviewAuditPage>(`/api/ai-moderator/reviews/audit?guild_id=${guildId}&limit=20&offset=${offset}`, {}, token);
}
export function saveAiModeratorReview(guildId: string, token: string, item: AiModerationReviewItem) {
  const { id, guild_id, channel_id, message_id, user_id, labels, created_at, updated_at, resolved_at, resolved_by, ...payload } = item;
  return apiRequest<AiModerationReviewItem>(`/api/ai-moderator/reviews/${id}`, { method: "PUT", body: JSON.stringify({ guild_id: guildId, ...payload }) }, token);
}
export function simulateAiModerator(guildId: string, token: string, messageText: string) {
  return apiRequest<AiModerationSimulation>("/api/ai-moderator/simulate", { method: "POST", body: JSON.stringify({ guild_id: guildId, message_text: messageText }) }, token);
}

export function exchangeDiscordCode(code: string) {
  return apiRequest<TokenResponse>("/api/auth/token", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function getActivitySession(guildId: string, token: string) {
  return apiRequest<ActivitySession>(`/api/activity/session?guild_id=${guildId}`, {}, token);
}

export function getActivityHealth(guildId: string, token: string) {
  return apiRequest<ActivityHealth>(`/api/activity/health?guild_id=${guildId}`, {}, token);
}

export function getActivityDashboard(guildId: string, token: string) {
  return apiRequest<ActivityDashboardResponse>(`/api/activity/dashboard?guild_id=${guildId}`, {}, token);
}

export function getActivityAudit(guildId: string, token: string, params: Record<string, string | number>) {
  const search = new URLSearchParams({ guild_id: guildId });
  Object.entries(params).forEach(([key, value]) => {
    if (String(value)) search.set(key, String(value));
  });
  return apiRequest<ActivityAuditPage>(`/api/activity/audit?${search.toString()}`, {}, token);
}

export function syncActivityRoles(guildId: string, token: string) {
  return apiRequest<ActivityRoleSyncResponse>(`/api/activity/rbac/roles/sync?guild_id=${guildId}`, {
    method: "POST",
  }, token);
}

export function getActivityAccessRoles(guildId: string, token: string) {
  return apiRequest<ActivityAccessRole[]>(`/api/activity/rbac/access-roles?guild_id=${guildId}`, {}, token);
}

export function getAccessControlData(guildId: string, token: string) {
  return apiRequest<{ access_roles: ActivityAccessRole[] }>(
    `/api/activity/rbac/access-control?guild_id=${guildId}`,
    {},
    token,
  );
}

export function getRolePanelsData(guildId: string, token: string) {
  return apiRequest<{ access_roles: ActivityAccessRole[]; synced_roles: ActivitySyncedRole[] }>(
    `/api/activity/rbac/role-panels?guild_id=${guildId}`,
    {},
    token,
  );
}

export function createActivityAccessRole(guildId: string, token: string, name: string) {
  return apiRequest<ActivityAccessRole>("/api/activity/rbac/access-roles", {
    method: "POST",
    body: JSON.stringify({ guild_id: guildId, name }),
  }, token);
}

export function deleteActivityAccessRole(guildId: string, token: string, roleId: number) {
  return apiRequest<Record<string, unknown>>(`/api/activity/rbac/access-roles/${roleId}?guild_id=${guildId}`, {
    method: "DELETE",
  }, token);
}

export function saveActivityAccessRoleModules(guildId: string, token: string, roleId: number, modules: ActivityAccessRole["modules"]) {
  return apiRequest<ActivityAccessRole>(`/api/activity/rbac/access-roles/${roleId}/modules`, {
    method: "PUT",
    body: JSON.stringify({ guild_id: guildId, modules }),
  }, token);
}

export function getActivitySyncedRoles(guildId: string, token: string) {
  return apiRequest<ActivitySyncedRole[]>(`/api/activity/rbac/synced-roles?guild_id=${guildId}`, {}, token);
}

export function saveActivitySyncedRoleAssignments(guildId: string, token: string, discordRoleId: string, accessRoleIds: number[]) {
  return apiRequest<ActivitySyncedRole>(`/api/activity/rbac/synced-roles/${discordRoleId}/assignments`, {
    method: "PUT",
    body: JSON.stringify({ guild_id: guildId, access_role_ids: accessRoleIds }),
  }, token);
}

export function getWelcomeConfig(guildId: string, token: string) {
  return apiRequest<WelcomeConfig>(`/api/welcome/config?guild_id=${guildId}`, {}, token);
}

export function saveWelcomeConfig(config: WelcomeConfig, token: string) {
  return apiRequest<WelcomeConfig>("/api/welcome/config", {
    method: "PUT",
    body: JSON.stringify(config),
  }, token);
}

export function resetWelcomeConfig(guildId: string, token: string) {
  return apiRequest<WelcomeConfig>(`/api/welcome/config?guild_id=${guildId}`, {
    method: "DELETE",
  }, token);
}

export function testWelcomeConfig(guildId: string, token: string) {
  return apiRequest<Record<string, unknown>>(`/api/welcome/test?guild_id=${guildId}`, {
    method: "POST",
  }, token);
}

export function getDiscordChannels(guildId: string, token: string, kind?: "text" | "voice") {
  const suffix = kind ? `&kind=${kind}` : "";
  return apiRequest<DiscordChannel[]>(`/api/discord/channels?guild_id=${guildId}${suffix}`, {}, token);
}

export function getDiscordRoles(guildId: string, token: string) {
  return apiRequest<DiscordRole[]>(`/api/discord/roles?guild_id=${guildId}`, {}, token);
}

export function getDiscordMembers(guildId: string, token: string) {
  return apiRequest<DiscordMember[]>(`/api/discord/members?guild_id=${guildId}`, {}, token);
}

export function searchDiscordMembers(guildId: string, token: string, query: string) {
  return apiRequest<DiscordMember[]>(`/api/discord/members/search?guild_id=${guildId}&q=${encodeURIComponent(query)}`, {}, token);
}

export function getChannelPurposes(guildId: string, token: string) {
  return apiRequest<Record<ChannelPurpose, string | undefined>>(`/api/activity/channel-purposes?guild_id=${guildId}`, {}, token);
}

export function saveChannelPurpose(guildId: string, token: string, purpose: ChannelPurpose, channelId: string) {
  return apiRequest<Record<ChannelPurpose, string | undefined>>("/api/activity/channel-purposes", {
    method: "PUT",
    body: JSON.stringify({ guild_id: guildId, purpose, channel_id: channelId }),
  }, token);
}

export function getActivityRoles(guildId: string, token: string) {
  return apiRequest<Record<ActivityRolePurpose, string | undefined>>(`/api/activity/roles?guild_id=${guildId}`, {}, token);
}

export function saveActivityRole(guildId: string, token: string, purpose: ActivityRolePurpose, roleId: string) {
  return apiRequest<Record<ActivityRolePurpose, string | undefined>>("/api/activity/roles", {
    method: "PUT",
    body: JSON.stringify({ guild_id: guildId, purpose, role_id: roleId }),
  }, token);
}

export function getDevBlogPosts(guildId: string, token: string) {
  return apiRequest<Array<Record<string, unknown>>>(`/api/dev-blog/posts?guild_id=${guildId}`, {}, token);
}

export function createDevBlogPost(draft: DevBlogDraft, token: string) {
  return apiRequest<Record<string, unknown>>("/api/dev-blog/posts", {
    method: "POST",
    body: JSON.stringify(draft),
  }, token);
}

export function getCreatorAlertSources(guildId: string, token: string) {
  return apiRequest<CreatorAlertSource[]>(`/api/creator-alerts/sources?guild_id=${guildId}`, {}, token);
}

export function saveCreatorAlertSource(source: CreatorAlertSource, token: string) {
  return apiRequest<Record<string, unknown>>("/api/creator-alerts/sources", {
    method: "PUT",
    body: JSON.stringify(source),
  }, token);
}

export function deleteCreatorAlertSource(guildId: string, sourceId: number, token: string) {
  return apiRequest<Record<string, unknown>>(`/api/creator-alerts/sources/${sourceId}?guild_id=${guildId}`, {
    method: "DELETE",
  }, token);
}

export function previewCreatorAlert(source: CreatorAlertSource, token: string) {
  return apiRequest<Record<string, unknown>>("/api/creator-alerts/test", {
    method: "POST",
    body: JSON.stringify({
      guild_id: source.guild_id,
      platform: source.platform,
      channel_name: source.channel_name || "Creator",
      channel_url: source.channel_url,
      alert_kind: source.alert_kind || "stream",
      title_template: source.title_template,
      description_template: source.description_template,
      template: source.template,
      button_label: source.button_label || "Watch",
      color: source.color ?? 0x5865F2,
      ping_role_id: source.ping_role_id,
    }),
  }, token);
}

export function getVoiceRooms(guildId: string, token: string) {
  return apiRequest<VoiceRoom[]>(`/api/voice/rooms?guild_id=${guildId}`, {}, token);
}

export function updateVoiceRoom(guildId: string, token: string, channelId: string, payload: Record<string, unknown>) {
  return apiRequest<Record<string, unknown>>(`/api/voice/rooms/${channelId}`, {
    method: "PATCH",
    body: JSON.stringify({ guild_id: guildId, ...payload }),
  }, token);
}

export function deleteVoiceRoom(guildId: string, token: string, channelId: string) {
  return apiRequest<Record<string, unknown>>(`/api/voice/rooms/${channelId}?guild_id=${guildId}`, {
    method: "DELETE",
  }, token);
}

export function getServerStats(guildId: string, token: string, period = 30) {
  return apiRequest<ServerStatsPayload>(`/api/stats/server?guild_id=${guildId}&period=${period}`, {}, token);
}

export function searchUserStats(guildId: string, token: string, query: string) {
  return apiRequest<Array<Record<string, unknown>>>(`/api/stats/users/search?guild_id=${guildId}&q=${encodeURIComponent(query)}`, {}, token);
}

export function getLogs(guildId: string, token: string, source = "all", eventType = "", query = "") {
  const params = new URLSearchParams({ guild_id: guildId, source, q: query });
  if (eventType) params.set("event_type", eventType);
  return apiRequest<LogsPayload>(`/api/logs?${params.toString()}`, {}, token);
}

export function getLogActors(guildId: string, token: string) {
  return apiRequest<LogActor[]>(`/api/logs/actors?guild_id=${guildId}`, {}, token);
}

export function getBotSettings(guildId: string, token: string) {
  return apiRequest<BotSettingsPayload>(`/api/bot/settings?guild_id=${guildId}`, {}, token);
}

export function getIntegrations(guildId: string, token: string) {
  return apiRequest<Record<string, unknown>>(`/api/integrations?guild_id=${guildId}`, {}, token);
}
