"""Diagnostics and translation consistency tests."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant

from custom_components.hannounce.diagnostics import async_get_config_entry_diagnostics

INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "hannounce"


async def test_diagnostics_reports_runtime_without_leaking_url(
    hass: HomeAssistant, players, setup_integration
) -> None:
    players.set_muted("media_player.kitchen", True)
    entry = await setup_integration()

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert data["integration_version"]
    assert data["home_assistant_version"]
    assert data["entry"]["options"]["volume"] == 70
    assert data["url"] == {"available": True, "scheme": "http"}
    assert "homeassistant.local" not in json.dumps(data)

    runtime = data["runtime"]
    assert runtime["intercom"]["enabled"] is False
    assert runtime["intercom"]["ready"] is False
    assert runtime["recent_announcements"] == 0

    by_id = {s["entity_id"]: s for s in runtime["speakers"]}
    assert set(by_id) == {"media_player.desk", "media_player.kitchen", "media_player.living_room"}
    assert by_id["media_player.kitchen"]["is_volume_muted"] is True
    assert by_id["media_player.kitchen"]["features"]["volume_mute"] is True
    assert by_id["media_player.living_room"]["features"]["media_announce"] is True


def _flat_keys(obj: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _flat_keys(value, path)
        else:
            keys.add(path)
    return keys


def _flat_values(obj: dict) -> list[str]:
    values: list[str] = []
    for value in obj.values():
        if isinstance(value, dict):
            values.extend(_flat_values(value))
        elif isinstance(value, str):
            values.append(value)
    return values


def test_translations_match_strings_and_have_no_long_dashes() -> None:
    strings = json.loads((INTEGRATION_DIR / "strings.json").read_text(encoding="utf-8"))
    expected_keys = _flat_keys(strings)
    translations_dir = INTEGRATION_DIR / "translations"
    files = sorted(translations_dir.glob("*.json"))
    assert {f.stem for f in files} == {"de", "en", "es", "fr", "it", "nl"}
    for path in files:
        content = json.loads(path.read_text(encoding="utf-8"))
        assert _flat_keys(content) == expected_keys, f"key mismatch in {path.name}"
        for text in _flat_values(content):
            assert "\u2013" not in text and "\u2014" not in text, f"long dash in {path.name}: {text}"
