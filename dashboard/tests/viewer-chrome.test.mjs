import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const tabs = ["Industry", "Audiobooks", "Reading", "Formats", "Genres", "Coverage"]
  .map(label => ({ id: label.toLowerCase(), label }));
let server;
let cacheDirectory;
let chrome;

before(async () => {
  cacheDirectory = await mkdtemp(join(tmpdir(), "viewer-chrome-test-"));
  server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    configFile: false,
    cacheDir: cacheDirectory,
    optimizeDeps: { noDiscovery: true, entries: [] },
    server: { middlewareMode: true, watch: null, hmr: false, ws: false },
    appType: "custom",
  });
  chrome = await server.ssrLoadModule("/src/components/DataAppChrome.jsx");
});

after(async () => {
  await server?.close();
  if (cacheDirectory) await rm(cacheDirectory, { recursive: true, force: true });
});

test("public header retains its title, timestamp and six accessible tabs", () => {
  const generatedAt = "2026-10-20T12:34:56Z";
  const markup = renderToStaticMarkup(React.createElement(chrome.DataAppTopbar, {
    title: "Global Reading Atlas", generatedAt, publicViewer: true,
    tabs, activeTabId: "formats", onTabChange() {},
  }));
  assert.match(markup, /class="dashboard-topbar-title">Global Reading Atlas<\/strong>/u);
  assert.ok(markup.includes(`dateTime="${generatedAt}"`));
  assert.match(markup, /Updated /u);
  assert.match(markup, /role="tablist" aria-label="Dashboard pages"/u);
  assert.equal((markup.match(/role="tab"/gu) ?? []).length, 6);
  for (const { id, label } of tabs) {
    assert.ok(markup.includes(`data-dashboard-tab-id="${id}" aria-label="${label}" aria-selected="${id === "formats"}" tabindex="${id === "formats" ? 0 : -1}"`));
  }
  assert.doesNotMatch(markup, /aria-label="More"/u);
});

test("legacy editing props cannot expose remote or authoring controls", () => {
  const unexpected = () => { throw new Error("The viewer must not invoke an editing action while rendering."); };
  const markup = renderToStaticMarkup(React.createElement(chrome.DataAppTopbar, {
    title: "Reviewed evidence", generatedAt: "2026-10-20T12:34:56Z",
    tabs, activeTabId: "industry", mode: "edit", canEdit: true,
    buildStatus: "creating", published: false,
    onModeChange: unexpected, onSave: unexpected, onCancel: unexpected,
    onTitleChange: unexpected, getActionHref: unexpected,
    onAction() {}, onOpenThemes() {},
  }));
  assert.match(markup, /data-mode="view"/u);
  assert.match(markup, /<option value="copy-link">Copy link<\/option>/u);
  assert.match(markup, /<option value="theme">Switch theme<\/option>/u);
  assert.doesNotMatch(markup, /contenteditable|Edit text|Publish|Ask|Schedule|Refresh now|Create a copy|Save|Cancel/u);
  assert.deepEqual(Object.keys(chrome).sort(), ["DataAppThemeDrawer", "DataAppTopbar"]);
});
