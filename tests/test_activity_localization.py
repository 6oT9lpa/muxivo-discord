from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_ROOT = ROOT / "activity" / "client" / "src"
LOCALES_ROOT = CLIENT_ROOT / "i18n" / "locales"
TRANSLATION_CALL = re.compile(r"(?:\$t|\bt)\(\s*[\"']([^\"']+)[\"']")
PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
TEXT_SUFFIXES = {".css", ".html", ".json", ".ts", ".vue"}


def load_locale(locale: str) -> dict[str, str]:
    path = LOCALES_ROOT / f"{locale}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_locale_dictionaries_have_matching_keys_and_placeholders() -> None:
    english = load_locale("en")
    russian = load_locale("ru")

    assert english.keys() == russian.keys()
    assert len(english) >= 250
    assert all(value.strip() for value in english.values())
    assert all(value.strip() for value in russian.values())

    for key, english_message in english.items():
        assert set(PLACEHOLDER.findall(english_message)) == set(PLACEHOLDER.findall(russian[key])), key


def test_literal_translation_keys_exist_in_both_locales() -> None:
    english = load_locale("en")
    russian = load_locale("ru")
    missing: dict[str, list[str]] = {}

    for path in CLIENT_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".vue"}:
            continue
        for key in TRANSLATION_CALL.findall(path.read_text(encoding="utf-8")):
            if key not in english or key not in russian:
                missing.setdefault(path.relative_to(ROOT).as_posix(), []).append(key)

    assert missing == {}


def test_activity_sources_are_valid_utf8_without_mojibake() -> None:
    forbidden_fragments = ("\ufffd", "Ã", "Â", "Ð", "Ñ")

    for path in CLIENT_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_bytes().decode("utf-8", errors="strict")
        assert "\x00" not in text, path
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{path}: found possible mojibake fragment {fragment!r}"


def test_language_switcher_is_available_in_public_and_panel_headers() -> None:
    switcher = (CLIENT_ROOT / "components" / "common" / "LanguageSwitcher.vue").read_text(encoding="utf-8")
    public_header = (CLIENT_ROOT / "components" / "common" / "AppHeader.vue").read_text(encoding="utf-8")
    panel_header = (CLIENT_ROOT / "components" / "panel" / "PanelTopbar.vue").read_text(encoding="utf-8")
    i18n_module = (CLIENT_ROOT / "i18n" / "index.ts").read_text(encoding="utf-8")

    assert "Languages" in switcher
    assert 'role="menu"' in switcher
    assert 'role="menuitemradio"' in switcher
    assert 'data-testid="language-menu-trigger"' in switcher
    assert "locale.toUpperCase()" not in switcher
    assert "selectLocale(option.code)" in switcher
    assert "<LanguageSwitcher />" in public_header
    assert "<LanguageSwitcher />" in panel_header
    assert '"muxivo-discord.activity.locale"' in i18n_module
    assert 'export type Locale = "en" | "ru"' in i18n_module


def test_editor_previews_stay_at_the_top_while_scrolling() -> None:
    component_names = ("WelcomeModulePanel.vue", "DevBlogPanel.vue", "CreatorAlertsPanel.vue")
    for component_name in component_names:
        source = (CLIENT_ROOT / "components" / "panel" / component_name).read_text(encoding="utf-8")
        assert "preview-editor-grid" in source, component_name
        assert "sticky-preview" in source, component_name

    styles = (CLIENT_ROOT / "style.css").read_text(encoding="utf-8")
    assert 'grid-template-areas: "editor preview"' in styles
    assert '"preview"\n      "editor"' in styles
    assert ".sticky-preview" in styles
    assert "position: sticky" in styles
    assert "overflow-y: auto" not in styles[styles.index(".sticky-preview"):styles.index(".discord-preview-header")]
    assert "overflow-x: clip" in styles


def test_welcome_and_dev_blog_previews_render_configured_images() -> None:
    welcome_preview = (CLIENT_ROOT / "components" / "panel" / "DiscordEmbedPreview.vue").read_text(encoding="utf-8")
    dev_blog = (CLIENT_ROOT / "components" / "panel" / "DevBlogPanel.vue").read_text(encoding="utf-8")

    assert 'v-if="config.thumbnail_url"' in welcome_preview
    assert "AuthenticatedImage" in welcome_preview
    assert ':src="config.thumbnail_url"' in welcome_preview
    assert 'v-if="config.footer_icon_url"' in welcome_preview
    assert ':src="config.footer_icon_url"' in welcome_preview
    assert 'v-if="embed.image_url"' in dev_blog
    assert "AuthenticatedImage" in dev_blog
    assert ':src="embed.image_url"' in dev_blog


def test_public_layout_and_footer_integrations_are_stable() -> None:
    headline = (CLIENT_ROOT / "components" / "common" / "StaggeredHeadline.vue").read_text(encoding="utf-8")
    footer = (CLIENT_ROOT / "components" / "common" / "PublicFooter.vue").read_text(encoding="utf-8")
    styles = (CLIENT_ROOT / "style.css").read_text(encoding="utf-8")

    assert "visibleText" in headline
    assert "typewriter-copy" in headline
    assert "'is-complete': visibleCount >= characters.length" in headline
    assert "typewriter-letter" not in headline
    assert "https://boosty.to/6o9lpa" in footer
    assert "Arnetik" not in footer
    assert "handleExternalClick" in footer
    assert "feature-grid > .reveal-on-scroll" in styles
    assert "word-break: normal" in styles
    assert ".typewriter-copy.is-complete::after" in styles


def test_about_module_cards_keep_equal_heights_and_aligned_mockups() -> None:
    styles = (CLIENT_ROOT / "style.css").read_text(encoding="utf-8")

    wrapper_rule = styles[styles.index(".about-module-grid .reveal-on-scroll"):
                          styles.index(".about-module-panel {")]
    panel_rule = styles[styles.index(".about-module-panel {"):
                        styles.index(".about-module-panel h3")]

    assert "display: flex" in wrapper_rule
    assert "height: 100%" in wrapper_rule
    assert "grid-template-rows: 1fr auto" in panel_rule
    assert "width: 100%" in panel_rule
    assert "height: 100%" in panel_rule


def test_activity_logs_use_localized_titles_and_structured_details() -> None:
    panel = (CLIENT_ROOT / "components" / "panel" / "LogsPanel.vue").read_text(encoding="utf-8")
    presenter = (CLIENT_ROOT / "utils" / "logPresentation.ts").read_text(encoding="utf-8")

    assert "logEventTitle" in panel
    assert "logDetailRows" in panel
    assert 'member_role_update: "logs.event.member_role_update"' in presenter
    assert 'moderation_ban: "logs.event.moderation_ban"' in presenter
    assert 'channel_delete: "logs.event.channel_delete"' in presenter


def test_preview_images_use_authenticated_media_proxy() -> None:
    image_component = (CLIENT_ROOT / "components" / "common" / "AuthenticatedImage.vue").read_text(encoding="utf-8")
    media_router = (ROOT / "activity" / "server" / "routers" / "media.py").read_text(encoding="utf-8")

    assert "/api/media/image" in image_component
    assert "Authorization" in image_component
    assert 'APIRouter(prefix="/api/media"' in media_router
    assert "ensure_panel_access" in media_router
