import { createClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Paths that must not send a Bearer token (avoid stale JWT on login/register). */
function isAnonymousAuthPath(path: string): boolean {
  const base = path.includes("?") ? path.slice(0, path.indexOf("?")) : path;
  return (
    base === "/api/v1/auth/login" ||
    base === "/api/v1/auth/register" ||
    base === "/api/v1/auth/reset-password"
  );
}

class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public details: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "headers"> {
  headers?: Record<string, string>;
}

async function getAccessToken(): Promise<string | null> {
  try {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // Auto-attach JWT if not already provided (never on anonymous auth calls)
  if (!headers["Authorization"] && !isAnonymousAuthPath(path)) {
    const token = await getAccessToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = body.error || {};
    throw new ApiError(
      error.code || "UNKNOWN_ERROR",
      error.message || response.statusText,
      response.status,
      error.details || {}
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/** Upload a single file via multipart/form-data with progress reporting.
 *
 * Uses XMLHttpRequest instead of fetch because fetch's upload progress API
 * is not widely supported and we need to drive a determinate progress bar.
 */
async function uploadFile<T>(
  path: string,
  file: File,
  {
    fieldName = "file",
    onProgress,
    signal,
  }: { fieldName?: string; onProgress?: (pct: number) => void; signal?: AbortSignal } = {}
): Promise<T> {
  const token = await getAccessToken();
  return await new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append(fieldName, file, file.name);

    xhr.open("POST", `${API_URL}${path}`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      const status = xhr.status;
      let body: { error?: { code?: string; message?: string; details?: Record<string, unknown> } } = {};
      try {
        body = JSON.parse(xhr.responseText || "{}");
      } catch {
        // Ignore malformed JSON — fall back to HTTP status text below.
      }
      if (status >= 200 && status < 300) {
        resolve(body as T);
      } else {
        const err = body.error ?? {};
        reject(
          new ApiError(
            err.code ?? "UPLOAD_FAILED",
            err.message ?? xhr.statusText ?? "Upload failed",
            status,
            err.details ?? {}
          )
        );
      }
    };

    xhr.onerror = () => reject(new ApiError("NETWORK_ERROR", "Network error during upload", 0));
    xhr.onabort = () => reject(new ApiError("UPLOAD_ABORTED", "Upload aborted", 0));

    if (signal) {
      if (signal.aborted) {
        xhr.abort();
      } else {
        signal.addEventListener("abort", () => xhr.abort(), { once: true });
      }
    }

    xhr.send(form);
  });
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: "POST",
      body: JSON.stringify(body),
    }),
  patch: <T>(path: string, body: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: (path: string, options?: RequestOptions) =>
    request<void>(path, { ...options, method: "DELETE" }),
  uploadFile,
};

export { ApiError };
