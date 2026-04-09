import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** FastAPI often returns `{ detail: { error: { message } } }`; some routes use top-level `error`. */
export function extractApiErrorMessage(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const d = data as { error?: { message?: string }; detail?: unknown };
  if (d.error?.message) return d.error.message;
  if (d.detail && typeof d.detail === "object" && d.detail !== null) {
    const inner = d.detail as { error?: { message?: string } };
    if (inner.error?.message) return inner.error.message;
  }
  return null;
}

export const api = axios.create({
  baseURL,
  timeout: 120_000,
  headers: { "Content-Type": "application/json" },
});

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}
