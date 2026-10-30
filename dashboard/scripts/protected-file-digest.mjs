import { createHash } from "node:crypto";

const ownerHashPattern = /^(?:[A-Fa-f0-9]{64})?$/u;

function utf8Source(bytes, path) {
  const source = bytes.toString("utf8");
  if (!Buffer.from(source, "utf8").equals(bytes)) {
    throw new Error(`Protected Data app runtime file is not valid UTF-8: ${path}`);
  }
  return source;
}

function skipJavascriptTrivia(source, offset) {
  while (offset < source.length) {
    if (/\s/u.test(source[offset])) {
      offset += 1;
    } else if (source.startsWith("//", offset)) {
      const lineEnd = source.slice(offset + 2).search(/[\r\n\u2028\u2029]/u);
      offset = lineEnd < 0 ? source.length : offset + 2 + lineEnd;
    } else if (source.startsWith("/*", offset)) {
      const commentEnd = source.indexOf("*/", offset + 2);
      if (commentEnd < 0) return -1;
      offset = commentEnd + 2;
    } else {
      break;
    }
  }
  return offset;
}

export function parseOwnerSeedModule(
  source,
  {
    shapeError = "The protected Data app owner module must contain exactly its expected owner exports.",
    seedError = "The protected Data app owner seed must be empty or a SHA-256 hexadecimal string.",
    conflictError = "The protected Data app user-ID and email owner seeds must be mutually exclusive.",
  } = {},
) {
  const values = [];
  let offset = skipJavascriptTrivia(source, 0);
  while (offset !== source.length) {
    const prefix = /^export const (dataAppOwner(?:UserId|Email)Sha256) = "/u.exec(source.slice(offset));
    if (offset < 0 || !prefix) {
      throw new Error(shapeError);
    }
    const start = offset + prefix[0].length;
    const end = source.indexOf('"', start);
    if (end < 0 || !source.startsWith('";', end)) {
      throw new Error(shapeError);
    }
    const value = source.slice(start, end);
    if (!ownerHashPattern.test(value)) {
      throw new Error(seedError);
    }
    values.push({ name: prefix[1], start, end, value });
    offset = skipJavascriptTrivia(source, end + 2);
  }
  // Recognize old static seed modules only to preserve/migrate existing artifacts.
  const names = values.map(({ name }) => name).join(",");
  if (!["dataAppOwnerEmailSha256", "dataAppOwnerUserIdSha256", "dataAppOwnerUserIdSha256,dataAppOwnerEmailSha256"].includes(names)) {
    throw new Error(shapeError);
  }
  if (values.filter(({ value }) => value).length > 1) {
    throw new Error(conflictError);
  }
  return values;
}

function normalizeOwner(bytes, path) {
  const source = utf8Source(bytes, path);
  const values = parseOwnerSeedModule(source);
  // Publication may change only the seed values; syntax and other bytes stay protected.
  const normalized = [];
  let offset = 0;
  for (const { start, end } of values) {
    normalized.push(source.slice(offset, start));
    offset = end;
  }
  normalized.push(source.slice(offset));
  return Buffer.from(normalized.join(""), "utf8");
}

/** Normalize publication-owned identity seeds before integrity verification. */
export function normalizeProtectedFile(path, contents) {
  const bytes = Buffer.isBuffer(contents) ? contents : Buffer.from(contents);
  if (path === "src/data-app-owner.js") return normalizeOwner(bytes, path);
  return bytes;
}

export function digestProtectedFile(path, contents) {
  return createHash("sha256").update(normalizeProtectedFile(path, contents)).digest("hex");
}
