from __future__ import annotations

from typing import Optional

import disnake

from application.utils.creator_alert_templates import CreatorAlertTemplateRenderer
from core.domain.creator_alert import CreatorAlertKind, CreatorContentEvent, CreatorPlatform


_DEFAULT_TITLE_TEMPLATES = {
    "",
    "{creator.name} is live on {platform}",
    "{creator.name} is active on {platform}",
    "{creator.name} начал стрим на {platform}",
}
_DEFAULT_DESCRIPTION_TEMPLATES = {
    "",
    "{creator.ping} {creator.name} started streaming {game}\n{url}",
    "{creator.ping} {title}\nGame: {game}\n{url}",
    "{creator.ping} {creator.name} posted an update: {url}",
    "{creator.ping}\n\n**{creator.name} уже в эфире.**\n\n**Название:** {title}\n**Категория:** {game}\n\n{url}",
}


class CreatorAlertEmbedBuilder:
    @staticmethod
    def render_text(
        template: str,
        event: CreatorContentEvent,
        *,
        creator_ping: str = "",
    ) -> str:
        return CreatorAlertTemplateRenderer.render(template, event, creator_ping=creator_ping)

    @staticmethod
    def build(
        event: CreatorContentEvent,
        *,
        title_template: str,
        description_template: str,
        color: int = 0x5865F2,
        creator_ping: str = "",
        creator_icon_url: Optional[str] = None,
    ) -> disnake.Embed:
        embed = disnake.Embed(
            title=CreatorAlertEmbedBuilder._resolve_title(title_template, event, creator_ping=creator_ping)[:256],
            description=CreatorAlertEmbedBuilder._resolve_description(
                description_template,
                event,
                creator_ping=creator_ping,
            )[:4096],
            url=event.url,
            color=color,
        )
        if creator_icon_url:
            embed.set_author(name=event.creator_name, icon_url=creator_icon_url)
        else:
            embed.set_author(name=event.creator_name)
        embed.add_field(name="Платформа", value=CreatorAlertEmbedBuilder.platform_name(event.platform), inline=True)
        if event.alert_kind == CreatorAlertKind.STREAM:
            embed.add_field(name="Категория", value=event.game or "Не указана", inline=True)
        else:
            embed.add_field(name="Тип", value=CreatorAlertEmbedBuilder.kind_name(event.alert_kind), inline=True)
        embed.set_footer(
            text="Muxivo Discord Creator Alerts",
            icon_url=event.thumbnail_url or creator_icon_url,
        )
        if event.thumbnail_url:
            embed.set_image(url=event.thumbnail_url)
        elif creator_icon_url:
            embed.set_thumbnail(url=creator_icon_url)
        return embed

    @staticmethod
    def default_stream_embed(event: CreatorContentEvent, *, color: int = 0x5865F2) -> disnake.Embed:
        return CreatorAlertEmbedBuilder.build(
            event,
            title_template="",
            description_template="",
            color=color,
        )

    @staticmethod
    def platform_color(platform: CreatorPlatform, fallback: Optional[int] = None) -> int:
        if fallback is not None:
            return fallback
        return {
            CreatorPlatform.TWITCH: 0x9146FF,
            CreatorPlatform.YOUTUBE: 0xFF0000,
            CreatorPlatform.KICK: 0x53FC18,
        }.get(platform, 0x5865F2)

    @staticmethod
    def platform_name(platform: CreatorPlatform) -> str:
        return {
            CreatorPlatform.TWITCH: "Twitch",
            CreatorPlatform.YOUTUBE: "YouTube",
            CreatorPlatform.KICK: "Kick",
        }.get(platform, platform.value.title())

    @staticmethod
    def kind_name(kind: CreatorAlertKind) -> str:
        return {
            CreatorAlertKind.STREAM: "Стрим",
            CreatorAlertKind.VIDEO: "Видео",
            CreatorAlertKind.SHORT: "Shorts",
        }.get(kind, kind.value.title())

    @staticmethod
    def _resolve_title(template: str, event: CreatorContentEvent, *, creator_ping: str = "") -> str:
        if template.strip() not in _DEFAULT_TITLE_TEMPLATES:
            return CreatorAlertEmbedBuilder.render_text(template, event, creator_ping=creator_ping)
        platform = CreatorAlertEmbedBuilder.platform_name(event.platform)
        if event.alert_kind == CreatorAlertKind.STREAM:
            return f"{event.creator_name} начал стрим на {platform}"
        if event.alert_kind == CreatorAlertKind.SHORT:
            return f"{event.creator_name} выпустил новое короткое видео"
        return f"{event.creator_name} выпустил новое видео на {platform}"

    @staticmethod
    def _resolve_description(template: str, event: CreatorContentEvent, *, creator_ping: str = "") -> str:
        if template.strip() not in _DEFAULT_DESCRIPTION_TEMPLATES:
            return CreatorAlertEmbedBuilder.render_text(template, event, creator_ping=creator_ping)

        platform = CreatorAlertEmbedBuilder.platform_name(event.platform)
        ping_line = f"{creator_ping}\n\n" if creator_ping else ""
        if event.alert_kind == CreatorAlertKind.STREAM:
            game = event.game or "Не указана"
            if event.platform == CreatorPlatform.YOUTUBE:
                return (
                    f"{ping_line}"
                    f"**{event.creator_name} запустил прямой эфир на YouTube.**\n\n"
                    f"**Тема трансляции:** {event.title}\n"
                    f"**Категория:** {game}\n\n"
                    "Открывай эфир, ставь лайк и поддержи автора в чате.\n\n"
                    f"{event.url}"
                )
            if event.platform == CreatorPlatform.KICK:
                return (
                    f"{ping_line}"
                    f"**{event.creator_name} вышел в эфир на Kick.**\n\n"
                    f"**Название:** {event.title}\n"
                    f"**Категория:** {game}\n\n"
                    "Подключайся к эфиру и поддержи стримера.\n\n"
                    f"{event.url}"
                )
            return (
                f"{ping_line}"
                f"**{event.creator_name} уже в эфире на {platform}.**\n\n"
                f"**Название:** {event.title}\n"
                f"**Категория:** {game}\n\n"
                "Залетай на трансляцию, поддержи автора и напиши пару сообщений в чат.\n\n"
                f"{event.url}"
            )

        label = "короткое видео" if event.alert_kind == CreatorAlertKind.SHORT else "видео"
        return (
            f"{ping_line}"
            f"**{event.creator_name} опубликовал новое {label} на {platform}.**\n\n"
            f"**Название:** {event.title}\n\n"
            "Можно смотреть прямо сейчас:\n"
            f"{event.url}"
        )
