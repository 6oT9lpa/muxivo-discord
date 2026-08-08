import type {
  AccessLevel,
  AccessMatrixRow,
  HealthSignal,
  ModuleKey,
  PanelModule,
  PanelSession,
  PermissionLevel,
  WelcomeConfig,
} from "../types/activity.types";
import { t } from "../i18n";

export const moduleOrder: ModuleKey[] = [
  "dashboard",
  "access",
  "welcome",
  "role-panels",
  "creator-alerts",
  "dev-blog",
  "muxivo-core",
  "logs",
  "server-stats",
  "voice-rooms",
  "bot-settings",
  "integrations",
  "health",
];

export const defaultVisibleModules: ModuleKey[] = [
  "dashboard",
  "integrations",
  "health",
  "server-stats",
  "voice-rooms",
];

export const accessConfigurableModules: ModuleKey[] = [
  "welcome",
  "role-panels",
  "creator-alerts",
  "dev-blog",
  "muxivo-core",
  "logs",
  "bot-settings",
];

export function moduleLabel(key: ModuleKey): string {
  return t(`module.${key}`);
}

export function moduleDescription(key: ModuleKey): string {
  return t(`module.${key}.description`);
}

export const administratorPermissions = moduleOrder.reduce(
  (permissions, key) => ({ ...permissions, [key]: "manage" as PermissionLevel }),
  {} as Record<ModuleKey, PermissionLevel>,
);

export const mockSession: PanelSession = {
  user: {
    id: "local-preview",
    username: "local-admin",
    global_name: "Local Administrator",
  },
  guild_id: "1517163246862471249",
  user_type: "admin",
  access: {
    is_admin: true,
    is_streamer: true,
    is_developer: true,
  },
  access_level: "administrator",
  activity_roles: ["Administrator"],
  permissions: administratorPermissions,
  available_modules: moduleOrder,
  is_admin: true,
};

export const mockWelcome: WelcomeConfig = {
  guild_id: 1517163246862471249,
  title: "Welcome to Muxivo",
  description:
    "Hello {user}. You joined {server}, a community powered by automation, creator tools and clean Discord workflows.",
  thumbnail_url: null,
  footer_text: "Muxivo DS Activity",
  footer_icon_url: null,
  color: 0x5865f2,
  is_enabled: true,
  rules_channel_id: null,
  roles_channel_id: null,
};

export const healthSignals: HealthSignal[] = [
  { name: "Discord Gateway", value: "Online", status: "operational", latency_ms: null },
  { name: "Activity API", value: "Serving", status: "operational", latency_ms: null },
  { name: "PostgreSQL", value: "Connected", status: "operational", latency_ms: null },
  { name: "AI Classifier", value: "Connected", status: "operational", latency_ms: null },
  { name: "Stream Checker", value: "Polling", status: "operational", latency_ms: null },
];

export const mockIntegrations: Record<string, unknown> = {
  discord_bot: { status: "configured", detail: "Discord Bot API is ready for the Activity workspace." },
  creator_platforms: {
    status: "configured",
    poll_interval_seconds: 60,
    sources: [
      { platform: "Twitch", count: 3, active_count: 3 },
      { platform: "YouTube", count: 2, active_count: 1 },
    ],
  },
  muxivo_core: { status: "configured", endpoint: "Local AI classifier connected" },
  database: { status: "configured", detail: "PostgreSQL stores bot state and Activity data." },
};

export function buildModules(session: PanelSession): PanelModule[] {
  const roleLabel = t(`permission.${session.access_level}`);
  return moduleOrder.map((key) => {
    const permission = session.permissions[key] ?? "disabled";
    return {
      key,
      title: moduleLabel(key),
      eyebrow: permission === "disabled" ? t("module.state.locked") : t(`permission.${roleLabel}`),
      description: moduleDescription(key),
      permission,
      status: permission === "disabled" ? "locked" : key === "health" ? "online" : key === "dev-blog" ? "draft" : "configured",
    };
  });
}

export const accessMatrix: AccessMatrixRow[] = [
  row("ordinary", defaultVisibleModules, "view"),
  row("creator", [...defaultVisibleModules, "creator-alerts"], "edit"),
  row("developer", [...defaultVisibleModules, "dev-blog"], "publish"),
  row("moderator", [...defaultVisibleModules, "muxivo-core", "logs"], "view"),
  row("administrator", moduleOrder, "manage"),
];

function row(role: AccessLevel, keys: ModuleKey[], level: PermissionLevel): AccessMatrixRow {
  const permissions = moduleOrder.reduce(
    (acc, key) => ({ ...acc, [key]: keys.includes(key) ? level : "disabled" }),
    {} as Record<ModuleKey, PermissionLevel>,
  );

  return { role, permissions };
}
