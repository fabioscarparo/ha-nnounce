<h1 align="center">HA-nnounce</h1>

<p align="center">
  <strong>Record your voice from your phone or browser,<br>
  and play it locally on your Home Assistant speakers.</strong>
</p>

<p align="center">
  <a href="https://hacs.xyz/docs/faq/custom_repositories"><img alt="HACS Custom" src="https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistantcommunitystore&logoColor=fff"></a>
  <a href="https://www.home-assistant.io/"><img alt="Home Assistant 2026.11+" src="https://img.shields.io/badge/Home_Assistant-2026.11%2B-18BCF2?logo=homeassistant&logoColor=fff"></a>
  <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-333"></a>
</p>

HA-nnounce turns Home Assistant `media_player` entities into a local, whole-home announcement system. Audio is recorded on your device, processed locally by Home Assistant, and delivered directly to speakers via `media-source://hannounce/...` with no cloud services involved.

**Choose the speakers, hold the microphone button, talk, and release to send.**

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/wall-dark.svg">
  <img alt="HA-nnounce announcement cards on a Home Assistant dashboard, showing ready, recording and sent states, with individual room cards and colors" src="docs/images/wall-light.svg">
</picture>

## Features

- **UI:** Dedicated sidebar panel and `custom:hannounce-card` (no dashboard resource to add, visual editor, EN/IT, light/dark themes).
- **Audio pipeline:** Local `ffmpeg` processing with silence trimming, EBU R128 loudness normalization, synthesized chimes, and MP3 encoding.
- **Playback control:** Dedicated announcement volume (where supported) or temporary volume override with automatic restoration.
- **Two-way audio intercom (Labs):** Exposes speakers as WebRTC intercom cameras via `aiortc` for Home Assistant's native *Start talking* UI.
- **Automations & history:** `hannounce.announce` and `hannounce.replay` actions, `hannounce_announced` event, and 1-hour retention in the Media panel.

## Architecture

```text
Browser / App (MediaRecorder) ──► POST /api/hannounce/announce
                                           │
                                           ▼
                                  ffmpeg (trim, EBU R128, chime, MP3)
                                           │
                                           ▼
                                  media_player.volume_set / play_media
                                  (media-source://hannounce/<id>.mp3)
                                           │
                                           ▼
                                  Speaker fetches signed local URL
                                           │
                                           ▼
                                  Wait for finish ──► Restore volume

iOS / Start talking (Labs) ──► WebRTC (aiortc camera) ──► Same pipeline on stop
```

## Supported speakers

Works with any Home Assistant `media_player` integration capable of playing audio from a local URL (no brand-specific code).

| Integration | Behavior |
|---|---|
| **Sonos, Music Assistant, Squeezebox, Bang & Olufsen** | Native announcement mode: ducks music, plays at the speaker's announcement volume, resumes playback. |
| **ESPHome (incl. Voice PE)** | Native announcement mode: ducks music and resumes playback. |
| **Google Cast (Home, Nest, Chromecast, groups)** | Local Cast playback as standard audio (music stops and does not resume). No Google cloud/SDK required. |
| **DLNA/UPnP, HEOS, Bluesound, LinkPlay, WiiM, MusicCast, SoundTouch, OpenHome, MPD, VLC, Kodi, Apple TV, forked-daapd, Fully Kiosk, UniFi Protect, Roku, Dune HD, Panasonic Viera** | Plays as a standard audio track. |
| **Custom integrations (e.g. Browser Mod)** | Receives a signed audio URL (add manually in integration options). |

**Google Home:** speakers work through Home Assistant's Google Cast integration. Google Assistant broadcast only accepts text, so it cannot play a recording.

**Not supported:** Players that cannot play arbitrary audio URLs (e.g., Alexa/Echo, Spotify).  
*Note: Tested on HA 2026.11.1 with simulated players; not every listed hardware integration has been verified on physical devices.*

## Requirements & Installation

**Requirements:**
- Home Assistant **2026.11+** with `ffmpeg` (included in HA OS and official containers).
- A local URL reachable by speakers configured in **Settings > System > Network** (e.g., `http://192.168.1.10:8123`). Self-signed HTTPS certificates are not supported.

**Install via HACS:**
1. HACS > Menu > **Custom repositories** > Add this repo URL (category: **Integration**).
2. Install **HA-nnounce** and restart Home Assistant.
3. **Settings > Devices & services > Add integration > HA-nnounce**.

*(Manual install: copy `custom_components/hannounce` to `config/custom_components/` and restart.)*

## Configuration

| Option | Default | Description |
|---|---|---|
| Speakers | All supported | Filter available speakers or manually add custom integrations (TVs excluded by default). |
| Set volume / Message volume | On / 60% | Temporarily sets volume and restores it after playback (preserves manual changes made mid-playback). |
| Use speaker announcement volume | On | Uses native announcement volume on Sonos, Music Assistant, Squeezebox, and B&O. |
| Chime | Ding dong | Synthesized pre-message chime: `None`, `Ding dong`, `Soft`, `3 tones`. |
| Even out loudness | On | EBU R128 loudness normalization. |
| Longest message | 60s | Auto-stop recording limit. |
| Sidebar panel | On | Adds the Announcements panel to the sidebar. |
| Intercom cameras (Labs) | Off | Creates WebRTC intercom cameras (installs `aiortc` on first use). |

## Usage

### Card & Panel

Hold the mic button to talk and release to send (or tap to start/stop, `Esc` to cancel). Per-device preferences (selected speakers, chime, keep each speaker's volume, listen before sending) are stored locally. The options dialog can also send an audio file.

```yaml
type: custom:hannounce-card
title: Kitchen               # Optional (shows speaker state if matching single entity)
icon: mdi:bullhorn-outline   # Optional
color: deep-orange           # Optional (default: primary)
entities:                    # Optional
  - media_player.kitchen
show_volume: true
show_settings: true
review: false                # Listen before sending
```

### Intercom (Labs Two-Way Audio)

1. Enable **Intercom cameras** in HA-nnounce options (creates one camera per speaker + *Intercom All speakers*).
2. Enable **Two-way audio** under **Settings > System > Labs > Camera**.
3. Open an intercom camera and use **Start talking / Stop talking** (handled directly via `aiortc`, no `go2rtc` needed).

### Microphone Access & HTTPS

Browser recording requires a secure context:

| Environment | Support |
|---|---|
| Browser over HTTPS (or `localhost`) | Full support (card, panel, intercom). |
| Browser over HTTP | No direct recording (audio file upload still works). |
| iOS app 2026.10.3+ over HTTP | Supported with intercom enabled (untested on physical iPhone). |
| Android app over HTTP | Not yet supported; HTTPS required. |

## Automations & Events

### `hannounce.announce`

Send a local file (must be in `allowlist_external_dirs`) or URL:

```yaml
action: hannounce.announce
data:
  entity_id:
    - media_player.kitchen
  file: /media/messages/dinner.mp3
  volume: 50
  chime: soft
```

### `hannounce.replay`

Replay the last announcement (omit `entity_id` to reuse the original targets):

```yaml
action: hannounce.replay
data:
  entity_id: media_player.bedroom
```

### Event: `hannounce_announced`

Fired on every announcement with payload: `id`, `targets`, `duration` (seconds, incl. chime), `source` (`upload` | `intercom` | `service`), and `user_id` (empty for intercom).

## Technical Notes & Limitations

- **Synchronization:** Selecting multiple individual speakers starts playback roughly simultaneously but is not synced. Use native speaker groups (Google Home, Sonos, or HA `media_player` groups) for synchronized audio.
- **Retention & Privacy:** Audio is processed by Home Assistant and served to speakers on your local network. Files and signed URLs expire and are auto-deleted after **1 hour**, and are excluded from HA backups.

## Development & License

See [tools/README.md](tools/README.md).

- **Backend tests:** `pip install -r requirements_test.txt && pytest` (33 tests, ~90% coverage via `pytest-homeassistant`).
- **Frontend tests:** `node --test tools/tests`.

Released under the [MIT License](LICENSE).