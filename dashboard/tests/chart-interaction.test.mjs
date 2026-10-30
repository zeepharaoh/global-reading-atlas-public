import assert from "node:assert/strict";
import test from "node:test";
import {
  chartMarkTooltipPosition,
  chartPointSelection,
  chartPointerTooltipPosition,
  chartRegionSource,
  chartSectionSource,
  hasSelectedChartData,
  pinnedChartCardPosition,
  resolveChartAnchor,
  selectedChartData,
} from "../src/chart-interaction.js";

const bounds = (left, top, width, height) => ({ left, top, width, height, right: left + width, bottom: top + height });

test("line selection follows rendered points and preserves CSS preview scaling", () => {
  const dot = { getBoundingClientRect: () => bounds(138, 168, 4, 4) };
  const other = { getBoundingClientRect: () => bounds(178, 158, 4, 4) };
  const cursor = { getBoundingClientRect: () => bounds(139.5, 110, 1, 80) };
  const wrapper = {
    getBoundingClientRect: () => bounds(100, 100, 200, 100), offsetWidth: 400, offsetHeight: 200,
    querySelectorAll: () => [dot, other],
    querySelector: selector => selector === ".recharts-tooltip-cursor" ? cursor : null,
  };
  const selection = chartPointSelection(wrapper, { closest: () => null }, () => ({ stroke: "#123", fill: "#456" }));
  assert.equal(selection.selectionType, "point");
  assert.equal(selection.left, 79.5);
  assert.equal(selection.top, 20);
  assert.equal(selection.height, 160);
  assert.equal(selection.points.length, 1);
  assert.equal(selection.points[0].x, 0.5);
  assert.equal(selection.points[0].y, 120);
  assert.equal(selection.points[0].radius, 4);
});

test("a line without a rendered point or cursor is not assigned a made-up selection", () => {
  const wrapper = { getBoundingClientRect: () => bounds(0, 0, 200, 100),
    querySelector: () => null, querySelectorAll: () => [] };
  assert.equal(chartPointSelection(wrapper, { closest: () => null }), null);
});

test("custom keyboard marks retain their own source region", () => {
  const mark = { getBoundingClientRect: () => bounds(20, 40, 100, 24), hasAttribute: () => true };
  const region = chartRegionSource({ closest: () => mark }, { type: "keydown" }, "rankedList");
  assert.equal(region.element, mark);
  assert.equal(region.markElement, mark);
  assert.equal(region.width, 100);
  assert.equal(region.height, 24);
  assert.equal(region.renderOverlay, false);
});

test("section and anchor geometry stays attached to the actual connected chart", () => {
  const element = { isConnected: true, getBoundingClientRect: () => bounds(10, 20, 120, 80) };
  const region = chartSectionSource({ closest: () => element });
  assert.deepEqual(resolveChartAnchor(region), { x: 70, y: 20, bottom: 100 });
  element.isConnected = false;
  assert.equal(resolveChartAnchor(region), null);
});

test("a pinned card stays within a narrow viewport and keeps space to scroll", () => {
  assert.deepEqual(pinnedChartCardPosition({ x: 500, y: 500 }, { width: 400 }, { width: 320, height: 480 }),
    { left: 12, top: 400, width: 296, maxHeight: 68 });
});

test("pointer tooltip flips at viewport edges and avoids a touch target", () => {
  const mark = bounds(50, 50, 30, 20), card = { width: 100, height: 60 }, viewport = { width: 320, height: 240 };
  assert.deepEqual(chartMarkTooltipPosition(mark, card, viewport, 12, 8, { x: 300, y: 220 }),
    { left: 192, top: 152 });
  assert.deepEqual(chartMarkTooltipPosition(mark, card, viewport, 12, 8, { x: 15, y: 20, type: "touch" }),
    { left: 12, top: 44 });
});

test("pointer tooltip coordinates convert back into a scaled chart", () => {
  const result = chartPointerTooltipPosition(bounds(100, 100, 200, 100), { width: 400, height: 200 },
    { width: 60, height: 30 }, { width: 1000, height: 800 }, { x: 150, y: 130 });
  assert.deepEqual(result, { x: 116, y: 76 });
});

test("copying selected published data preserves null, zero and row scope", () => {
  const row = Object.freeze({ country: "Example", year: 2025, value: 0, unavailable: null });
  const context = { row, value: 0, actions: [{ label: "Explore", onSelect: () => {} }] };
  assert.equal(hasSelectedChartData(context), true);
  assert.deepEqual(JSON.parse(selectedChartData(context)), row);
  assert.equal(selectedChartData(context).includes("actions"), false);
  assert.deepEqual(JSON.parse(selectedChartData({ label: "Unreported", value: null })),
    { label: "Unreported", value: null });
  assert.equal(hasSelectedChartData({ label: "Chart" }), false);
});
