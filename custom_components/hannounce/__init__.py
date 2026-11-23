"""HA-nnounce: record your voice and play it on the speakers of Home Assistant."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.requirements import RequirementsNotFound, async_process_requirements

from . import frontend, services, websocket
from .announcer import Announcement, Announcer, PlayOptions, QuietHoursError
from .const import (
    DOMAIN,
    INTERCOM_BROADCAST,
    INTERCOM_REQUIREMENT,
    QUIET_MODE_SKIP,
    ROUTE_TTL,
)
from .http import AnnounceAudioView, AnnounceChimeView, AnnounceUploadView
from .settings import AnnounceSettings, speaker_ids

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

TEXT = {
    "en": {"title": "Announcement", "panel": "Announcements", "all": "All speakers"},
    "it": {"title": "Annuncio", "panel": "Annunci", "all": "Tutti gli altoparlanti"},
    "de": {"title": "Durchsage", "panel": "Durchsagen", "all": "Alle Lautsprecher"},
    "fr": {"title": "Annonce", "panel": "Annonces", "all": "Tous les haut-parleurs"},
    "es": {"title": "Anuncio", "panel": "Anuncios", "all": "Todos los altavoces"},
    "nl": {"title": "Omroep", "panel": "Omroepen", "all": "Alle luidsprekers"},
    "ro": {"title": "Anunț", "panel": "Anunțuri", "all": "Toate difuzoarele"},
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

    def quiet_info(self) -> dict[str, Any]:
        """Return the quiet hours configuration and current active state."""
        settings = self.settings
        return {
            "enabled": settings.quiet_hours,
            "active": settings.is_quiet_active(self.hass),
            "mode": settings.quiet_mode,
            "volume": settings.quiet_volume,
            "speakers": list(settings.quiet_speakers),
            "start": settings.quiet_start[:5],
            "end": settings.quiet_end[:5],
            "entity_id": settings.quiet_entity,
        }

    def tts_engine(self, override: str | None = None) -> str | None:
        """Return the resolved Home Assistant TTS engine, or None if unavailable."""
        from homeassistant.components import tts  # noqa: PLC0415

        if tts.DOMAIN not in self.hass.config.components:
            return None
        try:
            return tts.async_resolve_engine(
                self.hass, override or self.settings.tts_entity or None
            )
        except KeyError:
            return None

    def tts_info(self) -> dict[str, Any]:
        """Return whether a Home Assistant TTS engine is available."""
        engine = self.tts_engine()
        return {"available": engine is not None, "engine": engine}

    def plan_playback(
        self,
        targets: list[str],
        volume: float | None,
        *,
        force: bool = False,
    ) -> tuple[list[str], dict[str, float | None]]:
        """Validate targets and apply quiet hours rules, returning targets and volumes."""
        valid = self.announcer.check_targets(targets)
        if not force and self.settings.is_quiet_active(self.hass):
            if self.settings.quiet_mode == QUIET_MODE_SKIP:
                valid = [
                    entity_id
                    for entity_id in valid
                    if not self.settings.affects_speaker(entity_id)
                ]
                if not valid:
                    raise QuietHoursError
                return valid, {entity_id: volume for entity_id in valid}

            cap = self.settings.quiet_volume_level
            volumes: dict[str, float | None] = {}
            for entity_id in valid:
                if self.settings.affects_speaker(entity_id):
                    if volume is not None:
                        volumes[entity_id] = min(volume, cap)
                    else:
                        state = self.hass.states.get(entity_id)
                        current = (
                            state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
                            if state
                            else None
                        )
                        volumes[entity_id] = (
                            cap if current is not None and current > cap else None
                        )
                else:
                    volumes[entity_id] = volume
            return valid, volumes

        return valid, {entity_id: volume for entity_id in valid}

    async def async_create_tts(
        self,
        message: str,
        *,
        source_kind: str,
        user_id: str | None = None,
        chime: str | None = None,
        tts_entity: str | None = None,
        language: str | None = None,
    ) -> Announcement:
        """Generate TTS audio via Home Assistant and encode it through the pipeline."""
        from homeassistant.components import tts  # noqa: PLC0415

        cleaned = message.strip()
        if not cleaned:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="empty_message"
            )
        engine = self.tts_engine(tts_entity)
        if engine is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="tts_unavailable"
            )
        try:
            media_id = tts.generate_media_source_id(
                self.hass, cleaned, engine=engine, language=language or None
            )
            extension, data = await tts.async_get_media_source_audio(
                self.hass, media_id
            )
        except (HomeAssistantError, ValueError, KeyError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="tts_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if not data:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="tts_failed",
                translation_placeholders={"error": "empty audio"},
            )
        suffix = f".{extension.lstrip('.')}" if extension else ".mp3"
        source = self.announcer.folder / f"tts_{self.announcer.new_id()}{suffix}"
        await self.hass.async_add_executor_job(source.write_bytes, data)
        try:
            return await self.announcer.async_create(
                source,
                self.settings,
                source_kind=source_kind,
                user_id=user_id,
                chime=chime,
                min_voice_seconds=0.05,
            )
        finally:
            await self.hass.async_add_executor_job(source.unlink, True)

    @callback
    def play(
        self,
        announcement: Announcement,
        targets: list[str],
        volume: float | None,
        *,
        force: bool = False,
    ) -> list[str]:
        """Play an announcement, return the speakers used."""
        valid, speaker_volumes = self.plan_playback(targets, volume, force=force)
        return self.announcer.async_play(
            announcement,
            valid,
            PlayOptions(
                volume=volume,
                title=self.text("title"),
                announce_volume=self.settings.announce_volume,
            ),
            speaker_volumes=speaker_volumes,
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
        volume = route.volume if route else self.settings.volume_level
        self.plan_playback(targets, volume)
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
        return self.play(announcement, targets, volume)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register what lives as long as Home Assistant runs."""
    hass.http.register_view(AnnounceUploadView())
    hass.http.register_view(AnnounceAudioView())
    hass.http.register_view(AnnounceChimeView())
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
