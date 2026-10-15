import * as Dropdown from "@radix-ui/react-dropdown-menu";
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { dataAppChromeColors } from "../chrome-contrast.js";
import { dataAppChromeLayout } from "../chrome-layout.js";
import { reportDateMetadata } from "../report-date.js";
import { dataAppThemePalette, dataAppThemes, dataAppThemeToken } from "../theme-presets.js";
import { DashboardTabs } from "./DashboardTabs.jsx";
import { Icon } from "./Icon.jsx";
import { Menu, MenuItem, Select, Tooltip } from "./ui.jsx";

function formatReviewedAt(value, part = "date") {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  const options =
    part === "time"
      ? { hour: "numeric", minute: "2-digit" }
      : { month: "short", day: "numeric", ...(part === "compact" ? {} : { year: "numeric" }) };
  return new Intl.DateTimeFormat(undefined, options).format(date);
}

function ReviewedFreshness({ generatedAt }) {
  return (
    <time dateTime={generatedAt}>
      <span className="dashboard-freshness-full">
        Updated {formatReviewedAt(generatedAt)}
        <span className="dashboard-freshness-time">, {formatReviewedAt(generatedAt, "time")}</span>
      </span>
      <span className="dashboard-freshness-compact">{formatReviewedAt(generatedAt, "compact")}</span>
    </time>
  );
}

function ReportDateLabel({ asOf, generatedAt }) {
  const metadata = reportDateMetadata({ asOf, generatedAt });
  if (!metadata) return null;
  const formatted = new Intl.DateTimeFormat(undefined, {
    month: "short", day: "numeric", year: "numeric", timeZone: metadata.timeZone,
  }).format(metadata.date);
  return <span className="freshness freshness-label">
    {metadata.label} <time dateTime={metadata.value}>{formatted}</time>
  </span>;
}

const HeaderOverflowButton = React.forwardRef(function HeaderOverflowButton(props, ref) {
  const tooltipId = React.useId();
  return (
    <span className="history-tooltip-trigger" data-delayed-tooltip>
    <button
      {...props}
      ref={ref}
      type="button"
      aria-label="More"
      aria-describedby={tooltipId}
      className="dashboard-header-action-button dashboard-header-overflow-button"
    >
      <span className="dashboard-header-overflow-visual"><Icon name="more" size={18} /></span>
    </button>
    <Tooltip id={tooltipId} className="topbar-mode-tooltip">More</Tooltip>
    </span>
  );
});

function ViewerMenu({ onAction, onOpenThemes }) {
  const nativeSelect = useRef(null);
  useLayoutEffect(() => { if (nativeSelect.current) nativeSelect.current.selectedIndex = -1; });
  if (!onAction && !onOpenThemes) return null;
  return <>
    <span className="dashboard-custom-overflow">
      <Menu label="More" align="start" contentClassName="dashboard-header-action-menu" trigger={<HeaderOverflowButton />}>
        {onAction && <MenuItem icon="link" className="dashboard-action-menu-item" onSelect={() => onAction("copy-link")}>Copy link</MenuItem>}
        {onOpenThemes && <MenuItem icon="palette" className="dashboard-action-menu-item" onSelect={onOpenThemes}>Switch theme</MenuItem>}
      </Menu>
    </span>
    <span className="dashboard-native-overflow">
      <span className="dashboard-header-overflow-visual" aria-hidden="true"><Icon name="more" size={18} /></span>
      <select ref={nativeSelect} aria-label="More" onChange={event => {
        const action = event.currentTarget.value;
        event.currentTarget.selectedIndex = -1;
        if (action === "copy-link") onAction?.("copy-link");
        else if (action === "theme") requestAnimationFrame(() => onOpenThemes?.());
      }} onKeyDown={event => { if (event.key === "Escape") event.stopPropagation(); }}>
        {onAction && <option value="copy-link">Copy link</option>}
        {onOpenThemes && <option value="theme">Switch theme</option>}
      </select>
    </span>
  </>;
}

export function DataAppTopbar({
  title, generatedAt, reportAsOf, onAction, onOpenThemes,
  surface = "dashboard", publicViewer = false, className = "",
  tabs = [], activeTabId, onTabChange,
}) {
  const showTabs = surface !== "report" && tabs.length > 1;
  const [chromeColors, setChromeColors] = useState({});
  const [chromeLayout, setChromeLayout] = useState({});
  const topbar = useRef(null);
  useEffect(() => {
    const header = topbar.current;
    if (!header) return undefined;
    header.setAttribute("data-tabs-motion-ready", "");
    return () => header.removeAttribute("data-tabs-motion-ready");
  }, []);
  useLayoutEffect(() => {
    if (!topbar.current || typeof getComputedStyle !== "function") return undefined;
    function updateChromeColors() {
      const header = topbar.current;
      if (!header) return;
      const rootStyles = getComputedStyle(document.documentElement);
      const headerStyles = getComputedStyle(header);
      const next = dataAppChromeColors({
        background: headerStyles.backgroundColor,
        underlay: getComputedStyle(document.body).backgroundColor,
        foreground: headerStyles.color,
        secondary: rootStyles.getPropertyValue("--secondary").trim(),
        positive: rootStyles.getPropertyValue("--positive").trim(),
      });
      setChromeColors(current => Object.keys(next).every(key => current[key] === next[key]) ? current : next);
    }
    updateChromeColors();
    const observer = new MutationObserver(updateChromeColors);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["style", "data-app-theme", "data-color-scheme", "data-app-appearance"],
    });
    return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    const main = document.querySelector(`main[data-data-app-content="${surface}"]`);
    if (!main || typeof getComputedStyle !== "function" || typeof ResizeObserver !== "function") return undefined;
    let frame = 0;
    const sizes = new ResizeObserver(scheduleLayout);
    function scheduleLayout() {
      if (!frame) frame = requestAnimationFrame(updateChromeLayout);
    }
    function updateChromeLayout() {
      frame = 0;
      const styles = getComputedStyle(main);
      const next = dataAppChromeLayout({
        viewportWidth: window.innerWidth,
        paddingLeft: Number.parseFloat(styles.paddingLeft),
        paddingRight: Number.parseFloat(styles.paddingRight),
      });
      setChromeLayout(current => Object.keys(next).every(key => current[key] === next[key]) ? current : next);
    }
    sizes.observe(main);
    window.addEventListener("resize", scheduleLayout);
    updateChromeLayout();
    return () => {
      cancelAnimationFrame(frame);
      sizes.disconnect();
      window.removeEventListener("resize", scheduleLayout);
    };
  }, [surface]);
  return <>
    <header ref={topbar} style={{ ...chromeColors, ...chromeLayout }}
      className={["dashboard-topbar", className].filter(Boolean).join(" ")}
      data-data-app-chrome="topbar" data-mode="view">
      <div className="dashboard-chrome-inner dashboard-topbar-inner">
        <div className="dashboard-topbar-copy">
          <strong className="dashboard-topbar-title">{title}</strong>
          {surface === "report" ? <ReportDateLabel asOf={reportAsOf} generatedAt={generatedAt} />
            : generatedAt && <span className="freshness freshness-label"><ReviewedFreshness generatedAt={generatedAt} /></span>}
        </div>
        {!publicViewer && (onAction || onOpenThemes) && <div className="dashboard-topbar-mode-controls">
          <div className="dashboard-topbar-actions"><ViewerMenu onAction={onAction} onOpenThemes={onOpenThemes} /></div>
        </div>}
      </div>
      <div className={`dashboard-tabs-collapse${showTabs ? " is-open" : ""}`} aria-hidden={!showTabs} inert={!showTabs}>
        <div className="dashboard-tabs-collapse-inner">
          <DashboardTabs tabs={tabs} activeTabId={activeTabId} onChange={onTabChange} />
        </div>
      </div>
    </header>
    {surface === "report" && (reportAsOf || generatedAt) &&
      <div className="dashboard-mobile-report-date"><ReportDateLabel asOf={reportAsOf} generatedAt={generatedAt} /></div>}
  </>;
}

function normalizedTokens(values) {
  if (typeof document === "undefined" || typeof getComputedStyle !== "function" || !document.body) {
    return values.map((value) => String(value));
  }
  const probe = document.createElement("i");
  probe.style.cssText = "position:absolute;visibility:hidden;pointer-events:none";
  document.body.append(probe);
  try {
    return values.map((value, index) => {
      if (index <= 20) {
        probe.style.color = value;
        return getComputedStyle(probe).color;
      }
      if (index <= 23) return String(Number.parseFloat(value));
      if (index <= 25) {
        probe.style.boxShadow = value;
        return getComputedStyle(probe).boxShadow;
      }
      probe.style.fontFamily = value;
      return getComputedStyle(probe).fontFamily;
    });
  } finally {
    probe.remove();
  }
}

function matchingPreset(originalTokens) {
  const original = normalizedTokens(originalTokens);
  const scheme = globalThis.document?.documentElement?.dataset.colorScheme ?? "light";
  return dataAppThemes.find((theme) => {
    const tokens = dataAppThemePalette(theme, scheme);
    return tokens && normalizedTokens(tokens).every((value, index) => value === original[index]);
  });
}

function fontLabel(font) {
  if (/mono|courier|menlo/iu.test(font)) return "Monospace";
  if (/rounded/iu.test(font)) return "Rounded sans";
  if (/georgia|times/iu.test(font)) return "Serif";
  return "Sans serif";
}

function subscribeColorScheme(onChange) {
  const root = globalThis.document?.documentElement;
  if (!root || typeof MutationObserver === "undefined") return () => {};
  const observer = new MutationObserver(onChange);
  observer.observe(root, {
    attributes: true,
    attributeFilter: ["data-color-scheme"],
  });
  return () => observer.disconnect();
}

function currentColorScheme() {
  return globalThis.document?.documentElement?.dataset.colorScheme ?? "light";
}

function ThemePreview({ theme, originalTokens, colorScheme }) {
  const tokens = dataAppThemePalette(theme, colorScheme) ?? originalTokens;
  const background = dataAppThemeToken(tokens, "background", "var(--background)");
  const surface = dataAppThemeToken(tokens, "surface", "var(--surface)");
  const text = dataAppThemeToken(tokens, "text", "var(--text)");
  const accent = dataAppThemeToken(tokens, "accent", "var(--accent)");
  const secondary = dataAppThemeToken(tokens, "secondary", "var(--secondary)");
  const border = dataAppThemeToken(tokens, "border", "var(--border)");
  const control = dataAppThemeToken(tokens, "control", "var(--control)");
  const controlRadius = Number.parseFloat(dataAppThemeToken(tokens, "control-radius", "8px"));
  const radius = controlRadius >= 16 ? "999px" : controlRadius > 0 ? "5px" : "0px";
  const font = dataAppThemeToken(tokens, "font-sans", "ui-sans-serif, system-ui, sans-serif");
  const swatches = Array.from({ length: 5 }, (_, index) => dataAppThemeToken(tokens, `chart-${index + 1}`, accent));

  return (
    <span
      className="theme-preview"
      aria-hidden="true"
      style={{
        "--preview-background": background,
        "--preview-surface": surface,
        "--preview-text": text,
        "--preview-secondary": secondary,
        "--preview-accent": accent,
        "--preview-border": border,
        "--preview-control": control,
        "--preview-radius": radius,
        "--preview-font": font,
      }}
    >
      <span className="theme-preview-type">
        <strong>Aa</strong>
        <span>{fontLabel(font)}</span>
      </span>
      <span className="theme-preview-swatches">
        {swatches.map((swatch, index) => (
          <i key={`${swatch}:${index}`} style={{ background: swatch }} />
        ))}
      </span>
      <span className="theme-preview-geometry">
        <i />
      </span>
    </span>
  );
}

export function DataAppThemeDrawer({
  activeTheme,
  open,
  onApply,
  onClose,
  onPreview,
  onPreviewEnd,
  originalTokens,
  appearance = "system",
  onAppearanceChange,
}) {
  const list = useRef(null);
  const colorScheme = useSyncExternalStore(subscribeColorScheme, currentColorScheme, currentColorScheme);
  const equivalentPreset = useMemo(() => matchingPreset(originalTokens), [originalTokens]);
  const themes = equivalentPreset ? dataAppThemes.filter(({ id }) => id !== "original") : dataAppThemes;
  const selected = activeTheme === "original" && equivalentPreset ? equivalentPreset.id : activeTheme;

  useEffect(() => {
    if (open && list.current) list.current.scrollLeft = 0;
  }, [open]);

  return (
    <section
      className={`theme-drawer${open ? " is-open" : ""}`}
      aria-hidden={!open}
      inert={!open}
      aria-label="Theme picker"
    >
      <div className="dashboard-chrome-inner theme-drawer-content">
        <header className="theme-drawer-header">
          <h2>Theme</h2>
          <div className="theme-drawer-actions">
            {onAppearanceChange && (
              <>
              <span className="theme-appearance-native">
                <Select label="Appearance" value={appearance} choices={["light", "dark", "system"]}
                  onChange={onAppearanceChange} formatChoice={value => value[0].toUpperCase() + value.slice(1)}
                  triggerClassName="theme-appearance-trigger" />
              </span>
              <span className="theme-appearance-menu">
              <Menu
                label="Dashboard appearance"
                align="end"
                trigger={
                  <button
                    type="button"
                    className="theme-appearance-trigger"
                    aria-label="Appearance"
                    tabIndex={open ? 0 : -1}
                  >
                    <Icon name={appearance === "light" ? "sun" : appearance === "dark" ? "moon" : "monitor"} />
                    <span>{appearance[0].toUpperCase() + appearance.slice(1)}</span>
                    <Icon name="chevronDown" />
                  </button>
                }
              >
                <Dropdown.RadioGroup value={appearance} onValueChange={onAppearanceChange}>
                  {[
                    { value: "light", icon: "sun", label: "Light" },
                    { value: "dark", icon: "moon", label: "Dark" },
                    { value: "system", icon: "monitor", label: "System" },
                  ].map(({ value, icon, label }) => (
                    <Dropdown.RadioItem key={value} className="menu-item" value={value}>
                      <Icon name={icon} />
                      <span className="menu-item-label">{label}</span>
                      <Dropdown.ItemIndicator className="menu-check">
                        <Icon name="check" />
                      </Dropdown.ItemIndicator>
                    </Dropdown.RadioItem>
                  ))}
                </Dropdown.RadioGroup>
              </Menu>
              </span>
              </>
            )}
            <button
              type="button"
              className="icon-button theme-drawer-close"
              aria-label="Close theme picker"
              tabIndex={open ? 0 : -1}
              onClick={onClose}
            >
              <Icon name="cross" size={20} />
            </button>
          </div>
        </header>
      </div>
      <div ref={list} className="theme-card-list">
        {themes.map((theme) => (
          <button
            type="button"
            key={theme.id}
            className={`theme-card${selected === theme.id ? " is-active" : ""}`}
            aria-pressed={selected === theme.id}
            aria-label={`Apply ${theme.label}`}
            tabIndex={open ? 0 : -1}
            onClick={() => onApply(theme.id)}
            onPointerMove={() => {
              if (document.documentElement.dataset.appTheme !== theme.id) onPreview?.(theme.id);
            }}
            onPointerLeave={onPreviewEnd}
            onFocus={() => onPreview?.(theme.id)}
            onBlur={onPreviewEnd}
          >
            <ThemePreview theme={theme} originalTokens={originalTokens} colorScheme={colorScheme} />
            <span className="theme-card-label">{theme.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
