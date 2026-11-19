# Changelog

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
