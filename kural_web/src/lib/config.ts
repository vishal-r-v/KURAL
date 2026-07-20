// Single source of truth for the KURAL FastAPI backend base URL.
// Configure via .env / .env.local -> VITE_API_BASE_URL. Falls back to the
// local dev default so the app still works out of the box.
export const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";
