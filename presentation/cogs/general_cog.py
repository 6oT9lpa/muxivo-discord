from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import disnake
from disnake.ext import commands

from infrastructure.logging import get_logger

logger = get_logger(__name__)


class GeneralCog(commands.Cog):
    _COMMANDS: tuple[dict[str, object], ...] = (
        {"section": "Основное", "command": "/help", "description": "Показать актуальную карту команд и модулей"},
        {"section": "Основное", "command": "/ping", "description": "Проверить задержку Muxivo Discord"},
        {"section": "Activity", "command": "Muxivo DS Activity", "description": "Панель управления: Dashboard, роли доступа, настройки, логи, Dev Blog, Creator Alerts"},
        {"section": "Статистика", "command": "/stats server", "description": "Статистика сервера за 7 или 30 дней"},
        {"section": "Статистика", "command": "/stats user", "description": "Статистика участника, включая активность и наказания"},
        {"section": "Статистика", "command": "/stats channels", "description": "Самые активные каналы за неделю"},
        {"section": "Статистика", "command": "/stats activity", "description": "Активность по часам за последние 7 дней"},
        {"section": "Статистика", "command": "/leaderboard", "description": "Топ активных участников"},
        {"section": "Голосовые комнаты", "command": "/send", "description": "Опустить панель управления текущей voice-комнатой вниз"},
        {"section": "Голосовые комнаты", "command": "/voice set_trigger", "description": "Назначить trigger-канал для создания комнат", "permission": "administrator"},
        {"section": "Голосовые комнаты", "command": "/voice remove_trigger", "description": "Удалить trigger-канал", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/sync_roles", "description": "Синхронизировать роли Discord для Activity и role panels", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/set_auto_role", "description": "Настроить авто-роль для новых участников", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/list_roles", "description": "Показать роли сервера и их статус", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/set_role_public", "description": "Скрыть или показать роль в публичных панелях", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/set_role", "description": "Назначить роли ping_dev и ping_stream", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/activity_role", "description": "Назначить Discord-роль для Activity creator/developer доступа", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/create_panel", "description": "Создать панель ролей с кнопками или реакциями", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/panel_add", "description": "Добавить роль в существующую панель", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/panel_remove", "description": "Удалить роль из панели", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/panel_list", "description": "Показать панели ролей на сервере", "permission": "administrator"},
        {"section": "Роли и панели", "command": "/delete_panel", "description": "Удалить панель ролей", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/set_channel", "description": "Назначить системный канал: welcome, logs, streams, Dev Blog или AI moderation log", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/list_channels", "description": "Показать назначенные системные каналы", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome setup", "description": "Настроить welcome-сообщение", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome media", "description": "Настроить медиа welcome-сообщения", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome channels", "description": "Выбрать каналы для кнопок rules/roles", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome toggle", "description": "Включить или выключить welcome", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome preview", "description": "Предпросмотр welcome-сообщения", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome reset", "description": "Сбросить welcome-настройки", "permission": "administrator"},
        {"section": "Каналы и welcome", "command": "/welcome show", "description": "Показать текущие welcome-настройки", "permission": "administrator"},
        {"section": "Creator Alerts", "command": "/streamer add", "description": "Подключить Twitch, YouTube или Kick source"},
        {"section": "Creator Alerts", "command": "/streamer remove", "description": "Удалить creator source"},
        {"section": "Creator Alerts", "command": "/streamer list", "description": "Показать creator sources"},
        {"section": "Creator Alerts", "command": "/stream-template set", "description": "Настроить шаблон embed-уведомления"},
        {"section": "Creator Alerts", "command": "Activity -> Creator Alerts", "description": "Создать source, preview, button label и шаблон уведомления"},
        {"section": "Dev Blog", "command": "Activity -> Dev Blog", "description": "Сохранить draft или опубликовать Components V2 пост"},
        {"section": "Модерация", "command": "/moderation", "description": "Краткая памятка по командам модерации"},
        {"section": "Модерация", "command": "/warn", "description": "Выдать предупреждение", "permission": "moderate_members"},
        {"section": "Модерация", "command": "/mute", "description": "Выдать таймаут", "permission": "ban_members"},
        {"section": "Модерация", "command": "/unmute", "description": "Снять таймаут", "permission": "moderate_members"},
        {"section": "Модерация", "command": "/kick", "description": "Кикнуть участника", "permission": "kick_members"},
        {"section": "Модерация", "command": "/ban", "description": "Забанить участника", "permission": "ban_members"},
        {"section": "Модерация", "command": "/unban", "description": "Разбанить участника по ID", "permission": "ban_members"},
        {"section": "Модерация", "command": "/history", "description": "История наказаний участника", "permission": "moderate_members"},
        {"section": "Модерация", "command": "/punishments", "description": "Активные наказания", "permission": "moderate_members"},
        {"section": "Модерация", "command": "/slowmode", "description": "Настроить slowmode канала", "permission": "manage_channels"},
        {"section": "Модерация", "command": "/purge", "description": "Массово удалить сообщения", "permission": "manage_messages"},
        {"section": "AI moderation", "command": "/set ai-channel", "description": "Добавить текстовый канал в локальную AI-модерацию", "permission": "administrator"},
        {"section": "AI moderation", "command": "/list ai-channel", "description": "Показать каналы, отслеживаемые AI", "permission": "administrator"},
        {"section": "AI moderation", "command": "/ai-policy label|blacklist|domains", "description": "Настроить лимиты действий, риск, blacklist и домены", "permission": "administrator"},
        {"section": "AI moderation", "command": "Activity -> Muxivo Core", "description": "Вкладка с каналами, политиками и безопасными настройками", "permission": "administrator"},
    )

    def __init__(self, bot: commands.Bot):
        self._bot = bot
        logger.info("GeneralCog initialized")

    @commands.slash_command(name="ping", description="Проверить задержку Muxivo Discord")
    async def ping(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        latency_ms = round(self._bot.latency * 1000)
        embed = disnake.Embed(
            title="Muxivo Discord online",
            description=f"Gateway latency: **{latency_ms} ms**",
            color=disnake.Color.green(),
        )
        embed.set_footer(text="Проверка видна только вам")
        await ctx.response.send_message(embed=embed, ephemeral=True)
        logger.info(
            "Ping command used: guild_id=%s user_id=%s latency_ms=%s",
            getattr(ctx.guild, "id", None),
            ctx.author.id,
            latency_ms,
        )

    @commands.slash_command(name="help", description="Показать доступные команды Muxivo Discord")
    async def help(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        commands_by_section = self.get_available_commands_by_section(ctx.author)
        embed = self._build_help_embed(ctx, commands_by_section)
        await ctx.response.send_message(embed=embed, ephemeral=True)
        logger.info(
            "Help command used: guild_id=%s user_id=%s command_count=%s",
            getattr(ctx.guild, "id", None),
            ctx.author.id,
            sum(len(commands) for commands in commands_by_section.values()),
        )

    def get_available_commands_by_section(self, member: disnake.Member) -> dict[str, list[dict[str, object]]]:
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for command in self._COMMANDS:
            if self._is_command_available(member, command):
                grouped[str(command["section"])].append(command)
        return dict(grouped)

    def _is_command_available(self, member: disnake.Member, command: dict[str, object]) -> bool:
        permission = command.get("permission")
        if not permission:
            return True

        guild_permissions = getattr(member, "guild_permissions", None)
        if guild_permissions is None:
            return False

        if getattr(guild_permissions, "administrator", False):
            return True

        return bool(getattr(guild_permissions, str(permission), False))

    def _build_help_embed(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        commands_by_section: dict[str, list[dict[str, object]]],
    ) -> disnake.Embed:
        guild_name = ctx.guild.name if ctx.guild else "Discord"
        embed = disnake.Embed(
            title="Muxivo Discord command center",
            description=(
                f"Команды и панели, доступные для **{ctx.author.display_name}** на сервере **{guild_name}**.\n"
                "Список учитывает ваши Discord-права. Доступ к Activity вкладкам дополнительно контролируется Activity RBAC."
            ),
            color=disnake.Color.blurple(),
        )

        for section, commands_in_section in commands_by_section.items():
            embed.add_field(
                name=section,
                value=self._format_commands(commands_in_section),
                inline=False,
            )

        embed.set_footer(text=f"Всего доступно пунктов: {sum(len(items) for items in commands_by_section.values())}")
        return embed

    def _format_commands(self, commands_in_section: Iterable[dict[str, object]]) -> str:
        lines = [
            f"`{command['command']}` - {command['description']}"
            for command in commands_in_section
        ]
        return "\n".join(lines)[:1024]
