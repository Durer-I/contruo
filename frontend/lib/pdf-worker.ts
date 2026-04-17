/** Configure pdf.js worker once (browser only). Uses CDN matching installed pdfjs-dist version. */

let configured = false;

export async function configurePdfWorker(): Promise<void> {
  if (typeof window === "undefined" || configured) return;
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
  configured = true;
}
