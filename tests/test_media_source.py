"""Messages as a media source, like text-to-speech."""

import pytest
from homeassistant.components import media_source
from homeassistant.core import HomeAssistant

from .conftest import needs_ffmpeg


@needs_ffmpeg
async def test_browse_and_resolve(hass: HomeAssistant, players, setup_integration, make_wav, tmp_path) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    await setup_integration()
    response = await hass.services.async_call(
        "hannounce", "announce", {"entity_id": ["media_player.kitchen", "media_player.desk"], "file": str(make_wav())},
        blocking=True, return_response=True,
    )

    root = await media_source.async_browse_media(hass, "media-source://hannounce")
    assert root.title == "HA-nnounce"
    (child,) = root.children
    assert child.media_content_id == f"media-source://hannounce/{response['id']}.mp3"
    assert child.can_play and "Kitchen" in child.title and "Desk" in child.title

    resolved = await media_source.async_resolve_media(hass, child.media_content_id, None)
    assert resolved.url == f"/api/hannounce/audio/{response['id']}.mp3"
    assert resolved.mime_type == "audio/mpeg"

    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, "media-source://hannounce/old.mp3", None)


async def test_empty_list(hass: HomeAssistant, players, setup_integration) -> None:
    await setup_integration()
    root = await media_source.async_browse_media(hass, "media-source://hannounce")
    assert root.children == []
