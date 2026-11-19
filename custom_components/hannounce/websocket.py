"""WebSocket commands used by the card and the panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import CHIMES, DOMAIN, EVENT_ANNOUNCED, INTERCOM_BROADCAST
from .settings import describe_speakers

VOLUME = vol.Any("keep", vol.All(vol.Coerce(float), vol.Range(min=0, max=100)))


def _volume(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    if value == "keep":
        return None
    return float(value) / 100


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the commands."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_replay)
    websocket_api.async_register_command(hass, ws_route)
    websocket_api.async_register_command(hass, ws_subscribe)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Send every new announcement, so the card can confirm intercom messages.

    Users that are not admins can't subscribe to events of integrations, so
    this command forwards the integration's own event.
    """

    @callback
    def forward(event: Event) -> None:
        data = dict(event.data)
        data.pop("user_id", None)
        connection.send_message(websocket_api.event_message(msg["id"], data))

    connection.subscriptions[msg["id"]] = hass.bus.async_listen(EVENT_ANNOUNCED, forward)
    connection.send_result(msg["id"])


def _runtime(hass: HomeAssistant, connection, msg_id: int):
    runtime = hass.data.get(DOMAIN)
    if runtime is None:
        connection.send_error(msg_id, "not_set_up", "HA-nnounce is not set up")
    return runtime


def _broadcast_camera(hass: HomeAssistant, runtime) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "camera", DOMAIN, f"{runtime.entry.entry_id}_intercom_{INTERCOM_BROADCAST}"
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info"})
@callback
def ws_info(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the speakers, the defaults and the intercom state."""
    if (runtime := _runtime(hass, connection, msg["id"])) is None:
        return
    settings = runtime.settings
    labs = False
    try:
        from homeassistant.components.labs import (  # noqa: PLC0415
            async_is_preview_feature_enabled,
        )

        labs = async_is_preview_feature_enabled(hass, "camera", "two_way_audio")
    except ImportError:
        pass
    connection.send_result(
        msg["id"],
        {
            "speakers": describe_speakers(hass, runtime.speakers()),
            "defaults": {
                "set_volume": settings.set_volume,
                "volume": settings.volume,
                "chime": settings.chime,
                "max_duration": settings.max_duration,
            },
            "chimes": list(CHIMES),
            "intercom": {
                "enabled": settings.intercom,
                "ready": runtime.intercom_ready,
                "labs": labs,
                "broadcast_entity_id": _broadcast_camera(hass, runtime)
                if runtime.intercom_ready
                else None,
            },
            "last": runtime.announcer.last.as_dict()
            if runtime.announcer.last and runtime.announcer.get(runtime.announcer.last.id)
            else None,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/replay",
        vol.Optional("targets"): [cv.entity_id],
        vol.Optional("volume"): VOLUME,
    }
)
@callback
def ws_replay(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Play the last message again."""
    if (runtime := _runtime(hass, connection, msg["id"])) is None:
        return
    last = runtime.announcer.last
    if last is None or runtime.announcer.get(last.id) is None:
        connection.send_error(msg["id"], "no_message", "There is no recent message")
        return
    try:
        used = runtime.play(
            last,
            msg.get("targets") or last.targets,
            _volume(msg.get("volume"), runtime.settings.volume_level),
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "play_failed", str(err))
        return
    connection.send_result(msg["id"], {**last.as_dict(), "targets": used})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/route",
        vol.Required("targets"): vol.All([cv.entity_id], vol.Length(min=1)),
        vol.Optional("volume"): VOLUME,
        vol.Optional("chime"): vol.In(CHIMES),
    }
)
@callback
def ws_route(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Choose the speakers of the next intercom message (used by the apps)."""
    if (runtime := _runtime(hass, connection, msg["id"])) is None:
        return
    if not runtime.intercom_ready:
        connection.send_error(msg["id"], "intercom_off", "The intercom is not on")
        return
    try:
        targets = runtime.announcer.check_targets(msg["targets"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "no_targets", str(err))
        return
    runtime.set_route(
        targets,
        _volume(msg.get("volume"), runtime.settings.volume_level),
        msg.get("chime"),
    )
    connection.send_result(
        msg["id"], {"entity_id": _broadcast_camera(hass, runtime), "targets": targets}
    )
