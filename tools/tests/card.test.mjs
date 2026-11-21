// Unit tests for the pure helpers of the card: node --test tools/tests
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  CARD_DEFAULTS,
  CHIME_SPECS,
  STRINGS,
  cleanConfig,
  colorVar,
  escapeHtml,
  fileExtension,
  formatClock,
  formatPercent,
  formatSpeakerSummary,
  formatTargets,
  groupSpeakersByArea,
  isQuietActive,
  languageOf,
  numberLocale,
  pickMimeType,
  quickAreas,
  renderChimeSamples,
  t,
} from "../../custom_components/hannounce/frontend/hannounce.js";

const hass = (language, number_format = "language") => ({ language, locale: { language, number_format } });

test("every string exists in every language", () => {
  const keys = Object.keys(STRINGS.en).sort();
  for (const [lang, table] of Object.entries(STRINGS)) {
    assert.deepEqual(Object.keys(table).sort(), keys, `keys of ${lang}`);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(!/[\u2013\u2014]/.test(value), `${lang}.${key} has a long dash`);
      const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
      assert.deepEqual(placeholders(value), placeholders(STRINGS.en[key]), `placeholders of ${lang}.${key}`);
    }
  }
});

test("language follows the user, English otherwise", () => {
  assert.equal(languageOf(hass("it")), "it");
  assert.equal(languageOf(hass("de-DE")), "de");
  assert.equal(languageOf(hass("fr-FR")), "fr");
  assert.equal(languageOf(hass("es")), "es");
  assert.equal(languageOf(hass("nl")), "nl");
  assert.equal(languageOf({ language: "it", locale: { language: "en" } }), "en");
  assert.equal(languageOf(hass("pt-BR")), "en");
  assert.equal(languageOf(undefined), "en");
  assert.equal(t(hass("it"), "sent", { targets: "Cucina" }), "Inviato a Cucina");
  assert.equal(t(hass("de"), "send"), "Senden");
  assert.equal(t(hass("fr"), "send"), "Envoyer");
  assert.equal(t(hass("es"), "send"), "Enviar");
  assert.equal(t(hass("nl"), "send"), "Verzend");
  assert.equal(t(hass("pt"), "send"), "Send");
  assert.equal(t(hass("it"), "missing_key"), "missing_key");
});

test("numbers follow the number format, not the language", () => {
  assert.equal(numberLocale(hass("it", "comma_decimal")), "en-US");
  assert.equal(numberLocale(hass("en", "decimal_comma")), "de");
  assert.equal(numberLocale(hass("it", "system")), undefined);
  assert.equal(numberLocale(hass("it", "language")), "it");
  assert.equal(formatPercent(hass("it"), 70), "70%");
  assert.equal(formatPercent(hass("en"), 5), "5%");
  assert.match(formatPercent(hass("it", "space_comma"), 70), /^70\s%$/u);
});

test("clock is minutes and two digit seconds", () => {
  assert.equal(formatClock(hass("it"), 3.9), "0:03");
  assert.equal(formatClock(hass("en"), 65), "1:05");
  assert.equal(formatClock(hass("en"), -2), "0:00");
});

test("targets read as a list, then as a count", () => {
  assert.equal(formatTargets(hass("it"), ["Cucina"]), "Cucina");
  assert.equal(formatTargets(hass("it"), ["Cucina", "Salotto"]), "Cucina e Salotto");
  assert.equal(formatTargets(hass("en"), ["Kitchen", "Office", "Hall"]), "Kitchen, Office, and Hall");
  assert.equal(formatTargets(hass("it"), ["A", "B", "C", "D"]), "4 altoparlanti");
  assert.equal(formatTargets(hass("it"), []), "");
});

test("colors come from the theme palette", () => {
  assert.equal(colorVar(undefined), "var(--primary-color)");
  assert.equal(colorVar("deep-orange"), "var(--deep-orange-color)");
  assert.equal(colorVar("#4285f4"), "#4285f4");
  assert.equal(colorVar("rgb(1, 2, 3)"), "rgb(1, 2, 3)");
  assert.equal(colorVar("red;} :host{display:none"), "var(--primary-color)");
});

test("config keeps only what differs from the defaults", () => {
  assert.deepEqual(cleanConfig({ type: "custom:x", ...CARD_DEFAULTS, title: "", entities: [] }), { type: "custom:x" });
  assert.deepEqual(cleanConfig({ type: "custom:x", review: true, color: "red" }), { type: "custom:x", review: true, color: "red" });
});

test("helpers for recording and markup", () => {
  assert.equal(escapeHtml(`<b a="1">'&`), "&lt;b a=&quot;1&quot;&gt;&#39;&amp;");
  assert.equal(pickMimeType({ isTypeSupported: (type) => type === "audio/mp4" }), "audio/mp4");
  assert.equal(pickMimeType(undefined), "");
  assert.equal(fileExtension("audio/webm;codecs=opus"), "webm");
  assert.equal(fileExtension("audio/mp4"), "m4a");
  assert.equal(fileExtension("audio/x-unknown"), "audio");
});

test("chime preview synthesizes non-silent bounded samples", () => {
  assert.equal(renderChimeSamples("none", 8000), null);
  assert.equal(renderChimeSamples("unknown", 8000), null);
  for (const [name, spec] of Object.entries(CHIME_SPECS)) {
    const samples = renderChimeSamples(name, 8000);
    assert.ok(samples instanceof Float32Array, name);
    assert.equal(samples.length, Math.ceil(spec.duration * 8000), name);
    let peak = 0;
    for (const v of samples) {
      assert.ok(v >= -1 && v <= 1, `${name} sample out of bounds`);
      peak = Math.max(peak, Math.abs(v));
    }
    assert.ok(peak > 0.2, `${name} should be audible`);
  }
});

test("quiet hours evaluation handles schedules, overnight wrap, and entities", () => {
  const mkHass = (entityState = "off") => ({
    config: { time_zone: "UTC" },
    states: { "input_boolean.sleep": { state: entityState } },
  });
  const night = { enabled: true, start: "22:00", end: "07:00", entity_id: "input_boolean.sleep" };

  assert.equal(isQuietActive(mkHass("off"), { ...night, enabled: false }, new Date("2026-01-01T23:00:00Z")), false);
  assert.equal(isQuietActive(mkHass("off"), night, new Date("2026-01-01T22:00:00Z")), true);
  assert.equal(isQuietActive(mkHass("off"), night, new Date("2026-01-01T06:59:00Z")), true);
  assert.equal(isQuietActive(mkHass("off"), night, new Date("2026-01-01T07:00:00Z")), false);
  assert.equal(isQuietActive(mkHass("off"), night, new Date("2026-01-01T14:00:00Z")), false);
  assert.equal(isQuietActive(mkHass("on"), night, new Date("2026-01-01T14:00:00Z")), true);

  const nap = { enabled: true, start: "13:00", end: "15:00" };
  assert.equal(isQuietActive(mkHass(), nap, new Date("2026-01-01T13:30:00Z")), true);
  assert.equal(isQuietActive(mkHass(), nap, new Date("2026-01-01T15:00:00Z")), false);
});

test("area grouping and quick area chips skip single-speaker and all-speaker areas", () => {
  const speakers = [
    { entity_id: "media_player.a", name: "Kitchen", area: "Living", area_id: "living", area_icon: "mdi:sofa" },
    { entity_id: "media_player.b", name: "Lounge", area: "Living", area_id: "living", area_icon: "mdi:sofa" },
    { entity_id: "media_player.c", name: "Bedroom", area: "Bedroom", area_id: "bed", area_icon: null },
    { entity_id: "media_player.d", name: "All House", area: null, area_id: null, area_icon: null },
  ];
  const { areas, ungrouped } = groupSpeakersByArea(speakers);
  assert.equal(areas.length, 2);
  assert.equal(areas[0].name, "Living");
  assert.equal(areas[0].icon, "mdi:sofa");
  assert.equal(areas[1].icon, "mdi:floor-plan");
  assert.equal(ungrouped.length, 1);

  const quick = quickAreas(speakers);
  assert.deepEqual(
    quick.map((a) => a.key),
    ["living"]
  );

  // If every speaker is in the same area, don't duplicate the All chip
  assert.deepEqual(quickAreas(speakers.slice(0, 2)), []);

  assert.equal(formatSpeakerSummary(hass("it"), []), "Scegli altoparlanti");
  assert.equal(formatSpeakerSummary(hass("en"), ["Kitchen", "Living"]), "Kitchen, Living");
  assert.equal(formatSpeakerSummary(hass("it"), ["Cucina", "Soggiorno", "Studio", "Camera"]), "Cucina, Soggiorno (+2)");
});
