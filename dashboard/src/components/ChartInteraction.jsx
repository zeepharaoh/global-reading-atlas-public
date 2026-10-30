import React, { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { SelectedChartRegion } from "../charting/SelectedChartRegion.jsx";
import {
  chartRegionSource,
  chartSectionSource,
  hasSelectedChartData,
  pinnedChartCardPosition,
  resolveChartAnchor,
  selectedChartData,
} from "../chart-interaction.js";
import { Icon } from "./Icon.jsx";
import "./chart-interaction.css";

const ChartInteractionContext = createContext({
  selectionEnabled: false,
  selectChartSection: () => false,
  selectChartMark: () => false,
  canSelectChartMark: () => false,
  selectedMarkElement: null,
  pinnedChartElement: null,
  dismissChartMark: () => {},
});
const chartRootSelector = ".recharts-wrapper, [data-chart-interaction-root]";

export function useChartInteraction() {
  return useContext(ChartInteractionContext);
}

export function PinnedChartCard({ context, actions, onClose, panelRef }) {
  useLayoutEffect(() => {
    const panel = panelRef.current;
    (panel?.querySelector(".chart-selection-actions button") ?? panel)?.focus({ preventScroll: true });
  }, [context, panelRef]);
  const value = context?.value;
  const summary = [context?.label, context?.series, value === null ? "Not reported" : value]
    .filter(entry => entry !== undefined && entry !== "").join(" · ");
  return <div ref={panelRef} className="chart-selection-panel" role="dialog" tabIndex={-1}
    aria-label="Selected chart data">
    <div className="chart-selection-heading">
      <div><strong>{context?.componentTitle || "Selected data"}</strong>{summary && <p>{summary}</p>}</div>
      <button type="button" className="chart-selection-close" aria-label="Close selected chart data" onClick={onClose}>
        <Icon name="cross" size={16} />
      </button>
    </div>
    <div className="chart-selection-actions">
      {actions.map((action, index) => <button key={`${action.label}-${index}`} type="button"
        onClick={() => { onClose(); action.onSelect(); }}>
        <span>{action.label}</span><Icon name={action.icon === "copy" ? "copy" : "arrowUpRight"} size={14} />
      </button>)}
    </div>
  </div>;
}

export function ChartInteractionProvider({ enabled = true, explorationEnabled = true, onStatus, children }) {
  const [selection, setSelection] = useState(null);
  const panelRef = useRef(null);
  const anchorSourceRef = useRef(null);
  const pinnedChartRef = useRef(null);
  const dismissedChartRef = useRef(null);
  const touchGestureRef = useRef(null);
  const touchPreviewRef = useRef(null);
  const selectionEnabled = enabled && explorationEnabled;
  const enabledRef = useRef(selectionEnabled);
  const exploreRef = useRef(explorationEnabled);
  enabledRef.current = selectionEnabled;
  exploreRef.current = explorationEnabled;
  const canSelect = context => enabledRef.current && (hasSelectedChartData(context)
    || (exploreRef.current && context?.actions?.some(action => action && typeof action.onSelect === "function")));

  function clearSelectionIndicator() {
    pinnedChartRef.current?.removeAttribute("data-chart-tooltip-pinned");
    pinnedChartRef.current = null;
    anchorSourceRef.current?.markElement?.classList.remove("chart-selection-mark");
  }

  function closeSelection() {
    clearSelectionIndicator();
    anchorSourceRef.current = null;
    setSelection(null);
  }

  function openSelection(context, anchorSource) {
    if (!canSelect(context)) return false;
    const anchor = resolveChartAnchor(anchorSource);
    if (!anchor) return false;
    touchPreviewRef.current = null;
    clearSelectionIndicator();
    anchorSourceRef.current = anchorSource;
    pinnedChartRef.current = context.hoverCard?.rootElement ?? context.hoverCard?.element
      ?? (anchorSource.selectionType === "point" ? anchorSource.element : null);
    pinnedChartRef.current?.setAttribute("data-chart-tooltip-pinned", "true");
    anchorSource.markElement?.classList.add("chart-selection-mark");
    setSelection({ context, anchor });
    return true;
  }

  function chartTouchClick(event, root) {
    const gesture = touchGestureRef.current;
    const native = event?.nativeEvent ?? event;
    if (native?.type?.startsWith("key") || native?.pointerType === "pen") return false;
    return Boolean(gesture && performance.now() - gesture.time < 750
      && (!root || gesture.root === root || gesture.root.closest(".chart-frame") === root.closest(".chart-frame")));
  }

  function selectChartMark(context, event) {
    if (!canSelect(context)) return false;
    const target = event?.target;
    const wrapper = target?.closest?.(chartRootSelector);
    if (wrapper && (pinnedChartRef.current === wrapper || dismissedChartRef.current === wrapper)) return false;
    if (chartTouchClick(event, wrapper)) {
      event?.stopPropagation?.();
      const gesture = touchGestureRef.current;
      if (gesture.canceled || !gesture.released) return false;
      const component = target?.closest?.(".dashboard-component");
      const key = [component?.dataset.componentId, context.chartType, context.label, context.series, context.value]
        .map(value => String(value ?? "")).join("\u0000");
      const previous = touchPreviewRef.current;
      const sameMark = previous?.root === wrapper && previous.key === key;
      touchPreviewRef.current = sameMark ? null : { root: wrapper, key };
      if (!sameMark) return false;
    }
    const component = target?.closest?.(".dashboard-component");
    const region = chartRegionSource(target, event, context.chartType);
    if (!region) return false;
    event?.stopPropagation?.();
    if (event?.detail > 0) target?.closest?.(".recharts-surface")?.blur?.();
    return openSelection({ ...context,
      componentKind: component?.dataset.componentKind,
      componentTitle: component?.querySelector(".component-title-text")?.textContent?.trim(),
    }, { ...region, hoverCard: context.hoverCard });
  }

  function selectChartSection(context, event) {
    if (!canSelect(context)) return false;
    const target = event?.target;
    const wrapper = target?.closest?.(chartRootSelector) ?? target?.closest?.(".chart-frame");
    if (chartTouchClick(event, wrapper) || pinnedChartRef.current || dismissedChartRef.current === wrapper) return false;
    const region = chartSectionSource(target);
    if (!region) return false;
    const component = target?.closest?.(".dashboard-component");
    return openSelection({ ...context,
      componentKind: component?.dataset.componentKind,
      componentTitle: component?.querySelector(".component-title-text")?.textContent?.trim(),
    }, region);
  }

  function dismissChartMark(element) {
    if (element && anchorSourceRef.current?.markElement === element) closeSelection();
  }

  useEffect(() => {
    const down = event => {
      if (event.pointerType !== "touch") {
        // Some mobile engines emit compatibility mouse events after a touch.
        // They must not erase the preview before its click is delivered.
        if (touchGestureRef.current && performance.now() - touchGestureRef.current.time < 750) return;
        touchGestureRef.current = null;
        touchPreviewRef.current = null;
        return;
      }
      const root = event.target?.closest?.(chartRootSelector) ?? event.target?.closest?.(".chart-frame");
      if (!root) { touchGestureRef.current = null; touchPreviewRef.current = null; return; }
      touchGestureRef.current = { root, id: event.pointerId, x: event.clientX, y: event.clientY,
        canceled: false, released: false, mode: null, frame: null, time: performance.now() };
    };
    const move = event => {
      const gesture = touchGestureRef.current;
      if (event.pointerType !== "touch" || gesture?.id !== event.pointerId) return;
      if (Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > 12) {
        gesture.canceled = true;
        touchPreviewRef.current = null;
      }
      // Recharts' native touch path is excluded; the touchmove listener below
      // distinguishes a horizontal scrub from vertical page scrolling.
      event.stopPropagation();
    };
    const touchMove = event => {
      const gesture = touchGestureRef.current;
      const touch = event.touches[0];
      if (!event.target?.closest?.(".recharts-wrapper, .chart-frame, [data-chart-interaction-root]")) return;
      event.stopPropagation();
      if (!gesture || !touch) return;
      const dx = touch.clientX - gesture.x, dy = touch.clientY - gesture.y;
      if (!gesture.mode && Math.hypot(dx, dy) >= 8) {
        gesture.mode = Math.abs(dx) > Math.abs(dy) * 1.25 ? "scrub" : "scroll";
        gesture.canceled = true;
        touchPreviewRef.current = null;
      }
      if (gesture.mode !== "scrub") return;
      // A horizontal gesture is ours. Never send WebKit's unbounded native
      // touchmove stream into Recharts' tooltip/layout loop; the chart consumes
      // one latest position per animation frame instead.
      event.preventDefault();
      gesture.point = { x: touch.clientX, y: touch.clientY };
      if (gesture.frame == null) gesture.frame = requestAnimationFrame(() => {
        gesture.frame = null;
        if (touchGestureRef.current !== gesture) return;
        gesture.root.dispatchEvent(new CustomEvent("data-chart-scrub", { bubbles: true, detail: gesture.point }));
      });
    };
    const cancel = event => {
      if (touchGestureRef.current?.id === event.pointerId) {
        touchGestureRef.current.canceled = true;
        touchPreviewRef.current = null;
      }
    };
    const up = event => {
      if (touchGestureRef.current?.id === event.pointerId) {
        touchGestureRef.current.released = true;
        touchGestureRef.current.time = performance.now();
      }
    };
    const endTouch = () => {
      const gesture = touchGestureRef.current;
      if (gesture?.frame != null) cancelAnimationFrame(gesture.frame);
      if (gesture) gesture.frame = null;
    };
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("pointermove", move, true);
    document.addEventListener("touchmove", touchMove, { capture: true, passive: false });
    document.addEventListener("touchend", endTouch, true);
    document.addEventListener("touchcancel", endTouch, true);
    document.addEventListener("pointercancel", cancel, true);
    document.addEventListener("pointerup", up, true);
    return () => {
      endTouch();
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("touchmove", touchMove, true);
      document.removeEventListener("touchend", endTouch, true);
      document.removeEventListener("touchcancel", endTouch, true);
      document.removeEventListener("pointercancel", cancel, true);
      document.removeEventListener("pointerup", up, true);
    };
  }, []);

  useEffect(() => {
    if (!selectionEnabled) closeSelection();
  }, [selectionEnabled]);

  useEffect(() => () => clearSelectionIndicator(), []);

  useEffect(() => {
    const resetDismissedChart = () => { dismissedChartRef.current = null; };
    document.addEventListener("pointerdown", resetDismissedChart, true);
    return () => document.removeEventListener("pointerdown", resetDismissedChart, true);
  }, []);

  useEffect(() => {
    if (!selection) return undefined;
    const closeOutside = event => {
      if (panelRef.current?.contains(event.target)) return;
      if (!pinnedChartRef.current && anchorSourceRef.current?.markElement?.contains?.(event.target)) return;
      if (pinnedChartRef.current?.contains(event.target)) dismissedChartRef.current = pinnedChartRef.current;
      closeSelection();
    };
    const closeOnEscape = event => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      event.preventDefault();
      const mark = anchorSourceRef.current?.markElement;
      closeSelection();
      if (mark?.isConnected) mark.focus?.({ preventScroll: true });
    };
    const closeOnFocusOutside = event => {
      if (panelRef.current?.contains(event.target) || anchorSourceRef.current?.markElement?.contains?.(event.target)) return;
      closeSelection();
    };
    document.addEventListener("pointerdown", closeOutside, true);
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("focusin", closeOnFocusOutside);
    return () => {
      document.removeEventListener("pointerdown", closeOutside, true);
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("focusin", closeOnFocusOutside);
    };
  }, [selection?.context]);

  useEffect(() => {
    if (!selection) return undefined;
    let frame;
    const syncAnchor = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const anchor = resolveChartAnchor(anchorSourceRef.current);
        if (!anchor) { closeSelection(); return; }
        setSelection(current => current ? { ...current, anchor } : null);
      });
    };
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(syncAnchor) : null;
    if (anchorSourceRef.current?.element) observer?.observe(anchorSourceRef.current.element);
    window.addEventListener("resize", syncAnchor);
    document.addEventListener("scroll", syncAnchor, true);
    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener("resize", syncAnchor);
      document.removeEventListener("scroll", syncAnchor, true);
    };
  }, [Boolean(selection)]);

  const contextValue = useMemo(() => ({
    selectionEnabled,
    selectChartMark,
    selectChartSection,
    canSelectChartMark: canSelect,
    dismissChartMark,
    selectedMarkElement: selection ? anchorSourceRef.current?.markElement : null,
    pinnedChartElement: selection ? pinnedChartRef.current : null,
  }), [selectionEnabled, explorationEnabled, selection]);

  const context = selection?.context;
  const actions = explorationEnabled
    ? (context?.actions ?? []).filter(action => action && typeof action.onSelect === "function") : [];
  if (hasSelectedChartData(context) && !actions.some(action => /^(?:copy data|copy selected data)$/iu.test(action.label))) {
    actions.push({ label: "Copy selected data", icon: "copy", onSelect: async () => {
      try {
        if (!globalThis.navigator?.clipboard?.writeText) throw new Error("Clipboard access is unavailable in this browser.");
        await navigator.clipboard.writeText(selectedChartData(context));
        onStatus?.("Selected data copied.");
      } catch (error) {
        onStatus?.(error instanceof Error ? error.message : "Unable to copy selected data.");
      }
    } });
  }
  const hoverCard = context?.hoverCard;
  const cardWidth = hoverCard?.width ?? 280;
  const position = selection && typeof window !== "undefined" ? pinnedChartCardPosition({
    ...selection.anchor,
    x: hoverCard ? selection.anchor.x : selection.anchor.x - cardWidth / 2,
  }, { width: cardWidth }, { width: window.innerWidth, height: window.innerHeight }) : null;
  const source = selection && anchorSourceRef.current;
  const region = source?.kind === "region" && source.element?.isConnected && source.renderOverlay !== false
    ? <SelectedChartRegion region={source} /> : null;
  const panel = position && <div className="chart-selection-anchor" style={{
    left: position.left, top: position.top, width: position.width,
    "--chart-selection-max-height": `${position.maxHeight}px`,
    "--chart-selection-radius": hoverCard?.radius,
    "--chart-selection-shadow": hoverCard?.shadow,
    "--chart-selection-background": hoverCard?.background,
  }}><PinnedChartCard context={context} actions={actions} onClose={closeSelection} panelRef={panelRef} /></div>;

  return <ChartInteractionContext.Provider value={contextValue}>
    {children}
    {typeof document !== "undefined" && region ? createPortal(region, source.element) : null}
    {typeof document !== "undefined" && panel ? createPortal(panel, document.body) : null}
  </ChartInteractionContext.Provider>;
}
