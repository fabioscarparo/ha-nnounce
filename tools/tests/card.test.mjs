// Unit tests for the pure helpers of the card: node --test tools/tests
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  CARD_DEFAULTS,
  STRINGS,
  cleanConfig,
  colorVar,
  escapeHtml,
  fileExtension,
  formatClock,
  formatPercent,
  formatTargets,
  languageOf,
  numberLocale,
  pickMimeType,
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
  assert.equal(languageOf({ language: "it", locale: { language: "en" } }), "en");
  assert.equal(languageOf(hass("pt-BR")), "en");
  assert.equal(languageOf(undefined), "en");
  assert.equal(t(hass("it"), "sent", { targets: "Cucina" }), "Inviato a Cucina");
  assert.equal(t(hass("de"), "send"), "Send");
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
