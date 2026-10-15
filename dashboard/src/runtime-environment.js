import { canonicalDashboardPath } from "./chart-permalink.js";
import { dashboardViewSearchParams } from "./dashboard-url-state.js";
import { safeSourceHref } from "./source-provenance.js";

// Keep report identity and task working directories on the same local-path
// boundary. Drive-relative paths and UNC shares are not absolute local paths.
export function isSafeLocalDataAppPath(value) {
  return typeof value === "string" && value.length <= 2048
    && /^(?:\/(?![\\/])|[A-Za-z]:[\\/])/u.test(value)
    && !/[\u0000-\u001f\u007f]/u.test(value);
}

function isLocalDevelopmentHost(hostname = "") {
  return (
    typeof hostname === "string" &&
    (["localhost", "127.0.0.1", "[::1]", "terminal.local"].includes(hostname) || hostname.endsWith(".localhost"))
  );
}

function normalizedLocalPreviewPath(value, directory = false) {
  if (typeof value !== "string" || !value || /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/u.test(value)) return null;

  const windowsDrive = /^[A-Za-z]:[\\/]/u.test(value);
  const windowsShare = /^(?:\\\\|\/\/)/u.test(value);
  const windows = windowsDrive || windowsShare;
  if (!windows && value.includes("\\")) return null;
  let path = windows ? value.replaceAll("\\", "/") : value;
  if (!directory && path.endsWith("/")) return null;

  let anchor;
  let remainder;
  if (windowsDrive) {
    anchor = path.slice(0, 3);
    remainder = path.slice(3);
  } else if (windowsShare) {
    const share = /^\/\/([^/]+)\/([^/]+)(?:\/|$)/u.exec(path);
    if (!share) return null;
    anchor = `//${share[1]}/${share[2]}`;
    remainder = path.slice(share[0].length);
  } else if (path.startsWith("/")) {
    anchor = "/";
    remainder = path.slice(1);
  } else {
    return null;
  }

  if (directory) remainder = remainder.replace(/\/+$/u, "");
  const parts = remainder ? remainder.split("/") : [];
  if (parts.some((part) => !part || part === "." || part === "..")) return null;
  if (windows) {
    const windowsParts = windowsShare ? [...anchor.slice(2).split("/"), ...parts] : parts;
    // Win32 removes trailing dots/spaces and gives colons/device prefixes special
    // meaning. Do not accept paths whose filesystem meaning differs from this
    // lexical containment check.
    if (windowsParts.some((part) => /[<>:"|?*]|[. ]$/u.test(part) || part === "." || part === "..")) return null;
  }

  path = parts.length ? `${anchor.endsWith("/") ? anchor : `${anchor}/`}${parts.join("/")}` : anchor;
  return { path, key: windows ? path.toLowerCase() : path, windows };
}

function localPreviewReference(source) {
  if (!["http:", "https:"].includes(source.protocol) || !isLocalDevelopmentHost(source.hostname)) return null;
  try {
    const entries = globalThis.document?.querySelectorAll?.('meta[name="data-app-local-reference"]');
    if (entries?.length !== 1) return null;
    const value = JSON.parse(entries[0].getAttribute("content"));
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    if (Object.keys(value).length !== 2 || !Object.hasOwn(value, "root") || !Object.hasOwn(value, "htmlPath")) {
      return null;
    }
    const root = normalizedLocalPreviewPath(value.root, true);
    const html = normalizedLocalPreviewPath(value.htmlPath);
    if (!root || !html || root.windows !== html.windows || !/\.html?$/iu.test(html.path)) return null;
    const prefix = root.key.endsWith("/") ? root.key : `${root.key}/`;
    if (!html.key.startsWith(prefix)) return null;
    return { root: root.path, htmlPath: html.path };
  } catch {
    return null;
  }
}

// Dashboard navigation state is the only query data that may accompany an
// otherwise safe artifact URL. Keep source-link credential/path checks intact.
export function safeDataAppSourceHref(value) {
  if (typeof value !== "string") return null;
  try {
    const source = new URL(value);
    const view = dashboardViewSearchParams(source);
    if ([...source.searchParams].length !== [...view].length
      || [...source.searchParams.keys()].some(key => !view.has(key))) return null;
    source.search = "";
    const safe = safeSourceHref(source.href);
    if (!safe) return null;
    const result = new URL(safe);
    result.search = view.toString();
    return result.href;
  } catch {
    return null;
  }
}

// Read the current page without transferring credentials or unrelated routing
// parameters. Unlike the artifact identity, this also retains local preview URLs.
export function currentDataAppViewUrl(location = globalThis.window?.location) {
  if (!location?.href) return null;
  try {
    const source = new URL(location.href);
    if (!["http:", "https:"].includes(source.protocol)) return null;
    source.username = "";
    source.password = "";
    source.search = dashboardViewSearchParams(source).toString();
    source.hash = "";
    source.pathname = canonicalDashboardPath(source.pathname);
    return safeDataAppSourceHref(source.href);
  } catch {
    return null;
  }
}

export function currentDataAppReference(
  location = globalThis.window?.location,
  projectRoot = typeof __DATA_APP_PROJECT_ROOT__ === "string" ? __DATA_APP_PROJECT_ROOT__ : "",
) {
  if (!location?.href) return {};

  let source;
  try {
    source = new URL(location.href);
  } catch {
    return {};
  }
  source.username = "";
  source.password = "";
  source.search = ["http:", "https:"].includes(source.protocol)
    ? dashboardViewSearchParams(source).toString()
    : "";
  source.hash = "";
  // URL normalizes file://localhost to an empty authority. Any remaining
  // authority denotes a network path, not a local report working directory.
  if (source.protocol === "file:" && source.hostname) return {};
  if (isLocalDevelopmentHost(source.hostname)) {
    return (
      localPreviewReference(source) ??
      (projectRoot ? { root: projectRoot, htmlPath: `${projectRoot}/dist/index.html` } : {})
    );
  }
  if (["http:", "https:"].includes(source.protocol)) {
    source.pathname = canonicalDashboardPath(source.pathname);
  }

  if (source.protocol !== "file:") {
    return { sourceUrl: source.toString() };
  }

  // Encoded separators must not change the filesystem hierarchy on decoding.
  if (/%2f|%5c/iu.test(source.pathname)) return {};
  let htmlPath;
  try {
    htmlPath = decodeURIComponent(source.pathname);
  } catch {
    return {};
  }
  // File URLs retain a leading slash before a Windows drive, unlike local
  // filesystem paths passed to the native task's working-directory parameter.
  if (/^\/[A-Za-z]:\//u.test(htmlPath)) htmlPath = htmlPath.slice(1);
  if (!isSafeLocalDataAppPath(htmlPath)) return {};
  const directory = htmlPath.replace(/\/[^/]*$/u, "");
  const projectDirectory = directory.endsWith("/dist") ? directory.slice(0, -5) : directory;
  const root = /^[A-Za-z]:$/u.test(projectDirectory) ? `${projectDirectory}/` : projectDirectory || "/";
  return { htmlPath, root, sourceUrl: source.toString() };
}
