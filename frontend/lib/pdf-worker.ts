/**
 * Configure pdf.js worker once (browser only).
 *
 * The worker file is shipped from /public so we don't depend on a third-party
 * CDN at runtime. Run `npm run prebuild` (or rerun `npm install`) when
 * upgrading pdfjs-dist to copy the matching worker; see scripts/copy-pdf-worker.
 */

let configured = false;

export async function configurePdfWorker(): Promise<void> {
  if (typeof window === "undefined" || configured) return;
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  configured = true;
}
