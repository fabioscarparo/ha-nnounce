"""Serve the card and the panel from the integration itself."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, FRONTEND_FILE, PANEL_ELEMENT, PANEL_URL_PATH, STATIC_URL

FRONTEND_PATH = Path(__file__).parent / "frontend" / FRONTEND_FILE
DATA_MODULE_URL = f"{DOMAIN}_module_url"


async def async_register_module(hass: HomeAssistant) -> None:
    """Serve the JavaScript module and load it on every dashboard."""
    if DATA_MODULE_URL in hass.data:
        return
    digest = await hass.async_add_executor_job(
        lambda: hashlib.sha256(FRONTEND_PATH.read_bytes()).hexdigest()[:12]
    )
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"{STATIC_URL}/{FRONTEND_FILE}", str(FRONTEND_PATH), True)]
    )
    url = f"{STATIC_URL}/{FRONTEND_FILE}?v={digest}"
    frontend.add_extra_js_url(hass, url)
    hass.data[DATA_MODULE_URL] = url


async def async_register_panel(hass: HomeAssistant, title: str) -> None:
    """Add the full page recorder to the sidebar."""
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title=title,
        sidebar_icon="mdi:bullhorn",
        module_url=hass.data[DATA_MODULE_URL],
        embed_iframe=False,
        require_admin=False,
    )


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the panel from the sidebar."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
