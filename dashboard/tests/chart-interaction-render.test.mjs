import assert from "node:assert/strict";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("chart interaction provider and selected-data card render independently of external services", async () => {
  const server = await createServer({ root, configFile: false, logLevel: "error",
    server: { middlewareMode: true, ws: false, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] }, appType: "custom" });
  try {
    const { ChartInteractionProvider, PinnedChartCard } = await server.ssrLoadModule("/src/components/ChartInteraction.jsx");
    const { ChartRenderer } = await server.ssrLoadModule("/src/charting/ChartRenderer.jsx");
    assert.equal(typeof ChartRenderer, "function");
    assert.equal(renderToStaticMarkup(createElement(ChartInteractionProvider, null,
      createElement("p", null, "Reviewed rows"))), "<p>Reviewed rows</p>");
    const html = renderToStaticMarkup(createElement(PinnedChartCard, {
      context: { componentTitle: "Observed participation", label: "Example", value: null },
      actions: [{ label: "Explore selected country", onSelect: () => {} }],
      onClose: () => {}, panelRef: { current: null },
    }));
    assert.match(html, /Selected chart data/);
    assert.match(html, /Not reported/);
    assert.match(html, /Explore selected country/);
    assert.doesNotMatch(html, /<form|<textarea|<a\b/);
  } finally {
    await server.close();
  }
});
