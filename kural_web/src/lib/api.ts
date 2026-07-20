// api.ts — Thin fetch abstraction over the KURAL FastAPI backend.
//
// Every network call in the app should go through this module so the base
// URL, timeout, and error handling are consistent in one place instead of
// being scattered across components with hardcoded "localhost" strings.

import { API_BASE_URL } from "./config.ts";

export type ApiErrorKind =
  | "network" // backend unreachable / CORS / DNS
  | "timeout" // request took too long
  | "validation" // 422 from FastAPI (bad input, empty transcript, etc.)
  | "not_found" // 404 (invalid complaint ID)
  | "bad_request" // 400
  | "server" // 5xx
  | "unknown";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  detail?: string;

  constructor(kind: ApiErrorKind, message: string, status?: number, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

const DEFAULT_TIMEOUT_MS = 15000;
// Voice upload + Whisper transcription + Claude extraction can legitimately
// take longer than a typical JSON request.
const VOICE_TIMEOUT_MS = 60000;

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err?.name === "AbortError") {
      throw new ApiError("timeout", "The request took too long to respond. Please try again.");
    }
    throw new ApiError(
      "network",
      "Could not reach the KURAL backend. Make sure it is running and reachable.",
    );
  }
  clearTimeout(timeoutId);

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail ?? JSON.stringify(body);
    } catch {
      detail = res.statusText;
    }

    if (res.status === 422) {
      throw new ApiError("validation", detail || "The server could not process this request.", res.status, detail);
    }
    if (res.status === 404) {
      throw new ApiError("not_found", detail || "Not found.", res.status, detail);
    }
    if (res.status === 400) {
      throw new ApiError("bad_request", detail || "Invalid request.", res.status, detail);
    }
    if (res.status >= 500) {
      throw new ApiError("server", detail || "The server ran into an internal error. Please try again.", res.status, detail);
    }
    throw new ApiError("unknown", detail || `Request failed with status ${res.status}`, res.status, detail);
  }

  // Some endpoints (none currently) could return empty bodies.
  const text = await res.text();
  return (text ? JSON.parse(text) : (undefined as unknown)) as T;
}

// ---------------------------------------------------------------------------
// Backend response shapes (subset of backend/models.py actually used here)
// ---------------------------------------------------------------------------

export interface BackendComplaintRecord {
  id: string;
  /** Part B: citizen-facing structured ticket ID, e.g. 'GCC/SWM/2026/00147'.
   *  This is the primary identifier citizens should see/quote — `id` above
   *  is the internal UUID, kept only for API routing. */
  ticket_id: string;
  raw_transcript: string;
  category: "roads" | "garbage" | "water" | "electricity" | "streetlights";
  ward: string;
  department: string;
  urgency: "low" | "medium" | "high";
  status: "filed" | "in_progress" | "escalated" | "resolved" | "closed";
  filed_at: string;
  sla_deadline: string;
  last_checked_at: string | null;
  escalation_count: number;
  resolution_note: string | null;
  summary: string;
  /** B3: one-sentence rationale Claude gives for the urgency classification. */
  urgency_reason: string;
  /** B1: set when this complaint was linked as a duplicate of an existing report. */
  duplicate_of: string | null;
  /** B1: count of later reports linked to THIS complaint as duplicates (0 if none). */
  duplicate_count: number;
}

export interface BackendEscalationEvent {
  id: string;
  complaint_id: string;
  triggered_at: string;
  reason: string;
  previous_status: BackendComplaintRecord["status"];
  new_status: BackendComplaintRecord["status"];
  llm_audit_result: "genuine" | "reopen" | null;
}

export interface SubmitComplaintResponse {
  complaint: BackendComplaintRecord;
  transcript?: string;
  sla_hours: number;
  ward_matched: boolean;
  /** B1: present on every submission; is_duplicate is true if linked to an existing report. */
  duplicate?: {
    is_duplicate: boolean;
    original_complaint_id: string | null;
    /** Part B: citizen-facing ticket ID of the original report, e.g. 'GCC/SWM/2026/00147'. */
    original_ticket_id: string | null;
    duplicate_count: number;
  };
  message: string;
}

export interface ComplaintListResponse {
  complaints: BackendComplaintRecord[];
  total: number;
}

export interface ComplaintDetailResponse {
  complaint: BackendComplaintRecord;
  escalation_trail: BackendEscalationEvent[];
}

export interface ResolveComplaintResponse {
  status: "resolved" | "reopen";
  audit: {
    verdict: "genuine" | "reopen";
    confidence: string;
    reasoning: string;
    recommended_action: string;
  };
  message: string;
}

/**
 * B2: marker prefix the backend uses (backend/db.py NOTIFICATION_LOG_MARKER)
 * to flag a simulated citizen-notification entry in the escalation trail,
 * as opposed to a real state-transition event.
 */
export const NOTIFICATION_LOG_MARKER = "[SIMULATED SMS]";

export interface SlaSummaryEntry {
  department: string;
  sla_hours: number;
  contact: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function checkHealth(): Promise<boolean> {
  try {
    await request<{ status: string }>("/health", {}, 5000);
    return true;
  } catch {
    return false;
  }
}

export async function submitTextComplaint(text: string): Promise<SubmitComplaintResponse> {
  return request<SubmitComplaintResponse>("/complaint/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

/**
 * Upload a voice recording to /complaint/voice.
 *
 * Uses XMLHttpRequest (rather than fetch) purely so we can report real
 * upload progress to the caller — fetch has no cross-browser upload
 * progress event.
 */
export function submitVoiceComplaint(
  audioBlob: Blob,
  filename: string = "recording.webm",
  onProgress?: (percent: number) => void
): Promise<SubmitComplaintResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("audio", audioBlob, filename);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/complaint/voice`);
    xhr.timeout = VOICE_TIMEOUT_MS;

    xhr.upload.onprogress = (e) => {
      if (onProgress && e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      let body: any = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        // fall through to status-based handling below
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100);
        resolve(body as SubmitComplaintResponse);
        return;
      }

      const detail = body?.detail ?? xhr.statusText ?? "Upload failed";
      if (xhr.status === 422) {
        reject(new ApiError("validation", detail, xhr.status, detail));
      } else if (xhr.status === 404) {
        reject(new ApiError("not_found", detail, xhr.status, detail));
      } else if (xhr.status === 400) {
        reject(new ApiError("bad_request", detail, xhr.status, detail));
      } else if (xhr.status >= 500) {
        reject(new ApiError("server", detail, xhr.status, detail));
      } else {
        reject(new ApiError("unknown", detail, xhr.status, detail));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError("network", "Could not reach the KURAL backend. Make sure it is running and reachable."));
    };
    xhr.ontimeout = () => {
      reject(new ApiError("timeout", "The upload took too long. Please try again."));
    };

    xhr.send(formData);
  });
}

export async function listComplaints(params: {
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<ComplaintListResponse> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  search.set("limit", String(params.limit ?? 200));
  search.set("offset", String(params.offset ?? 0));
  return request<ComplaintListResponse>(`/complaints?${search.toString()}`);
}

export async function getComplaint(id: string): Promise<ComplaintDetailResponse> {
  return request<ComplaintDetailResponse>(`/complaints/${encodeURIComponent(id)}`);
}

export async function resolveComplaint(
  id: string,
  note: string
): Promise<ResolveComplaintResponse> {
  return request<ResolveComplaintResponse>(`/complaints/${encodeURIComponent(id)}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
}

export async function getSlaSummary(): Promise<Record<string, SlaSummaryEntry>> {
  return request<Record<string, SlaSummaryEntry>>("/meta/sla");
}

export interface WardDetail {
  id: string;
  display: string;
  area: string;
  lat: number | null;
  lng: number | null;
}

/** Ward names + approximate lat/lng, used to plot the ward coverage map. */
export async function getWardDetails(): Promise<WardDetail[]> {
  const res = await request<{ wards: string[]; ward_details: WardDetail[] }>("/meta/wards");
  return res.ward_details ?? [];
}

/** Turn any thrown error into a friendly, user-facing message. */
export function friendlyErrorMessage(err: unknown, language: "English" | "Tamil" = "English"): string {
  if (err instanceof ApiError) {
    switch (err.kind) {
      case "network":
        return language === "English"
          ? "Can't connect to the KURAL server right now. Please check your connection and try again."
          : "KURAL சேவையகத்துடன் இணைக்க முடியவில்லை. தொடர்பை சரிபார்த்து மீண்டும் முயற்சிக்கவும்.";
      case "timeout":
        return language === "English"
          ? "The server took too long to respond. Please try again."
          : "சேவையகம் பதிலளிக்க அதிக நேரம் எடுத்தது. மீண்டும் முயற்சிக்கவும்.";
      case "validation":
        return err.detail || (language === "English"
          ? "We couldn't process that. Please check your input and try again."
          : "இதை செயலாக்க முடியவில்லை. உள்ளீட்டை சரிபார்த்து மீண்டும் முயற்சிக்கவும்.");
      case "not_found":
        return language === "English"
          ? "We couldn't find a complaint with that ID. Please double-check and try again."
          : "இந்த எண்ணில் புகார் எதுவும் இல்லை. சரிபார்த்து மீண்டும் முயற்சிக்கவும்.";
      case "server":
        return language === "English"
          ? "Something went wrong on our end. Please try again in a moment."
          : "எங்கள் தரப்பில் ஒரு பிழை ஏற்பட்டது. சிறிது நேரத்தில் மீண்டும் முயற்சிக்கவும்.";
      default:
        return err.message || (language === "English" ? "Something went wrong." : "ஒரு பிழை ஏற்பட்டது.");
    }
  }
  return language === "English" ? "Something went wrong. Please try again." : "ஒரு பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.";
}
