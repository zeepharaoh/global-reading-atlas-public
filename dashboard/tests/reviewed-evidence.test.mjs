import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = path => readFileSync(new URL(path, import.meta.url));
const json = path => JSON.parse(read(path).toString("utf8"));
const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const snapshot = json("../src/data.json");

test("the dashboard keeps the same reviewed query data as the analysis snapshot", () => {
  const analysis = json("../../data/processed/dashboard_snapshot.json");
  assert.deepEqual(snapshot.queries, analysis.queries);
  assert.equal(snapshot.publicViewer, true);
});

test("survey measures retain traceable source, population and period metadata", () => {
  const sources = new Set(json("../../data/source_register.json").map(source => source.source_id));
  for (const queryId of [
    "format_profiles", "format_history", "genre_profiles", "genre_history",
    "audiobook_evidence", "audiobook_history", "storytel_audio_2026",
  ]) {
    const rows = snapshot.queries[queryId]?.rows;
    assert.ok(rows?.length, `Missing reviewed query: ${queryId}`);
    for (const row of rows) {
      assert.ok(sources.has(row.source_id), `Unregistered source in ${queryId}: ${row.source_id}`);
      for (const field of ["source_url", "evidence_locator", "denominator", "population", "period", "comparison_group"]) {
        assert.equal(typeof row[field], "string", `${queryId} is missing ${field}`);
        assert.ok(row[field].trim(), `${queryId} has an empty ${field}`);
      }
      assert.ok(["http:", "https:"].includes(new URL(row.source_url).protocol));
      assert.ok(Number.isInteger(row.year), `Invalid observation year in ${queryId}`);
      assert.ok(row.participation === null || Number.isFinite(row.participation)
        && row.participation >= 0 && row.participation <= 100, `Invalid survey rate in ${queryId}`);
    }
  }
});

test("audiobook evidence preserves missing genres and incompatible survey periods", () => {
  assert.ok(snapshot.queries.audiobook_evidence.rows.every(row => row.format_label === "Audiobook"));
  const genres = snapshot.queries.genre_history.rows;
  for (const year of [2024, 2025]) {
    const missing = genres.filter(row => row.country_iso3 === "CAN" && row.year === year
      && row.format_label === "Audiobook" && row.genre === "Comics or Graphic Novels");
    assert.equal(missing.length, 2, `Retain both published genre scopes for Canada ${year}.`);
    assert.ok(missing.every(row => row.participation === null), "An unreported percentage must never become zero.");
  }
  const audio = snapshot.queries.us_formats.rows.filter(row => row.format_label === "Audiobook");
  assert.equal(audio.find(row => row.year === 2025).method_break, true);
  assert.ok(audio.filter(row => row.year <= 2021).every(row => row.method_break === false));
});

test("the committed dashboard and exact snapshot sidecar agree with their build receipt", () => {
  const receipt = json("../dist/data-app-build.json");
  assert.equal(receipt.kind, "inline-data-v1");
  assert.equal(receipt.html.path, "index.html");
  assert.equal(receipt.snapshot.path, `snapshot.${receipt.snapshot.sha256}.json`);
  for (const artifact of [receipt.html, receipt.snapshot]) {
    const bytes = read(`../dist/${artifact.path}`);
    assert.equal(bytes.length, artifact.bytes);
    assert.equal(digest(bytes), artifact.sha256);
  }
  const source = read("../src/data.json");
  assert.equal(digest(source), receipt.sourceSnapshotSha256);
  assert.equal(receipt.snapshot.sha256, receipt.sourceSnapshotSha256);
  assert.deepEqual(json(`../dist/${receipt.snapshot.path}`), snapshot);
  const html = read("../dist/index.html").toString("utf8");
  assert.match(html, new RegExp(`<meta\\s+name=["']data-app-snapshot-sha256["']\\s+content=["']${receipt.sourceSnapshotSha256}["']`, "u"));
  assert.doesNotMatch(html, /<meta\b[^>]*name=["']data-app-local-/iu);
});
