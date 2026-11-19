"""HA-nnounce: record your voice and play it on the speakers of Home Assistant."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.requirements import RequirementsNotFound, async_process_requirements

from . import frontend, services, websocket
from .announcer import Announcement, Announcer, PlayOptions
from .const import DOMAIN, INTERCOM_BROADCAST, INTERCOM_REQUIREMENT, ROUTE_TTL
from .http import AnnounceAudioView, AnnounceUploadView
from .settings import AnnounceSettings, speaker_ids

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

TEXT = {
    "en": {"title": "Announcement", "panel": "Announcements", "all": "All speakers"},
    "it": {"title": "Annuncio", "panel": "Annunci", "all": "Tutti gli altoparlanti"},
}

type HannounceConfigEntry = ConfigEntry[HannounceData]


@dataclass
class Route:
    """Where the next intercom message of the broadcast camera goes."""

    targets: list[str]
    volume: float | None
    chime: str | None
    expires: float


@dataclass
class HannounceData:
    """Runtime data shared by the views, commands, services and cameras."""

    hass: HomeAssistant
    entry: ConfigEntry
    announcer: Announcer
    settings: AnnounceSettings
    intercom_ready: bool = False
    routes: dict[str, Route] = field(default_factory=dict)

    def text(self, key: str) -> str:
        """Return a short text in the server language."""
        language = self.hass.config.language.split("-")[0]
        return TEXT.get(language, TEXT["en"])[key]

    def speakers(self) -> list[str]:
        """Return the speakers offered to the user."""
        return speaker_ids(self.hass, self.settings)

    def speaker_name(self, entity_id: str) -> str:
        """Return the friendly name of a speaker."""
        if state := self.hass.states.get(entity_id):
            return state.name
        return entity_id.split(".", 1)[-1].replace("_", " ").title()

    @callback
    def play(
        self,
        announcement: Announcement,
        targets: list[str],
        volume: float | None,
    ) -> list[str]:
        """Play an announcement, return the speakers used."""
        return self.announcer.async_play(
            announcement,
            targets,
            PlayOptions(
                volume=volume,
                title=self.text("title"),
                announce_volume=self.settings.announce_volume,
            ),
        )

    @callback
    def set_route(
        self, targets: list[str], volume: float | None, chime: str | None
    ) -> None:
        """Choose where the next messages of the broadcast intercom go."""
        self.routes[INTERCOM_BROADCAST] = Route(
            targets=targets,
            volume=volume,
            chime=chime,
            expires=time.monotonic() + ROUTE_TTL,
        )

    def _route(self, key: str) -> Route | None:
        route = self.routes.get(key)
        if route and route.expires > time.monotonic():
            return route
        return None

    def intercom_targets(self, key: str, speaker: str | None) -> list[str]:
        """Return where an intercom message goes."""
        if speaker is not None:
            return [speaker]
        if route := self._route(key):
            return route.targets
        return self.speakers()

    async def async_play_pcm(
        self, pcm: bytes, key: str, speaker: str | None
    ) -> list[str]:
        """Encode raw 48 kHz mono PCM from the intercom and play it."""
        route = self._route(key) if speaker is None else None
        targets = self.intercom_targets(key, speaker)
        self.announcer.check_targets(targets)
        source = self.announcer.folder / f"in_{self.announcer.new_id()}.pcm"
        await self.hass.async_add_executor_job(source.write_bytes, pcm)
        try:
            announcement = await self.announcer.async_create(
                source,
                self.settings,
                source_kind="intercom",
                raw_pcm_rate=48000,
                chime=route.chime if route else None,
            )
        finally:
            await self.hass.async_add_executor_job(source.unlink, True)
        volume = route.volume if route else self.settings.volume_level
        return self.play(announcement, targets, volume)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register what lives as long as Home Assistant runs."""
    hass.http.register_view(AnnounceUploadView())
    hass.http.register_view(AnnounceAudioView())
    websocket.async_setup(hass)
    services.async_setup(hass)
    await frontend.async_register_module(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: HannounceConfigEntry
) -> bool:
    """Set up from a config entry."""
    settings = AnnounceSettings.from_options(entry.options)
    announcer = Announcer(hass, get_ffmpeg_manager(hass).binary)
    await announcer.async_start()
    runtime = HannounceData(
        hass=hass, entry=entry, announcer=announcer, settings=settings
    )
    entry.runtime_data = runtime
    hass.data[DOMAIN] = runtime

    if settings.show_panel:
        await frontend.async_register_panel(hass, runtime.text("panel"))

    if settings.intercom:
        runtime.intercom_ready = await _async_prepare_intercom(hass)
        if runtime.intercom_ready:
            await hass.config_entries.async_forward_entry_setups(
                entry, [Platform.CAMERA]
            )
    else:
        ir.async_delete_issue(hass, DOMAIN, "intercom_requirements")
    return True


async def _async_prepare_intercom(hass: HomeAssistant) -> bool:
    """Install aiortc the first time the intercom is turned on."""
    try:
        await async_process_requirements(hass, DOMAIN, [INTERCOM_REQUIREMENT])
        await hass.async_add_executor_job(_import_intercom)
    except (RequirementsNotFound, ImportError) as err:
        _LOGGER.error("The intercom needs %s: %s", INTERCOM_REQUIREMENT, err)
        ir.async_create_issue(
            hass,
            DOMAIN,
            "intercom_requirements",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="intercom_requirements",
            translation_placeholders={"requirement": INTERCOM_REQUIREMENT},
        )
        return False
    ir.async_delete_issue(hass, DOMAIN, "intercom_requirements")
    return True


def _import_intercom() -> None:
    """Import the WebRTC stack outside the event loop (it is slow)."""
    import dns.rdata  # noqa: PLC0415
    import dns.rdatatype  # noqa: PLC0415

    from . import intercom  # noqa: F401, PLC0415

    # aioice listens to mDNS (browsers hide their address behind abcd.local)
    # and parses every packet on the network with dnspython, which imports a
    # module per record type on first use. Load them all here, also for class
    # IN with the mDNS cache-flush bit (32769), so nothing loads in the loop.
    dns.rdata.load_all_types(disable_dynamic_load=False)
    for rdclass in (1, 32769):
        for rdtype in dns.rdatatype.RdataType:
            dns.rdata.get_rdata_class(rdclass, rdtype)


async def async_unload_entry(
    hass: HomeAssistant, entry: HannounceConfigEntry
) -> bool:
    """Unload a config entry."""
    runtime = entry.runtime_data
    if runtime.intercom_ready and not await hass.config_entries.async_unload_platforms(
        entry, [Platform.CAMERA]
    ):
        return False
    frontend.async_remove_panel(hass)
    await runtime.announcer.async_stop()
    hass.data.pop(DOMAIN, None)
    return True
