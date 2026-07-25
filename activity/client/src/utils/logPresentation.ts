import { t } from "../i18n";

export type LogDetail = {
  key: string;
  label: string;
  value: string;
};

export type LogEmbedField = {
  name: string;
  value: string;
  inline: boolean;
};

export type LogEmbed = {
  title?: string;
  description?: string;
  content?: string;
  before?: string;
  after?: string;
  fields: LogEmbedField[];
  footer?: string;
  color?: string;
};

const eventKeys: Record<string, string> = {
  message: "logs.event.message",
  message_edit: "logs.event.message_edit",
  message_delete: "logs.event.message_delete",
  message_delete_bulk: "logs.event.message_delete_bulk",
  member_join: "logs.event.member_join",
  member_leave: "logs.event.member_leave",
  member_update: "logs.event.member_update",
  member_role_update: "logs.event.member_role_update",
  role_create: "logs.event.role_create",
  role_update: "logs.event.role_update",
  role_delete: "logs.event.role_delete",
  channel_create: "logs.event.channel_create",
  channel_update: "logs.event.channel_update",
  channel_delete: "logs.event.channel_delete",
  voice_join: "logs.event.voice_join",
  voice_leave: "logs.event.voice_leave",
  voice_move: "logs.event.voice_move",
  voice_owner_transfer: "logs.event.voice_owner_transfer",
  moderation_warn: "logs.event.moderation_warn",
  moderation_mute: "logs.event.moderation_mute",
  moderation_unmute: "logs.event.moderation_unmute",
  moderation_kick: "logs.event.moderation_kick",
  moderation_ban: "logs.event.moderation_ban",
  moderation_unban: "logs.event.moderation_unban",
  moderation_audit_mute: "logs.event.moderation_audit_mute",
  moderation_audit_unmute: "logs.event.moderation_audit_unmute",
  moderation_audit_kick: "logs.event.moderation_audit_kick",
  moderation_audit_ban: "logs.event.moderation_audit_ban",
  moderation_audit_unban: "logs.event.moderation_audit_unban",
  activity_roles_synced: "logs.event.activity_roles_synced",
  activity_access_role_created: "logs.event.activity_access_role_created",
  activity_access_role_deleted: "logs.event.activity_access_role_deleted",
  activity_access_role_modules_updated: "logs.event.activity_access_role_modules_updated",
  activity_synced_role_assignments_updated: "logs.event.activity_synced_role_assignments_updated",
  activity_welcome_test_sent: "logs.event.activity_welcome_test_sent",
  activity_dev_blog_published: "logs.event.activity_dev_blog_published",
  activity_dev_blog_draft_saved: "logs.event.activity_dev_blog_draft_saved",
  activity_voice_room_updated: "logs.event.activity_voice_room_updated",
  activity_voice_room_deleted: "logs.event.activity_voice_room_deleted",
};

const detailKeys: Record<string, string> = {
  target: "logs.detail.target",
  channel_id: "logs.detail.channel_id",
  channel: "logs.detail.channel",
  before_channel: "logs.detail.before_channel",
  after_channel: "logs.detail.after_channel",
  reason: "logs.detail.reason",
  duration_seconds: "logs.detail.duration",
  punishment_id: "logs.detail.punishment_id",
  content: "logs.detail.content",
  before: "logs.detail.before",
  after: "logs.detail.after",
  changes: "logs.detail.changes",
  added_roles: "logs.detail.added_roles",
  removed_roles: "logs.detail.removed_roles",
  description: "logs.detail.description",
  title: "logs.detail.title",
  role: "logs.detail.role",
  color: "logs.detail.color",
  position: "logs.detail.position",
  channel_type: "logs.detail.channel_type",
  category: "logs.detail.category",
  author: "logs.detail.author",
  footer: "logs.detail.footer",
};

export function logEventTitle(value: unknown): string {
  const raw = String(value || "log_event");
  const key = eventKeys[raw];
  return key ? t(key) : t("logs.event.unknown", { event: humanizeKey(raw) });
}

export function logDetailRows(row: Record<string, unknown>): LogDetail[] {
  const rows: LogDetail[] = [];
  const targetName = row.target_name ? String(row.target_name) : "";
  const targetId = row.target_id ? String(row.target_id) : "";
  if (targetName || targetId) {
    rows.push({
      key: "target",
      label: t("logs.detail.target"),
      value: targetName && targetId ? `${targetName} (${targetId})` : targetName || targetId,
    });
  }
  if (row.channel_id) {
    rows.push({ key: "channel_id", label: t("logs.detail.channel_id"), value: String(row.channel_id) });
  }

  const details = parseLogDetails(row.details ?? row.content);
  for (const [key, value] of Object.entries(details)) {
    if (value === null || value === undefined || value === "") continue;
    if (key === "fields" && Array.isArray(value)) {
      value.forEach((field, index) => {
        if (!field || typeof field !== "object") return;
        const record = field as Record<string, unknown>;
        rows.push({
          key: `field-${index}`,
          label: String(record.name || t("logs.detail.details")),
          value: formatDetailValue(record.value),
        });
      });
      continue;
    }

    const normalizedKey = key === "_raw" ? "details" : key;
    rows.push({
      key: `${normalizedKey}-${rows.length}`,
      label: detailKeys[normalizedKey] ? t(detailKeys[normalizedKey]) : humanizeKey(normalizedKey),
      value: formatDetailValue(value),
    });
  }

  if (!rows.length) {
    rows.push({ key: "empty", label: t("logs.detail.details"), value: t("dashboard.no_details") });
  }
  return rows;
}

export function parseLogDetails(value: unknown): Record<string, unknown> & { _raw?: string } {
  if (value && typeof value === "object") return value as Record<string, unknown>;
  const raw = String(value ?? "").trim();
  if (!raw) return {};

  const normalized = raw
    .replaceAll("'", "\"")
    .replace(/\bNone\b/g, "null")
    .replace(/\bTrue\b/g, "true")
    .replace(/\bFalse\b/g, "false");
  try {
    const parsed = JSON.parse(normalized);
    return parsed && typeof parsed === "object" ? parsed : { _raw: raw };
  } catch {
    return { _raw: raw };
  }
}

/** Normalizes Discord's serialized embed payload for the dashboard card. */
export function parseLogEmbed(value: unknown): LogEmbed | null {
  const details = parseLogDetails(value);
  const fields = Array.isArray(details.fields)
    ? details.fields.flatMap((field) => {
        if (!field || typeof field !== "object") return [];
        const record = field as Record<string, unknown>;
        const name = String(record.name ?? "").trim();
        const fieldValue = formatDetailValue(record.value);
        return name || fieldValue ? [{ name: name || t("logs.detail.details"), value: fieldValue, inline: Boolean(record.inline) }] : [];
      })
    : [];
  const title = stringValue(details.title);
  const description = stringValue(details.description);
  const content = stringValue(details.content);
  const before = stringValue(details.before);
  const after = stringValue(details.after);
  const footer = footerValue(details.footer);
  const color = stringValue(details.color);
  const hasEmbedShape = Boolean(title || description || content || before || after || footer || fields.length);
  return hasEmbedShape ? { title, description, content, before, after, footer, color, fields } : null;
}

function formatDetailValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(formatDetailValue).filter(Boolean).join(", ");
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (record.name || record.id) {
      const name = record.name ? String(record.name) : "";
      const id = record.id ? String(record.id) : "";
      return name && id ? `${name} (${id})` : name || id;
    }
    return Object.entries(record)
      .map(([key, nestedValue]) => `${humanizeKey(key)}: ${formatDetailValue(nestedValue)}`)
      .join("; ");
  }
  if (typeof value === "boolean") return value ? t("common.yes") : t("common.no");
  return String(value);
}

function stringValue(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const text = formatDetailValue(value).trim();
  return text || undefined;
}

function footerValue(value: unknown): string | undefined {
  if (!value) return undefined;
  if (typeof value === "object") return stringValue((value as Record<string, unknown>).text ?? value);
  return stringValue(value);
}

function humanizeKey(value: string): string {
  const normalized = value.replaceAll("_", " ").trim();
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : t("logs.detail.details");
}
