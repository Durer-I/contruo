/**
 * Copies the pdf.js worker bundle from node_modules into public/ so the
 * browser can load it from the same origin (no third-party CDN dependency).
 *
 * Wired into the `postinstall` and `prebuild` scripts so it runs automatically
 * whenever pdfjs-dist is installed or before `next build`.
 */

import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const src = resolve(root, "node_modules/pdfjs-dist/build/pdf.worker.min.mjs");
const dest = resolve(root, "public/pdf.worker.min.mjs");

if (!existsSync(src)) {
  // Soft-fail: pdfjs-dist may not be installed yet (e.g. fresh CI shallow clone before deps install).
  console.warn(`[copy-pdf-worker] missing source: ${src}; skipping`);
  process.exit(0);
}

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`[copy-pdf-worker] copied ${src} -> ${dest}`);
