# Development tools

None of this is part of the installed integration: HACS only copies `custom_components/hannounce`.

## Tests

- `tests/` (repository root): backend tests with the official `pytest-homeassistant` package.
  `pip install -r requirements_test.txt`, then `pytest`. Keep `pytest-homeassistant` on the same
  release as the Home Assistant you test against. ffmpeg must be installed for the audio tests.
- `tools/tests/card.test.mjs`: the pure helpers of the card (languages, numbers, durations, colors,
  YAML). `node --test tools/tests`.
