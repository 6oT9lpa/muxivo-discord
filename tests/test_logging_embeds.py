import pytest
from datetime import datetime, timezone

from presentation.embeds.logging_embed import (
    VoiceLogEmbedBuilder,
    MessageLogEmbedBuilder,
    MessageDeleteLogEmbedBuilder,
    MemberEventEmbedBuilder,
)


class MockMember:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
        self.mention = f"<@{id}>"
        self.joined_at = None
        self.roles = []
        self._str = name

    def __str__(self):
        return self._str


class MockUser:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
        self._str = name

    def __str__(self):
        return self._str


def test_voice_log_embed_build_join():
    member = MockMember(123456789, "TestUser")
    embed = VoiceLogEmbedBuilder.build_join(member, "General Voice")
    
    assert embed.title == "TestUser (123456789)"
    assert embed.color.value == 0x57F287
    
    field_names = [f.name for f in embed.fields]
    assert "Channel:" in field_names


def test_voice_log_embed_build_leave():
    member = MockMember(123456789, "TestUser")
    embed = VoiceLogEmbedBuilder.build_leave(member, "General Voice")
    
    assert embed.title == "TestUser (123456789)"
    assert embed.color.value == 0xED4245
    
    field_names = [f.name for f in embed.fields]
    assert "Channel:" in field_names


def test_voice_log_embed_build_move():
    member = MockMember(123456789, "TestUser")
    embed = VoiceLogEmbedBuilder.build_move(member, "Voice 1", "Voice 2")
    
    assert embed.title == "TestUser (123456789)"
    assert embed.color.value == 0x5865F2
    
    field_names = [f.name for f in embed.fields]
    assert "Before Channel:" in field_names
    assert "After Channel:" in field_names


def test_message_log_embed_build_delete():
    author = MockUser(123456789, "TestUser")
    embed = MessageLogEmbedBuilder.build_delete(author)
    
    assert embed.title == "TestUser (123456789)"
    assert embed.color.value == 0xED4245


def test_message_log_embed_build_edit():
    author = MockUser(123456789, "TestUser")
    embed = MessageLogEmbedBuilder.build_edit(author)
    
    assert embed.title == "TestUser (123456789)"
    assert embed.color.value == 0xFEE75C


def test_member_event_embed_build_leave():
    member = MockMember(123456789, "TestUser")
    embed = MemberEventEmbedBuilder.build_leave(member)

    assert embed.title == "Member left: TestUser (ID: 123456789)"
    assert embed.color.value == 0xED4245
    assert any(field.name == "Event" and field.value == "member_leave" for field in embed.fields)


def test_message_delete_embed_shows_deleted_attachment_instead_of_empty_message():
    author = MockMember(123456789, "TestUser")
    message = type("Message", (), {
        "id": 44,
        "author": author,
        "content": "",
        "attachments": [
            type("Attachment", (), {
                "filename": "casino.png",
                "url": "https://cdn.discordapp.com/attachments/1/2/casino.png",
                "content_type": "image/png",
                "size": 2048,
            })(),
        ],
    })()

    embed = MessageDeleteLogEmbedBuilder.build_delete(message)

    fields = {field.name: field.value for field in embed.fields}
    assert "текст отсутствует" in fields["Содержание"]
    assert "casino.png" in fields["Удалённые вложения"]
    assert embed.image.url == "https://cdn.discordapp.com/attachments/1/2/casino.png"


def test_member_event_embed_build_update():
    member = MockMember(123456789, "TestUser")
    embed = MemberEventEmbedBuilder.build_update(member, ["pending: True -> False"])

    assert embed.title == "Member updated: TestUser (ID: 123456789)"
    assert embed.color.value == 0xFEE75C
    assert any(field.name == "Changes" and "pending: True -> False" in field.value for field in embed.fields)


def test_member_event_embed_build_pending_update():
    member = MockMember(123456789, "TestUser")
    embed = MemberEventEmbedBuilder.build_pending_update(member, True, False)

    assert embed.title == "Проверка участника обновлена: TestUser (ID: 123456789)"
    assert embed.color.value == 0x57F287
    assert any(field.name == "Статус" and "ожидает проверки" in field.value for field in embed.fields)
