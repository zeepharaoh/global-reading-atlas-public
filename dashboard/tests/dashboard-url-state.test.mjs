import assert from "node:assert/strict";
import test from "node:test";
import * as runtimeEnvironment from "../src/runtime-environment.js";

import {
  dashboardUrlWithState,
  dashboardViewSearchParams,
  readDashboardUrlState,
  resolveDashboardUrlFilters,
  serializeDashboardUrlState,
} from "../src/dashboard-url-state.js";
import {
  currentDataAppReference,
  currentDataAppViewUrl,
  isSafeLocalDataAppPath,
  safeDataAppSourceHref,
} from "../src/runtime-environment.js";

const snapshot = {
  filters: [
    { id: "country", field: "country", multiple: true, queryIds: ["audience"], defaultValue: "all" },
    { id: "year", field: "year", queryIds: ["audience"], defaultValue: "2024" },
    { id: "format", field: "format", queryIds: ["audience"], defaultValue: "all", shareInUrl: false },
  ],
  queries: { audience: { rows: [
    { country: "Canada", year: 2024, format: "Audiobook" },
    { country: "Norway", year: 2025, format: "Print" },
    { country: "Singapore", year: 2025, format: "Audiobook" },
  ] } },
};
const tabs = [{ id: "audiobooks" }, { id: "formats" }];
const base = "https://example.org/atlas/dashboard/";

test("the runtime environment exposes only local reference and safe URL helpers", () => {
  assert.deepEqual(Object.keys(runtimeEnvironment).sort(), [
    "currentDataAppReference", "currentDataAppViewUrl", "isSafeLocalDataAppPath", "safeDataAppSourceHref",
  ]);
});

test("shared views round-trip filters, chart selections and tab-specific state", () => {
  const selections = {
    tab: "audiobooks",
    filters: { country: ["Norway", "Canada", "Canada"], year: "2025", format: "Audiobook" },
    assumptions: { price: 1.2, unchanged: 0 },
    sections: { audio: { comparison_group: "Annual adult population", country: "Canada" } },
    charts: { listening: {
      inlineFilters: { country: ["Norway", "Canada"] },
      visibleSeries: ["Print", "Audiobook", "Audiobook"],
      zoomRange: { start: 2022, end: 2025 },
    } },
    tabViews: { formats: { filters: { country: "Norway" }, focus: { metric: "reach" } } },
    focus: { country: "Canada" },
  };
  const parameters = serializeDashboardUrlState(snapshot, tabs, selections);
  const restored = readDashboardUrlState(snapshot, tabs, `${base}?${parameters}`);
  assert.equal(restored.complete, true);
  assert.equal(restored.tab, "audiobooks");
  assert.deepEqual(restored.filters, {
    country: ["Canada", "Norway"], format: "Audiobook", year: "2025",
  });
  assert.deepEqual(restored.assumptions, { price: 1.2 });
  assert.deepEqual(restored.sections, selections.sections);
  assert.deepEqual(restored.charts.listening, {
    inlineFilters: { country: ["Norway", "Canada"] },
    visibleSeries: ["Audiobook", "Print"], zoomRange: { start: 2022, end: 2025 },
  });
  assert.deepEqual(restored.tabViews, selections.tabViews);
  assert.deepEqual(restored.focus, selections.focus);
  assert.equal(serializeDashboardUrlState(snapshot, tabs, restored).toString(), parameters.toString());
});

test("an explicitly shared default view replaces the recipient's remembered filters", () => {
  const parameters = serializeDashboardUrlState(snapshot, tabs, { tab: "audiobooks" });
  const restored = readDashboardUrlState(snapshot, tabs, `${base}?${parameters}`);
  const remembered = { country: ["Norway"], year: "2025", format: "Print" };
  assert.deepEqual(resolveDashboardUrlFilters(snapshot, remembered, restored), {
    country: "all", year: "2024", format: "all",
  });
});

test("unknown choices, duplicate parameters and unsafe object keys are ignored", () => {
  const parameters = new URLSearchParams({ view: "1", tab: "missing" });
  parameters.append("f.country", '["Canada","Unreviewed country"]');
  parameters.append("f.year", "2024");
  parameters.append("f.year", "2025");
  parameters.set("s", '{"__proto__":{"polluted":"yes"}}');
  parameters.set("c", '{"listening":{"rows":[{"participation":99}]}}');
  const restored = readDashboardUrlState(snapshot, tabs, `${base}?${parameters}`);
  assert.equal(restored.tab, null);
  assert.deepEqual(restored.filters, {});
  assert.deepEqual(restored.sections, {});
  assert.deepEqual(restored.charts, {});
  assert.equal(Object.hasOwn(Object.prototype, "polluted"), false);
});

test("shared links remove credentials and unrelated navigation when requested", () => {
  const result = dashboardUrlWithState(
    "https://reader:sample@example.org/atlas/dashboard/?token=sample#private",
    snapshot, tabs, { tab: "formats", filters: { year: "2025" } }, { preserveExisting: false },
  );
  assert.equal(result.origin, "https://example.org");
  assert.equal(result.pathname, "/atlas/dashboard/");
  assert.equal(result.username, "");
  assert.equal(result.password, "");
  assert.equal(result.hash, "");
  assert.equal(result.searchParams.has("token"), false);
  assert.equal(result.searchParams.get("tab"), "formats");
  assert.equal(result.searchParams.get("f.year"), "2025");
});

test("view state never carries unrelated query parameters or reviewed rows", () => {
  const parameters = new URLSearchParams({
    view: "1", tab: "audiobooks", token: "sample", return_to: "/settings", rows: "sample",
    "f.country": "Canada", c: '{"listening":{"visibleSeries":["Audiobook"]}}',
  });
  const safe = dashboardViewSearchParams(`${base}?${parameters}`);
  assert.deepEqual([...safe.keys()].sort(), ["c", "f.country", "tab", "view"]);
  assert.throws(() => serializeDashboardUrlState(snapshot, tabs, {
    focus: { detail: "x".repeat(65_537) },
  }), error => error instanceof RangeError && error.code === "DATA_APP_VIEW_TOO_LARGE");
});

test("source links allow bounded dashboard selections and reject unsafe destinations", () => {
  const approved = `${base}?view=1&tab=audiobooks&f.country=Canada`;
  assert.equal(safeDataAppSourceHref(approved), approved);
  for (const candidate of [
    "javascript:alert(1)", "data:text/html,sample", "file:///tmp/atlas/index.html", "/relative/report",
    "https://reader:sample@example.org/report", `${base}?token=sample`, `${base}#private`,
    `${base}?view=1&tab=audiobooks&tab=formats`,
    "https://example.org/access_token/sample", "https://example.org/%2574oken/sample",
  ]) {
    assert.equal(safeDataAppSourceHref(candidate), null, candidate);
  }
});

test("current browser URLs keep the deployment subpath and strip private navigation", () => {
  const href = "https://reader:sample@example.org/atlas/dashboard/?token=sample&view=1&tab=audiobooks#private";
  const cleaned = currentDataAppViewUrl({ href });
  assert.equal(cleaned, `${base}?view=1&tab=audiobooks`);
  assert.equal(currentDataAppViewUrl({ href: "file:///tmp/atlas/index.html" }), null);
  assert.deepEqual(currentDataAppReference({ href }, ""), { sourceUrl: cleaned });
});

test("local references accept absolute local paths and exclude network paths", () => {
  for (const path of ["/tmp/atlas/index.html", "C:\\Reports\\index.html"]) {
    assert.equal(isSafeLocalDataAppPath(path), true, path);
  }
  for (const path of ["relative/report.html", "C:report.html", "//server/share", "\\\\server\\share", "/tmp/a\n.html", ""]) {
    assert.equal(isSafeLocalDataAppPath(path), false, path);
  }
  assert.deepEqual(currentDataAppReference({ href: "file://server/share/index.html" }, ""), {});
  assert.deepEqual(currentDataAppReference({ href: "file:///tmp/atlas%2Fdist/index.html" }, ""), {});
  assert.deepEqual(currentDataAppReference({ href: "file:///tmp/atlas/dist/index.html" }, ""), {
    htmlPath: "/tmp/atlas/dist/index.html", root: "/tmp/atlas", sourceUrl: "file:///tmp/atlas/dist/index.html",
  });
});
