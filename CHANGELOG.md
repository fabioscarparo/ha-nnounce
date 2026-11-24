# Changelog

## 0.4.0

- **Complete intercom screen translations:** Added German (`de`), French (`fr`), Spanish (`es`), and Dutch (`nl`) strings to the WebRTC intercom status screen so all 7 supported languages (`en`, `it`, `de`, `fr`, `es`, `nl`, `ro`) have full parity.
- **Best-effort playback resume (opt-in):** Added the `Resume playback after messages (best effort)` option (off by default) for speakers without native `MEDIA_ANNOUNCE` support (such as Google Cast and DLNA). Resumes directly playable `http(s)://` streams and `media-source://` tracks after restoring volume and mute, seeking back to the previous position on finite tracks when `SEEK` is supported.
- **Optional Amazon Alexa / Echo support (experimental):** Added the opt-in `Amazon Alexa / Echo support` option (off by default) supporting both Home Assistant's official `alexa_devices` integration (`notify.send_message` to sibling `_speak` or `_announce` entities, including `WHA` speaker groups) and HACS `alexa_media` (`notify.alexa_media` with `type: tts`). Transcodes on demand to Amazon SSML-compliant CBR 48 kbps / 24 kHz mono MP3 (capped at 240s) served via signed external HTTPS URL (`/api/hannounce/audio/<id>-alexa.mp3`), with config flow validation and diagnostics reporting.

## 0.3.3

- **Prevent duplicate playback on speaker groups:** Selecting `All` or an area shortcut now selects individual speakers instead of also selecting a speaker group alongside its own members (falling back to groups only when no individual speakers exist).
- **Per-card speaker selection:** Cards configured with a custom `entities` subset now keep their own saved selection (`cardTargets`) without overwriting the shared selection used by the sidebar panel and full-home cards, and reload cleanly when `entities` changes in the visual editor.
- **Cleaner single-speaker cards:** Cards targeting a single speaker now hide the redundant speaker chip row, keep the header clickable for more-info, and show `Unavailable` or `Silenced by quiet hours` directly in the hint when the speaker cannot play.
- **Card UI polish & dark mode fixes:** Added dynamic scroll fade edges (with RTL and resize support) on the horizontal area strip, fixed full-width speaker rows in the selection dialog (`.dialog-content.speakers-list`), fixed the toggle switch thumb contrast in dark mode, aligned Home Assistant CSS token fallbacks, added compact header buttons for narrow (`<= 280px`) columns, and regenerated the light/dark README wall SVGs.

## 0.3.2

- **Non-blocking setup & file validation:** Intercom screen fonts are now loaded once in the Home Assistant executor (`load_fonts()`) and shared across all intercom cameras instead of doing blocking file I/O on the event loop per speaker. Also moved `is_allowed_path` + `is_file` checks into a shared executor helper (`async_check_allowed_file`) across config flow, services, HTTP preview, and audio creation.

## 0.3.1

- **Translations:** Added Romanian (`ro`) across the integration config flow, services, sidebar panel, card, card editor, and intercom screen (thanks to @robex2005 in #1).
- **Intercom screen Unicode support:** Loads a system Unicode TrueType font (`DejaVuSans`, `LiberationSans`, `NotoSans`, `FreeSans`, `Arial`, etc.) when available so accented letters and diacritics render cleanly on the intercom camera stream, with an ASCII diacritic-stripping fallback if only Pillow's built-in font is present.

## 0.3.0

### New features

- **Quiet hours (Do Not Disturb):** Configure a quiet schedule (including overnight ranges like `22:00` to `07:00`) and/or an optional `input_boolean` or `binary_sensor` trigger in the integration options. Choose whether to **cap announcement volume** (default `25%`, also clamping speakers whose current volume exceeds the cap when "Keep each speaker's volume" is on) or **skip affected speakers** completely. Scope quiet hours to all speakers or specific ones (such as bedrooms).
- **Text mode (TTS):** Type an announcement directly from the card or panel using Home Assistant's already-configured text-to-speech engine (Piper, PicoTTS, Home Assistant Cloud, Google Translate, and more; optional `tts_entity` override in the integration options). Generated speech flows through HA-nnounce's full pipeline (chime, loudness normalization, volume/mute restore, quiet hours, replay, and Media history). On plain HTTP browsers without microphone access, Text mode opens automatically when a TTS engine is available.
- **Custom chime:** Set a local audio file path (MP3, WAV, OGG, FLAC... inside `allowlist_external_dirs`, validated on save) in the integration options to unlock a 5th `Custom` chime option in the card, panel, and `hannounce.announce` action, complete with audio preview via the authenticated `/api/hannounce/chime` endpoint.
- **Voice enhancement toggle:** New `Voice enhancement` option (enabled by default) in the integration settings. Turn it off to disable browser microphone DSP (`echoCancellation`, `noiseSuppression`, `autoGainControl`), the `70 Hz` high-pass filter, and automatic silence trimming for raw, unprocessed audio.

### Card & UI

- **Separated Area shortcuts & compact speaker dialog:** Area shortcuts (`All` + Home Assistant areas with live `selected/available` counts) now sit in their own horizontal strip above the speakers so areas and individual speakers are never mixed. Homes with 7+ speakers automatically switch to a compact `42px` selector row that opens a searchable, area-grouped dialog (bottom sheet on mobile); override anytime via `speaker_style: auto | chips | compact` in the visual editor.
- **Auto-growing text box:** In Text mode, the full-width text area grows vertically as you type (with `Enter` to send and `Shift+Enter` for a new line) above a full-width Send button.
- **Quiet hours visual indicators:** Displays an indigo moon pill (`Max 25%` or `Quiet: <speaker>`) in the volume header, a volume cap marker on the slider in cap mode, and dashed moon badges on silenced speakers in skip mode.
- **5-chime segmented control:** Dynamically displays the `Custom` option only when configured, with automatic compact sizing so all 5 labels fit cleanly without truncation.
- **Translations:** Updated all 6 languages (`en`, `it`, `de`, `fr`, `es`, `nl`) across both backend config/services and the frontend card/editor.

### Automations, Events & Diagnostics

- **`hannounce.announce`:** Added `message` (mutually exclusive with `file` and `url`), optional `tts_entity` and `language`, `chime: custom`, and `force: true` to bypass quiet hours for urgent announcements.
- **`hannounce.replay`:** Added `force: true` to bypass quiet hours.
- **WebSocket & Event:** Added `hannounce/say` command for TTS announcements; `hannounce_announced` now reports `source: "tts"` for text messages sent from the card or panel.
- **Diagnostics:** Redacts `custom_chime` file paths (`**REDACTED**`) and includes `custom_chime_configured`, `tts`, and `quiet` runtime status.

## 0.2.0

- Automatic unmute and mute restoration during announcements (when not using native speaker announcement volume), preserving manual mid-playback volume changes.
- Native Home Assistant targets (`entity_id`, `area_id`, `floor_id`, `device_id`, `label_id`) in `hannounce.announce` and `hannounce.replay`.
- Chime preview button in the card and panel options dialog (synthesized via Web Audio API).
- Diagnostics download (`Settings > Devices & services > HA-nnounce > Download diagnostics`) for troubleshooting without exposing URLs or user data.
- Added German (`de`), French (`fr`), Spanish (`es`), and Dutch (`nl`) translations for both backend and frontend.
- Added GitHub Actions CI workflow running `ruff`, `pytest`, and frontend unit tests.

## 0.1.1

- Added integration brand icons (`icon.png` and `icon@2x.png`) for Home Assistant.

## 0.1.0

First release.

- Record a voice message from the dashboard card or the Announcements panel and play it on one or more Home Assistant speakers, with an optional chime.
- Works with every Home Assistant media player that plays audio from a URL: Google Cast (Google Home, Nest), Sonos, ESPHome (such as the Home Assistant Voice PE), DLNA, Music Assistant, Squeezebox, HEOS, Kodi and more. Televisions are left out of the default list of speakers.
- Speakers get the message as a media source (`media-source://hannounce/...`), like text-to-speech: each integration converts it for its device. Players of custom integrations get a signed URL.
- On players that support it (Sonos, ESPHome, Music Assistant...) the message uses announcement mode: the music lowers and then resumes.
- Message volume: after the message every speaker goes back to its previous volume, unless someone changed it in the meantime. With the option "Use the announcement volume of the speaker", Sonos, Music Assistant, Squeezebox and Bang & Olufsen play the message at its own volume without touching the music.
- Dashboard card built on Home Assistant's design system, with a visual editor, a preview in the card picker, light and dark themes, English and Italian, and the number format of the user profile.
- Options for each device: chime, each speaker's own volume, listen before sending, send an audio file.
- Intercom: with the Labs two-way audio, the Start talking button of the HA-nnounce cameras plays your voice on the speakers.
- `hannounce.announce` and `hannounce.replay` actions and the `hannounce_announced` event.
- The messages of the last hour show in the Media panel, under HA-nnounce.
- Errors show as Home Assistant notifications in your language; every upload error is JSON with a code.
- Backend tests with the official `pytest-homeassistant` package, MIT license.
