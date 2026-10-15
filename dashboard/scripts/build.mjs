import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const snapshot = readFileSync(join(root, "src/data.json"));
const payload = JSON.parse(snapshot.toString("utf8"));
if (!payload || typeof payload !== "object" || Array.isArray(payload)
    || !payload.queries || typeof payload.queries !== "object" || Array.isArray(payload.queries)) {
  throw new Error("The dashboard snapshot must contain reviewed query data.");
}

delete process.env.CODEX_SESSION_ID;
delete process.env.CODEX_THREAD_ID;

const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const sourceHash = digest(snapshot);
const snapshotName = `snapshot.${sourceHash}.json`;
const temporary = mkdtempSync(join(root, ".atlas-build-"));
const staging = join(temporary, "dist");
const destination = join(root, "dist");
const previous = join(temporary, "previous");

try {
  const { build } = await import("vite");
  await build({ root, build: { outDir: staging, emptyOutDir: true } });
  const html = readFileSync(join(staging, "index.html"));
  const markup = html.toString("utf8");
  const metas = [...markup.matchAll(/<meta\b[^>]*>/giu)].map(([tag]) => ({
    name: tag.match(/\bname\s*=\s*["']([^"']*)["']/iu)?.[1],
    content: tag.match(/\bcontent\s*=\s*["']([^"']*)["']/iu)?.[1],
  }));
  const hashes = metas.filter((meta) => meta.name === "data-app-snapshot-sha256");
  if (hashes.length !== 1 || hashes[0].content !== sourceHash) {
    throw new Error("The built dashboard does not declare its exact source snapshot SHA256.");
  }
  if (metas.some((meta) => /^data-app-local-/u.test(meta.name ?? "")) || markup.includes(root)) {
    throw new Error("The dashboard contains local development metadata.");
  }
  if (digest(readFileSync(join(root, "src/data.json"))) !== sourceHash) {
    throw new Error("The dashboard snapshot changed during compilation. Build again.");
  }
  writeFileSync(join(staging, snapshotName), snapshot);
  const manifest = {
    version: 1,
    kind: "inline-data-v1",
    html: { path: "index.html", sha256: digest(html), bytes: html.length },
    snapshot: { path: snapshotName, sha256: sourceHash, bytes: snapshot.length },
    sourceSnapshotSha256: sourceHash,
  };
  writeFileSync(join(staging, "data-app-build.json"), JSON.stringify(manifest, null, 2) + "\n");
  if (existsSync(destination)) renameSync(destination, previous);
  try {
    renameSync(staging, destination);
  } catch (error) {
    if (existsSync(previous)) renameSync(previous, destination);
    throw error;
  }
  console.log(`Built dashboard with validated snapshot ${sourceHash}.`);
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
