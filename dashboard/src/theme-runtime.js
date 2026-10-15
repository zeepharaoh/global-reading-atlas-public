const root = globalThis.document?.documentElement;
const media = globalThis.matchMedia
  ? matchMedia("(prefers-color-scheme: dark)")
  : { matches: false };

function applyScheme() {
  if (!root) return;
  const preference = root.dataset.appAppearance;
  const scheme = preference === "light" || preference === "dark"
    ? preference : (media.matches ? "dark" : "light");
  root.dataset.colorScheme = scheme;
  const selected = root.dataset.appTheme;
  if (selected && selected !== "original") {
    applyDataAppTheme(selected, scheme);
  } else {
    const fixed = getComputedStyle(root).getPropertyValue("--fixed-theme-scheme").trim();
    root.style.colorScheme = fixed || scheme;
  }
  const dark = root.style.colorScheme === "dark";
  root.dataset.colorScheme = dark ? "dark" : "light";
  root.style.setProperty("--lightningcss-light", dark ? " " : "initial");
  root.style.setProperty("--lightningcss-dark", dark ? "initial" : " ");
  syncDataAppBrowserThemeColor();
}

export function setDataAppAppearance(value = "system") {
  if (!root) return;
  root.dataset.appAppearance = ["light", "dark"].includes(value) ? value : "system";
  applyScheme();
}

import { applyDataAppTheme, syncDataAppBrowserThemeColor } from "./theme-presets.js";

if (root) {
  applyScheme();
  media.addEventListener?.("change", applyScheme);
}
