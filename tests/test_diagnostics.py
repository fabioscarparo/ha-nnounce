"""Diagnostics and translation consistency tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

from homeassistant.core import HomeAssistant

from custom_components.hannounce import TEXT
from custom_components.hannounce.diagnostics import async_get_config_entry_diagnostics

INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "hannounce"


async def test_diagnostics_reports_runtime_without_leaking_url(
    hass: HomeAssistant, players, setup_integration
) -> None:
    players.set_muted("media_player.kitchen", True)
    entry = await setup_integration(custom_chime="/media/secret_dir/chime.mp3")

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert data["integration_version"]
    assert data["home_assistant_version"]
    assert data["entry"]["options"]["volume"] == 70
    assert data["entry"]["options"]["custom_chime"] == "**REDACTED**"
    assert data["url"] == {"available": True, "scheme": "http"}
    dumped = json.dumps(data)
    assert "homeassistant.local" not in dumped
    assert "secret_dir" not in dumped

    runtime = data["runtime"]
    assert runtime["custom_chime_configured"] is True
    assert runtime["resume_playback"] is False
    assert runtime["alexa"] == {"enabled": False, "external_https_available": False}
    assert runtime["tts"] == {"available": False, "engine": None}
    assert runtime["quiet"]["enabled"] is False
    assert runtime["intercom"]["enabled"] is False
    assert runtime["intercom"]["ready"] is False
    assert runtime["recent_announcements"] == 0

    by_id = {s["entity_id"]: s for s in runtime["speakers"]}
    assert set(by_id) == {"media_player.desk", "media_player.kitchen", "media_player.living_room"}
    assert by_id["media_player.kitchen"]["is_volume_muted"] is True
    assert by_id["media_player.kitchen"]["features"]["volume_mute"] is True
    assert by_id["media_player.kitchen"]["features"]["seek"] is False
    assert by_id["media_player.living_room"]["features"]["media_announce"] is True


async def test_diagnostics_alexa_enabled_does_not_leak_external_url(
    hass: HomeAssistant, players, setup_integration
) -> None:
    hass.config.external_url = "https://secret-instance.ui.nabu.casa"
    entry = await setup_integration(alexa_support=True, resume_playback=True)

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert data["runtime"]["resume_playback"] is True
    assert data["runtime"]["alexa"] == {
        "enabled": True,
        "external_https_available": True,
    }
    assert "secret-instance" not in json.dumps(data)


def _flat_items(obj: dict, prefix: str = "") -> dict[str, str]:
    items: dict[str, str] = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flat_items(value, path))
        elif isinstance(value, str):
            items[path] = value
    return items


def _placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{(\w+)\}", text))


def test_translations_match_strings_and_have_no_long_dashes() -> None:
    strings = _flat_items(
        json.loads((INTEGRATION_DIR / "strings.json").read_text(encoding="utf-8"))
    )
    translations_dir = INTEGRATION_DIR / "translations"
    files = sorted(translations_dir.glob("*.json"))
    languages = {f.stem for f in files}
    assert languages == {"de", "en", "es", "fr", "it", "nl", "ro"}
    assert set(TEXT) == languages
    for path in files:
        content = _flat_items(json.loads(path.read_text(encoding="utf-8")))
        assert set(content) == set(strings), f"key mismatch in {path.name}"
        for key, text in content.items():
            assert "\u2013" not in text and "\u2014" not in text, f"long dash in {path.name}: {text}"
            assert _placeholders(text) == _placeholders(strings[key]), (
                f"placeholder mismatch in {path.name}:{key}"
            )
