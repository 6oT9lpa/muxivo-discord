from datetime import datetime, timezone
from typing import Optional, List, Union
from zoneinfo import ZoneInfo

import disnake

from presentation.embeds import EmbedBuilder
from presentation.embeds.deleted_message_attachment_presentation import (
    DeletedMessageAttachmentPresenter,
)


def format_datetime(dt: datetime) -> str:
    msk = ZoneInfo("Europe/Moscow")
    return dt.astimezone(msk).strftime("%H:%M %d.%m.%Y")

def format_permissions(perms: disnake.Permissions) -> str:
    """Форматирует права роли в читаемый список"""
    if perms.value == 0:
        return "Нет прав"
    names = []
    for name, value in perms:
        if value:
            russian = {
                "create_instant_invite": "Создавать приглашения",
                "kick_members": "Выгонять участников",
                "ban_members": "Банить участников",
                "administrator": "Администратор",
                "manage_channels": "Управлять каналами",
                "manage_guild": "Управлять сервером",
                "add_reactions": "Добавлять реакции",
                "view_audit_log": "Просмотр аудит-лога",
                "priority_speaker": "Приоритетный режим",
                "stream": "Стримить",
                "view_channel": "Просмотр каналов",
                "send_messages": "Отправлять сообщения",
                "send_tts_messages": "Отправлять TTS",
                "manage_messages": "Управлять сообщениями",
                "embed_links": "Вставлять ссылки",
                "attach_files": "Прикреплять файлы",
                "read_message_history": "Читать историю",
                "mention_everyone": "Упоминать @everyone",
                "use_external_emojis": "Использовать внешние эмодзи",
                "view_guild_insights": "Просмотр статистики",
                "connect": "Подключаться к голосовым",
                "speak": "Говорить",
                "mute_members": "Отключать микрофон",
                "deafen_members": "Отключать звук",
                "move_members": "Перемещать участников",
                "use_voice_activity": "Голосовая активность",
                "change_nickname": "Менять ник",
                "manage_nicknames": "Управлять никами",
                "manage_roles": "Управлять ролями",
                "manage_webhooks": "Управлять вебхуками",
                "manage_emojis_and_stickers": "Управлять эмодзи и стикерами",
                "use_application_commands": "Использовать команды",
                "request_to_speak": "Запрос на выступление",
                "manage_events": "Управлять событиями",
                "manage_threads": "Управлять тредами",
                "create_public_threads": "Создавать публичные треды",
                "create_private_threads": "Создавать приватные треды",
                "use_external_stickers": "Использовать внешние стикеры",
                "send_messages_in_threads": "Отправлять в тредах",
                "use_embedded_activities": "Использовать встроенные активности",
                "moderate_members": "Модерировать участников",
            }
            names.append(russian.get(name, name))
    return ", ".join(names[:5]) + (f" и ещё {len(names)-5}" if len(names) > 5 else "")

class ChannelCreateEmbedBuilder:
    @staticmethod
    def build_create(
        channel: Union[disnake.TextChannel, disnake.VoiceChannel, disnake.CategoryChannel, disnake.ForumChannel],
        moderator: disnake.Member = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x57F287)
        builder.set_title(f"Канал создан: #{channel.name} (ID: {channel.id})")

        channel_type = "Текстовый"
        if isinstance(channel, disnake.VoiceChannel):
            channel_type = "Голосовой"
        elif isinstance(channel, disnake.CategoryChannel):
            channel_type = "Категория"
        elif isinstance(channel, disnake.ForumChannel):
            channel_type = "Форум"
        builder.add_field("Тип", channel_type, inline=True)

        if moderator:
            builder.add_field(
                "Создал",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=True,
            )
        else:
            builder.add_field("Создал", "Неизвестен (возможно, бот)", inline=True)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

class ChannelDeleteEmbedBuilder:
    @staticmethod
    def build_delete(
        channel: Union[disnake.TextChannel, disnake.VoiceChannel, disnake.CategoryChannel, disnake.ForumChannel],
        moderator: disnake.Member = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"Канал удалён: #{channel.name} (ID: {channel.id})")

        channel_type = "Текстовый"
        if isinstance(channel, disnake.VoiceChannel):
            channel_type = "Голосовой"
        elif isinstance(channel, disnake.CategoryChannel):
            channel_type = "Категория"
        elif isinstance(channel, disnake.ForumChannel):
            channel_type = "Форум"
        builder.add_field("Тип", channel_type, inline=True)

        if moderator:
            builder.add_field(
                "Удалил",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=True,
            )
        else:
            builder.add_field("Удалил", "Неизвестен (возможно, бот)", inline=True)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

class VoiceLogEmbedBuilder:
    @staticmethod
    def build_join(
        member: disnake.Member,
        channel_name: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x57F287)
        builder.set_title(f"{member} (ID: {member.id})")
        builder.set_description("**Присоединился к голосовому каналу**")
        builder.add_field("Канал", channel_name, inline=False)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

    @staticmethod
    def build_leave(
        member: disnake.Member,
        channel_name: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"{member} (ID: {member.id})")
        builder.set_description("**Покинул голосовой канал**")
        builder.add_field("Канал", channel_name, inline=False)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

    @staticmethod
    def build_move(
        member: disnake.Member,
        from_channel: str,
        to_channel: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x5865F2)
        builder.set_title(f"{member} (ID: {member.id})")
        builder.set_description("**Переместился между голосовыми каналами**")
        builder.add_field("Из", from_channel, inline=True)
        builder.add_field("В", to_channel, inline=True)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

class ChannelLogEmbedBuilder:
    @staticmethod
    def build_update(
        channel: Union[disnake.TextChannel, disnake.VoiceChannel, disnake.CategoryChannel, disnake.ForumChannel],
        changes: List[str],
        moderator: disnake.Member = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xFEE75C)
        builder.set_title(f"Канал обновлён: #{channel.name} (ID: {channel.id})")

        channel_type = "Текстовый"
        if isinstance(channel, disnake.VoiceChannel):
            channel_type = "Голосовой"
        elif isinstance(channel, disnake.CategoryChannel):
            channel_type = "Категория"
        elif isinstance(channel, disnake.ForumChannel):
            channel_type = "Форум"
        builder.add_field("Тип канала", channel_type, inline=True)

        if changes:
            builder.add_field("Изменения", "\n".join(f"• {c}" for c in changes), inline=False)
        else:
            builder.add_field("Изменения", "Неизвестные изменения", inline=False)

        if moderator:
            builder.add_field(
                "Модератор",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=True,
            )
        else:
            builder.add_field("Модератор", "Неизвестен (возможно, бот или системное действие)", inline=True)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

class VoiceOwnerTransferEmbedBuilder:
    @staticmethod
    def build_transfer(
        channel: disnake.VoiceChannel,
        old_owner: disnake.Member,
        new_owner: disnake.Member,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x5865F2)
        builder.set_title(f"Владелец динамического войса изменён: #{channel.name} (ID: {channel.id})")
        builder.add_field("Канал", channel.mention if getattr(channel, "mention", None) else f"#{channel.name}", inline=False)
        builder.add_field("Старый владелец", f"{old_owner.mention} (`{old_owner}` ID: {old_owner.id})", inline=False)
        builder.add_field("Новый владелец", f"{new_owner.mention} (`{new_owner}` ID: {new_owner.id})", inline=False)
        builder.add_field("Причина", "Owner вышел из канала и не вернулся в течение 10 секунд", inline=False)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()

class MessageEditLogEmbedBuilder:
    @staticmethod
    def build_edit(
        message: disnake.Message,
        before_content: str,
        after_content: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xFEE75C)
        builder.set_title(f"Сообщение отредактировано (ID: {message.id})")

        builder.add_field(
            "Автор",
            f"{message.author.mention} (`{message.author}` ID: {message.author.id})",
            inline=False,
        )

        builder.add_field(
            "До",
            before_content[:1024] + ("…" if len(before_content) > 1024 else ""),
            inline=False,
        )

        builder.add_field(
            "После",
            after_content[:1024] + ("…" if len(after_content) > 1024 else ""),
            inline=False,
        )

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()

class MessageDeleteLogEmbedBuilder:
    @staticmethod
    def build_delete(
        message: disnake.Message,
        moderator: disnake.Member = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"Сообщение удалено (ID: {message.id})")

        builder.add_field(
            "Автор",
            f"{message.author.mention} (`{message.author}` ID: {message.author.id})",
            inline=False,
        )

        if moderator:
            builder.add_field(
                "Удалил",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=False,
            )
        else:
            builder.add_field("Удалил", "Неизвестно (возможно, бот)", inline=False)

        attachment_presentation = DeletedMessageAttachmentPresenter.present(
            getattr(message, "attachments", ())
        )
        content = message.content or (
            "(текст отсутствует; удалённое вложение указано ниже)"
            if attachment_presentation.field_value
            else "(пустое сообщение)"
        )
        builder.add_field(
            "Содержание",
            content[:1024] + ("…" if len(content) > 1024 else ""),
            inline=False,
        )
        if attachment_presentation.field_value:
            builder.add_field("Удалённые вложения", attachment_presentation.field_value, inline=False)
        if attachment_presentation.preview_url:
            builder.add_image(attachment_presentation.preview_url)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")

        return builder.build()


class VoiceLogEmbedBuilder:
    @staticmethod
    def build_join(
        member: disnake.Member,
        channel_name: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x57F287)
        builder.set_title(f"{member} ({member.id})")
        builder.set_description("Joined voice channel")
        builder.add_field("Channel:", channel_name, inline=False)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()

    @staticmethod
    def build_leave(
        member: disnake.Member,
        channel_name: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"{member} ({member.id})")
        builder.set_description("Left voice channel")
        builder.add_field("Channel:", channel_name, inline=False)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()

    @staticmethod
    def build_move(
        member: disnake.Member,
        from_channel: str,
        to_channel: str,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x5865F2)
        builder.set_title(f"{member} ({member.id})")
        builder.set_description("Moved between voice channels")
        builder.add_field("Before Channel:", from_channel, inline=True)
        builder.add_field("After Channel:", to_channel, inline=True)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()


class MessageLogEmbedBuilder:
    @staticmethod
    def build_delete(author, timestamp: Optional[datetime] = None) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"{author} ({author.id})")
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()

    @staticmethod
    def build_edit(author, timestamp: Optional[datetime] = None) -> disnake.Embed:
        builder = EmbedBuilder(color=0xFEE75C)
        builder.set_title(f"{author} ({author.id})")
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()


class MemberEventEmbedBuilder:
    @staticmethod
    def build_leave(
        member: disnake.Member,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"Member left: {member} (ID: {member.id})")
        builder.add_field("Event", "member_leave", inline=True)
        builder.add_field("User", f"{member.mention} (`{member}` ID: {member.id})", inline=False)

        joined_at = getattr(member, "joined_at", None)
        if joined_at:
            builder.add_field("Joined", f"<t:{int(joined_at.timestamp())}:R>", inline=True)

        roles = [
            role.name
            for role in getattr(member, "roles", [])
            if not getattr(role, "is_default", lambda: False)()
        ]
        if roles:
            visible_roles = ", ".join(roles[:10])
            if len(roles) > 10:
                visible_roles = f"{visible_roles}..."
            builder.add_field("Roles", visible_roles, inline=False)

        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()

    @staticmethod
    def build_update(
        member: disnake.Member,
        changes: List[str],
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder = EmbedBuilder(color=0xFEE75C)
        builder.set_title(f"Member updated: {member} (ID: {member.id})")
        builder.add_field("Event", "member_update", inline=True)
        builder.add_field("User", f"{member.mention} (`{member}` ID: {member.id})", inline=False)
        builder.add_field("Changes", "\n".join(f"- {change}" for change in changes) or "-", inline=False)
        builder.set_footer(text=f"Time: {format_datetime(timestamp)}")
        return builder.build()

    @staticmethod
    def build_pending_update(
        member: disnake.Member,
        before_pending: bool,
        after_pending: bool,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        builder = EmbedBuilder(color=0x57F287 if before_pending and not after_pending else 0xFEE75C)
        builder.set_title(f"Проверка участника обновлена: {member} (ID: {member.id})")
        builder.add_field("Пользователь", f"{member.mention} (`{member}` ID: {member.id})", inline=False)
        before_value = "ожидает проверки" if before_pending else "прошёл проверку"
        after_value = "ожидает проверки" if after_pending else "прошёл проверку"
        builder.add_field("Статус", f"{before_value} → {after_value}", inline=False)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()

class BulkDeleteEmbedBuilder:
    @staticmethod
    def build_bulk_delete(
        channel: disnake.TextChannel,
        count: int,
        moderator: Optional[disnake.Member] = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title("🗑 Массовое удаление сообщений")
        builder.add_field("Канал", channel.mention, inline=True)
        builder.add_field("Количество", str(count), inline=True)
        if moderator:
            builder.add_field(
                "Удалил",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=False,
            )
        else:
            builder.add_field("Удалил", "Неизвестно", inline=False)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()
    
class RoleCreateEmbedBuilder:
    @staticmethod
    def build_create(
        role: disnake.Role,
        moderator: Optional[disnake.Member] = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x57F287)
        builder.set_title(f"Роль создана: {role.name} (ID: {role.id})")
        builder.add_field("Цвет", f"#{role.color.value:06X}" if role.color.value else "Нет", inline=True)
        builder.add_field("Положение", str(role.position), inline=True)
        builder.add_field("Отображается отдельно", "Да" if role.hoist else "Нет", inline=True)
        builder.add_field("Упоминаемая", "Да" if role.mentionable else "Нет", inline=True)
        builder.add_field("Права", format_permissions(role.permissions), inline=False)
        if moderator:
            builder.add_field(
                "Создал",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=False,
            )
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()
    
class RoleDeleteEmbedBuilder:
    @staticmethod
    def build_delete(
        role: disnake.Role,
        moderator: Optional[disnake.Member] = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0xED4245)
        builder.set_title(f"Роль удалена: {role.name} (ID: {role.id})")
        builder.add_field("Цвет", f"#{role.color.value:06X}" if role.color.value else "Нет", inline=True)
        builder.add_field("Положение", str(role.position), inline=True)
        if moderator:
            builder.add_field(
                "Удалил",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=False,
            )
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()
    
class RoleUpdateEmbedBuilder:
    @staticmethod
    def build_update(
        before: disnake.Role,
        after: disnake.Role,
        moderator: Optional[disnake.Member] = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        changes = []
        if before.name != after.name:
            changes.append(f"Название: `{before.name}` → `{after.name}`")
        if before.color != after.color:
            before_c = f"#{before.color.value:06X}" if before.color.value else "Нет"
            after_c = f"#{after.color.value:06X}" if after.color.value else "Нет"
            changes.append(f"Цвет: `{before_c}` → `{after_c}`")
        if before.position != after.position:
            changes.append(f"Позиция: {before.position} → {after.position}")
        if before.hoist != after.hoist:
            changes.append(f"Отображать отдельно: {'Да' if after.hoist else 'Нет'}")
        if before.mentionable != after.mentionable:
            changes.append(f"Упоминаемая: {'Да' if after.mentionable else 'Нет'}")
        if before.permissions != after.permissions:
            # Показываем только изменения прав
            added, removed = [], []
            for perm, value in after.permissions:
                if value and not getattr(before.permissions, perm, False):
                    added.append(perm)
                elif not value and getattr(before.permissions, perm, False):
                    removed.append(perm)
            if added:
                changes.append(f"Добавлены права: {', '.join(added)}")
            if removed:
                changes.append(f"Убраны права: {', '.join(removed)}")

        builder = EmbedBuilder(color=0xFEE75C)
        builder.set_title(f"Роль обновлена: {after.name} (ID: {after.id})")
        if changes:
            builder.add_field("Изменения", "\n".join(f"• {c}" for c in changes), inline=False)
        else:
            builder.add_field("Изменения", "Незначительные изменения", inline=False)
        if moderator:
            builder.add_field(
                "Изменил",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=False,
            )
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()
    
class MemberRoleUpdateEmbedBuilder:
    @staticmethod
    def build_update(
        member: disnake.Member,
        added_roles: List[disnake.Role],
        removed_roles: List[disnake.Role],
        moderator: Optional[disnake.Member] = None,
        timestamp: Optional[datetime] = None,
    ) -> disnake.Embed:
        builder = EmbedBuilder(color=0x5865F2)
        builder.set_title(f"Роли обновлены у {member} (ID: {member.id})")
        if added_roles:
            builder.add_field(
                "Добавлены",
                ", ".join(r.mention for r in added_roles),
                inline=False,
            )
        if removed_roles:
            builder.add_field(
                "Убраны",
                ", ".join(r.mention for r in removed_roles),
                inline=False,
            )
        if not added_roles and not removed_roles:
            builder.add_field("Изменения", "Незначительные", inline=False)
        if moderator:
            builder.add_field(
                "Модератор",
                f"{moderator.mention} (`{moderator}` ID: {moderator.id})",
                inline=False,
            )
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        builder.set_footer(text=f"Время: {format_datetime(timestamp)}")
        return builder.build()
