"""The config flow and the options."""

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
    defaults = {field.schema: field.default() for field in result["data_schema"].schema}
    assert defaults["volume"] == 70
    assert defaults["announce_volume"] is True

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**DEFAULT_OPTIONS, "volume": 40, "chime": "soft"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["volume"] == 40
    assert entry.runtime_data.settings.chime == "soft"
