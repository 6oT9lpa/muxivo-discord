export type Theme = "dark" | "light";
export type ActivityUserType = "standard" | "streamer" | "developer" | "admin";
export type AccessLevel = "ordinary" | "creator" | "developer" | "moderator" | "administrator";
export type PermissionLevel = "disabled" | "view" | "edit" | "publish" | "manage";

export type ModuleKey =
  | "dashboard"
  | "access"
  | "welcome"
  | "role-panels"
  | "creator-alerts"
  | "dev-blog"
  | "ai-moderator"
  | "logs"
  | "server-stats"
  | "voice-rooms"
  | "bot-settings"
  | "integrations"
  | "health";

export type ActivityUser = {
  id: string;
  username: string;
  discriminator?: string | null;
  global_name?: string | null;
  avatar?: string | null;
};

export type ActivityAccess = {
  is_admin: boolean;
  is_streamer: boolean;
  is_developer: boolean;
};

export type ActivitySession = {
  user: ActivityUser;
  guild_id: string;
  user_type: ActivityUserType;
  access: ActivityAccess;
  is_admin: boolean;
  access_level?: AccessLevel;
  activity_roles?: string[];
  permissions?: Record<ModuleKey, PermissionLevel>;
  available_modules?: ModuleKey[];
};

export type PanelSession = ActivitySession & {
  access_level: AccessLevel;
  activity_roles: string[];
  permissions: Record<ModuleKey, PermissionLevel>;
  available_modules: ModuleKey[];
};

export type WelcomeConfig = {
  guild_id: string | number;
  title: string;
  description: string;
  thumbnail_url: string | null;
  footer_text: string | null;
  footer_icon_url: string | null;
  color: number;
  is_enabled: boolean;
  rules_channel_id: string | number | null;
  roles_channel_id: string | number | null;
};

export type PanelModule = {
  key: ModuleKey;
  title: string;
  eyebrow: string;
  description: string;
  status: "online" | "configured" | "draft" | "attention" | "locked";
  permission: PermissionLevel;
};

export type DashboardMetric = {
  label: string;
  value: string;
  delta: string;
  tone: "neutral" | "success" | "warning" | "danger";
  key?: "modules" | "ai" | "creators" | "latency";
};

export type TimelineEvent = {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: "neutral" | "success" | "warning" | "danger";
};

export type HealthSignal = {
  name: string;
  value: string;
  status: "operational" | "degraded" | "offline";
  latency_ms?: number | null;
};

export type ActivityHealth = {
  guild_id: string;
  signals: HealthSignal[];
  bot_latency_ms: number | null;
};

export type AccessMatrixRow = {
  role: AccessLevel;
  permissions: Record<ModuleKey, PermissionLevel>;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  scope: string;
};

export type DiscordChannel = {
  id: string;
  name: string;
  type: number;
  position: number;
  parent_id?: string | null;
};

export type DiscordRole = {
  id: string;
  name: string;
  color: number;
  position: number;
  permissions?: number;
  managed: boolean;
  mentionable: boolean;
};

export type DiscordMember = {
  id: string;
  username: string;
  display_name: string;
  avatar?: string | null;
};

export type ActivityRolePurpose =
  | "activity_admin"
  | "activity_streamer"
  | "activity_developer"
  | "ping_stream"
  | "ping_dev";

export type ChannelPurpose =
  | "welcome"
  | "member_log"
  | "mod_log"
  | "message_log"
  | "channel_log"
  | "stream_announce"
  | "dev_blog"
  | "ai_moderation_log";

export type BotSettingsPayload = {
  guild_id: string | number;
  subscription_tier?: "free" | "plus" | "pro";
  activity_rotation_enabled?: boolean;
  activity_rotation_interval_seconds?: number;
  log_level?: string | null;
  retention?: Record<string, unknown>;
  channels: DiscordChannel[];
  roles: DiscordRole[];
  channel_purposes: Partial<Record<ChannelPurpose, string>>;
  activity_roles: Partial<Record<ActivityRolePurpose, string>>;
};

export type AiModeratorSettings = {
  guild_id: string;
  channels: string[];
  log_channel_id: string | null;
  policy: AiModerationPolicy;
  is_default_policy: boolean;
  available_channels: DiscordChannel[];
  metrics_enabled: boolean;
  review_access: boolean;
};

export type AiModerationReviewItem = {
  id: number; guild_id: string; channel_id: string; message_id: string; user_id: string;
  message_text: string; risk_score: number; severity: number; action: AiModerationAction;
  labels: string[]; status: "OPEN" | "RESOLVED"; revision: number;
  created_at: string; updated_at: string; resolved_at: string | null; resolved_by: string | null;
};
export type AiModerationReviewPage = { items: AiModerationReviewItem[]; total: number; limit: number; offset: number };
export type AiModerationReviewAuditEntry = { id: number; review_item_id: number; actor_id: string; action: string; before_json: Record<string, unknown>; after_json: Record<string, unknown>; created_at: string; message_id: string; user_id: string };
export type AiModerationReviewAuditPage = { items: AiModerationReviewAuditEntry[]; total: number; limit: number; offset: number };

export type AiModeratorMetrics = {
  total_messages: number;
  would_delete: number;
  review_count: number;
  average_latency_ms: number;
  safe_false_positive_rate: number | null;
  confused_classes: Array<{ name: string; count: number }>;
  noisy_rules: Array<{ name: string; count: number }>;
  moderator_correction_seconds: number | null;
};

export type AiModerationAction = "IGNORE" | "LOG" | "REVIEW" | "WARN" | "DELETE" | "DELETE_WARN" | "TIMEOUT" | "KICK" | "BAN";

export type AiModerationLabelPolicy = {
  risk_threshold: number;
  min_action: AiModerationAction;
  max_action: AiModerationAction;
};

export type AiModerationPolicy = {
  blacklist_words: string[];
  allowed_domains: string[];
  labels: Record<string, AiModerationLabelPolicy>;
  blacklist_action: AiModerationAction;
  unapproved_domain_action: AiModerationAction;
  context_window_days: number;
  repeat_offender_threshold: number;
  repeat_offender_action: AiModerationAction;
  escalation_enabled: boolean;
  escalation_score_threshold: number;
  escalation_half_life_days: number;
  excluded_user_ids: string[];
  excluded_role_ids: string[];
  excluded_channel_ids: string[];
  exclude_bots: boolean;
  test_mode: boolean;
  enforcement_mode: "SHADOW" | "LIMITED" | "ELEVATED";
  limited_min_confidence: number;
  beta_enforcement_acknowledged: boolean;
  allow_automated_timeout: boolean;
  allow_automated_kick: boolean;
  allow_automated_ban: boolean;
};

export type DevBlogEmbed = {
  title?: string | null;
  description: string;
  image_url?: string | null;
  color: number;
};

export type DevBlogDraft = {
  guild_id: string | number;
  title: string;
  content?: string | null;
  embeds: DevBlogEmbed[];
  status: "draft" | "published";
  image_render_mode?: "gallery_bottom" | "inline_between_text";
};

export type CreatorAlertSource = {
  id?: number;
  user_id?: string | number;
  guild_id: string | number;
  platform: "twitch" | "youtube" | "kick";
  alert_kind?: "stream" | "video" | "short";
  channel_url: string;
  channel_name?: string | null;
  external_channel_id?: string | null;
  title_template?: string | null;
  description_template?: string | null;
  template?: string | null;
  button_label?: string | null;
  color?: number;
  ping_role_id?: string | number | null;
  active: boolean;
  last_event_id?: string | null;
  last_checked_at?: string | null;
};

export type VoiceRoom = {
  channel_id: string;
  guild_id: string | number;
  owner_id: string;
  admin_id?: string | null;
  voice_member_ids?: string[];
  name: string;
  is_persistent: boolean;
  created_at: string;
  discord?: {
    id: string;
    name: string;
    user_limit?: number;
    rtc_region?: string | null;
    permission_overwrites?: unknown[];
  } | null;
};

export type ServerStatsPayload = {
  summary: Record<string, unknown>;
  channels: Array<Record<string, unknown>>;
  hourly: Array<{ hour: number; count: number }>;
  daily: Array<{ date: string; count: number }>;
};

export type LogsPayload = {
  messages: Array<Record<string, unknown>>;
  audit: Array<Record<string, unknown>>;
};

export type LogActor = {
  id: string;
  name: string;
};

export type AccessDeniedDetail = {
  code: string;
  message: string;
  can_sync_roles?: boolean;
};

export type ActivityAccessRole = {
  id: number;
  guild_id: number;
  slug: string;
  name: string;
  is_builtin: boolean;
  modules: Record<ModuleKey, PermissionLevel>;
};

export type ActivitySyncedRole = {
  role_id: string;
  guild_id: number;
  name: string;
  color: number;
  position: number;
  permissions: number;
  is_admin: boolean;
  managed: boolean;
  mentionable: boolean;
  synced_at?: string | null;
  access_roles: ActivityAccessRole[];
};

export type ActivityRoleSyncResponse = {
  guild_id: number;
  synced_count: number;
  admin_roles_count: number;
  roles: ActivitySyncedRole[];
};

export type ActivityAuditEvent = {
  id: number;
  guild_id: number;
  actor_id?: number | null;
  actor_name?: string | null;
  target_id?: number | null;
  target_name?: string | null;
  event_type: string;
  details?: string | null;
  created_at: string;
};

export type ActivityAuditPage = {
  items: ActivityAuditEvent[];
  total: number;
  limit: number;
  offset: number;
};

export type ActivityDashboardResponse = {
  metrics: {
    modules_ready: number;
    modules_total: number;
    ai_checks_today: number;
    ai_flagged_today: number;
    creator_sources: number;
    bot_latency_ms: number | null;
  };
  audit: ActivityAuditEvent[];
};
