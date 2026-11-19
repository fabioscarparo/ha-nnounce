"""Setting up, the card and the panel, unloading."""

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.hannounce.const import DOMAIN
from custom_components.hannounce.settings import AnnounceSettings, speaker_ids


async def test_card_and_panel(hass: HomeAssistant, players, setup_integration, hass_client) -> None:
    entry = await setup_integration()
    url = hass.data[f"{DOMAIN}_module_url"]
    assert url.startswith("/hannounce_static/hannounce.js?v=")
    response = await (await hass_client()).get(url)
    assert response.status == 200
    assert 'const CARD_TYPE = "hannounce-card"' in await response.text()

    panel = hass.data[DATA_PANELS]["hannounce"]
    assert panel.config["_panel_custom"]["name"] == "hannounce-panel"
    assert panel.require_admin is False

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert "hannounce" not in hass.data[DATA_PANELS]
    assert DOMAIN not in hass.data


async def test_panel_can_be_hidden(hass: HomeAssistant, players, setup_integration) -> None:
    await setup_integration(show_panel=False)
    assert "hannounce" not in hass.data.get(DATA_PANELS, {})


async def test_default_speakers_skip_hidden_and_disabled(hass: HomeAssistant, players) -> None:
    registry = er.async_get(hass)
    registry.async_update_entity("media_player.desk", hidden_by=er.RegistryEntryHider.USER)
    registry.async_update_entity("media_player.kitchen", disabled_by=er.RegistryEntryDisabler.USER)
    settings = AnnounceSettings.from_options({})
    assert speaker_ids(hass, settings) == ["media_player.living_room"]
