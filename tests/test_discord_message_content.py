from types import SimpleNamespace

from application.services.discord_message_content import DiscordMessageContentNormalizer


def _message(content="", attachment_url="", edited_at=None, embeds=()):
    attachments = [SimpleNamespace(url=attachment_url, filename="file.gif", content_type="image/gif")] if attachment_url else []
    return SimpleNamespace(content=content, attachments=attachments, embeds=list(embeds), stickers=[], edited_at=edited_at)


def test_same_gif_with_only_metadata_change_is_not_a_content_change() -> None:
    normalizer = DiscordMessageContentNormalizer()
    assert not normalizer.changed(_message(attachment_url="https://cdn.example/a.gif", edited_at=1), _message(attachment_url="https://cdn.example/a.gif", edited_at=2))


def test_changed_link_or_attachment_is_a_content_change() -> None:
    normalizer = DiscordMessageContentNormalizer()
    assert normalizer.changed(_message("https://example.com/a"), _message("https://example.com/b"))
    assert normalizer.changed(_message(attachment_url="https://cdn.example/a.gif"), _message(attachment_url="https://cdn.example/b.gif"))


def test_changed_text_is_a_content_change() -> None:
    assert DiscordMessageContentNormalizer().changed(_message("before"), _message("after"))


def test_link_preview_hydration_is_not_a_content_change() -> None:
    normalizer = DiscordMessageContentNormalizer()
    message = "https://store.steampowered.com/app/2140510/Town_of_Salem_2/"
    automatic_preview = SimpleNamespace(
        type="link",
        url=message,
        title="Town of Salem 2",
        description="Discord-generated link preview",
    )

    assert not normalizer.changed(_message(message), _message(message, embeds=(automatic_preview,)))


def test_gif_preview_hydration_is_not_a_content_change() -> None:
    normalizer = DiscordMessageContentNormalizer()
    gif_preview = SimpleNamespace(type="gifv", url="https://cdn.discordapp.com/attachments/1/2/a.gif")
    assert not normalizer.changed(
        _message("https://cdn.discordapp.com/attachments/1/2/a.gif"),
        _message("https://cdn.discordapp.com/attachments/1/2/a.gif", embeds=(gif_preview,)),
    )
