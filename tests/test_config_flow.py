"""The config flow and the options."""

from pathlib import Path

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.hannounce.const import DOMAIN

from .conftest import DEFAULT_OPTIONS


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DEFAULT_OPTIONS, "volume": 55.0})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA-nnounce"
    assert result["data"] == {}
    # Numbers from the slider are stored as integers
    assert result["options"]["volume"] == 55
    assert isinstance(result["options"]["volume"], int)


async def test_only_one_entry(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, options=DEFAULT_OPTIONS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_saves_and_reloads(hass: HomeAssistant, players, setup_integration) -> None:
    entry = await setup_integration()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    defaults = {
        field.schema: field.default()
        for field in result["data_schema"].schema
        if field.default is not vol.UNDEFINED
    }
    assert defaults["volume"] == 70
    assert defaults["announce_volume"] is True
    assert defaults["resume_playback"] is False
    assert defaults["alexa_support"] is False
    assert defaults["voice_enhancement"] is True
    assert defaults["quiet_hours"] is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            **DEFAULT_OPTIONS,
            "volume": 40,
            "chime": "soft",
            "resume_playback": True,
            "voice_enhancement": False,
            "quiet_hours": True,
            "quiet_start": "22:30:00",
            "quiet_end": "07:00:00",
            "quiet_mode": "skip",
            "quiet_volume": 20.0,
            "quiet_speakers": ["media_player.kitchen"],
            "quiet_entity": "input_boolean.sleep_mode",
            "tts_entity": "tts.piper",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["volume"] == 40
    settings = entry.runtime_data.settings
    assert settings.chime == "soft"
    assert settings.resume_playback is True
    assert settings.alexa_support is False
    assert settings.voice_enhancement is False
    assert settings.quiet_hours is True
    assert settings.quiet_start == "22:30:00"
    assert settings.quiet_mode == "skip"
    assert settings.quiet_volume == 20
    assert settings.quiet_speakers == ("media_player.kitchen",)
    assert settings.quiet_entity == "input_boolean.sleep_mode"
    assert settings.tts_entity == "tts.piper"


async def test_custom_chime_validation(
    hass: HomeAssistant, players, setup_integration, make_wav, tmp_path: Path
) -> None:
    entry = await setup_integration()
    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Path outside allowlist_external_dirs is rejected
    bad_path = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "custom_chime": "/etc/hosts"},
    )
    assert bad_path["type"] is FlowResultType.FORM
    assert bad_path["errors"] == {"custom_chime": "path_not_allowed"}

    hass.config.allowlist_external_dirs = {str(tmp_path)}

    # Missing file inside allowed dir is rejected
    missing = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "custom_chime": str(tmp_path / "missing.wav")},
    )
    assert missing["type"] is FlowResultType.FORM
    assert missing["errors"] == {"custom_chime": "file_not_found"}

    # Selecting Custom chime without a path is rejected
    no_file = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "chime": "custom"},
    )
    assert no_file["type"] is FlowResultType.FORM
    assert no_file["errors"] == {"chime": "custom_chime_missing"}

    # Valid file with Custom chime succeeds
    chime_file = make_wav("bell.wav", seconds=0.6)
    ok = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "chime": "custom", "custom_chime": str(chime_file)},
    )
    assert ok["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.settings.chime == "custom"
    assert entry.runtime_data.settings.custom_chime == str(chime_file)


async def test_alexa_support_requires_external_https_url(
    hass: HomeAssistant, players, setup_integration
) -> None:
    entry = await setup_integration()
    result = await hass.config_entries.options.async_init(entry.entry_id)

    # No external URL configured
    no_ext = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "alexa_support": True},
    )
    assert no_ext["type"] is FlowResultType.FORM
    assert no_ext["errors"] == {"alexa_support": "external_https_required"}

    # Plain HTTP external URL is rejected
    hass.config.external_url = "http://my-home.example.com"
    http_ext = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "alexa_support": True},
    )
    assert http_ext["type"] is FlowResultType.FORM
    assert http_ext["errors"] == {"alexa_support": "external_https_required"}

    # Raw IP HTTPS URL is rejected (Amazon requires a domain with trusted cert)
    hass.config.external_url = "https://203.0.113.10:8123"
    ip_ext = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "alexa_support": True},
    )
    assert ip_ext["type"] is FlowResultType.FORM
    assert ip_ext["errors"] == {"alexa_support": "external_https_required"}

    # Valid external HTTPS domain succeeds
    hass.config.external_url = "https://my-home.ui.nabu.casa"
    ok = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_OPTIONS, "alexa_support": True},
    )
    assert ok["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.settings.alexa_support is True
