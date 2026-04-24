/**
 * Temporary dev-only HTTP instrumentation.
 *
 * Enable with NEXT_PUBLIC_DEBUG_HTTP=1 in .env.local, then open DevTools console.
 * Remove this file + DevHttpInstrumentation import when done profiling.
 */

const ENABLED = process.env.NEXT_PUBLIC_DEBUG_HTTP === "1";

const MAX_URL_LEN = 140;

function truncateUrl(url: string): string {
  if (url.length <= MAX_URL_LEN) return url;
  return `${url.slice(0, MAX_URL_LEN)}…`;
}

function resolveUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/** Monotonic "request started" order across fetch + manual XHR markers. */
let startSeq = 0;
/** Monotonic "finished" order (headers for fetch; full response for XHR). */
let doneSeq = 0;

export function debugHttpMarkStart(kind: string, url: string): number {
  if (!ENABLED) return 0;
  const id = ++startSeq;
  console.debug(`[DEBUG_HTTP] #${id} START (${kind}) ${truncateUrl(url)}`);
  return id;
}

export function debugHttpMarkDone(
  id: number,
  phase: string,
  elapsedMs: number,
  extra?: string
): void {
  if (!ENABLED || id === 0) return;
  const rank = ++doneSeq;
  const tail = extra ? ` ${extra}` : "";
  console.debug(
    `[DEBUG_HTTP] #${id} ${phase} ${elapsedMs.toFixed(1)}ms finishOrder=${rank}${tail}`
  );
}

let fetchPatched = false;

export function installDevHttpInstrumentation(): void {
  if (!ENABLED || typeof window === "undefined" || fetchPatched) return;
  fetchPatched = true;

  const original = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = resolveUrl(input);
    const id = debugHttpMarkStart("fetch", url);
    const t0 = performance.now();
    try {
      const res = await original(input, init);
      debugHttpMarkDone(id, `HEADERS status=${res.status}`, performance.now() - t0);
      return res;
    } catch (e) {
      debugHttpMarkDone(id, "FETCH_ERROR", performance.now() - t0, String(e));
      throw e;
    }
  };

  console.info(
    "[DEBUG_HTTP] Instrumentation active (fetch). Set NEXT_PUBLIC_DEBUG_HTTP=0 and restart to disable."
  );
}
