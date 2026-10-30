import assert from "node:assert/strict";
import test from "node:test";

import { chartExportAppearance, chartExportMetadata } from "../src/chart-export.js";
import { dataAppThemes, dataAppThemePalette, dataAppThemeTokens } from "../src/theme-presets.js";

test("the Classic theme retains the reviewed light and dark chart colors", () => {
  const themes = dataAppThemes.filter(theme => theme.id === "classic");
  assert.equal(themes.length, 1, "Classic must have a stable, unique theme identifier.");
  const classic = themes[0];
  const chartColors = scheme => Array.from({ length: 8 }, (_, index) =>
    dataAppThemePalette(classic, scheme)[dataAppThemeTokens.indexOf(`chart-${index + 1}`)]);
  assert.deepEqual(chartColors("light"), [
    "#0285ff", "#924ff7", "#04b84c", "#fb6a22", "#ff66ad", "#ffc300", "#fa423e", "#8f8f8f",
  ]);
  assert.deepEqual(chartColors("dark"), [
    "#66b5ff", "#ad7bf9", "#40c977", "#ff8549", "#ff8cc1", "#ffd240", "#ff6764", "#afafaf",
  ]);
});

test("missing and retired export themes safely use the complete Classic palette", () => {
  for (const scheme of ["light", "dark"]) {
    const expected = chartExportAppearance("classic", scheme);
    for (const theme of [undefined, "retired-palette-id", "original"]) {
      assert.deepEqual(chartExportAppearance(theme, scheme), expected);
    }
    for (const token of dataAppThemeTokens) {
      assert.equal(typeof expected[`--${token}`], "string", `Missing ${scheme} export token: ${token}`);
      assert.notEqual(expected[`--${token}`], "");
    }
    assert.equal(expected.colorScheme, scheme);
  }
});

test("dark-only themes cannot create unreadable light exports", () => {
  const darkOnly = dataAppThemes.find(theme => theme.darkOnly);
  assert.ok(darkOnly, "At least one dark-only theme must exercise the light-export fallback.");
  assert.deepEqual(chartExportAppearance(darkOnly.id, "light"), chartExportAppearance("classic", "light"));
  const darkExport = chartExportAppearance(darkOnly.id, "dark");
  assert.equal(darkExport["--background"], dataAppThemePalette(darkOnly, "dark")[0]);
  assert.equal(darkExport.colorScheme, "dark");
  assert.deepEqual(chartExportAppearance("classic", "system", "dark"), {});
  assert.deepEqual(chartExportAppearance("classic", "system", "light"), { "--surface": "#fff" });
});

test("export captions retain the reviewed source and selected population filters", () => {
  const metadata = chartExportMetadata({ source: {
    label: "Public book survey", files: ["data/curated/format_profiles.csv"],
    executedAt: "2026-10-01T00:00:00Z",
  } }, [
    { label: "Country", value: "Canada" }, { label: "Format", value: "Audiobook" },
    { label: "Unused selection", value: "all" },
  ]);
  assert.match(metadata.source, /Public book survey/u);
  assert.match(metadata.source, /format_profiles\.csv/u);
  assert.match(metadata.source, /Captured/u);
  assert.equal(metadata.filters, "Country: Canada · Format: Audiobook");
});
