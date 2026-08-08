from types import SimpleNamespace

from presentation.embeds.deleted_message_attachment_presentation import (
    DeletedMessageAttachmentPresenter,
)


def test_presenter_renders_attachment_metadata_and_image_preview() -> None:
    presentation = DeletedMessageAttachmentPresenter.present(
        (
            SimpleNamespace(
                filename="casino [bonus].png",
                url="https://cdn.discordapp.com/attachments/1/2/casino.png",
                content_type="image/png",
                size=2_048,
            ),
        )
    )

    assert presentation.preview_url == "https://cdn.discordapp.com/attachments/1/2/casino.png"
    assert "casino \\[bonus\\].png" in presentation.field_value
    assert "image/png, 2.0 KiB" in presentation.field_value


def test_presenter_limits_attachment_count_and_does_not_link_invalid_urls() -> None:
    attachments = tuple(
        SimpleNamespace(
            filename=f"file-{index}.txt",
            url="not-a-url" if index == 0 else f"https://cdn.discordapp.com/{index}",
            content_type="text/plain",
            size=1,
        )
        for index in range(6)
    )

    presentation = DeletedMessageAttachmentPresenter.present(attachments)

    assert "[file-0.txt]" not in presentation.field_value
    assert "… and 1 more attachment(s)" in presentation.field_value
    assert presentation.preview_url is None
