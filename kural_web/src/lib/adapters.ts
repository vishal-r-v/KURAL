// adapters.ts — Map KURAL backend JSON shapes onto the existing frontend
// `Complaint` / `TimelineEvent` types (src/types.ts) so components don't
// need to change. Per integration rules: adapt the frontend to the backend,
// don't change the backend response format.

import {
  BackendComplaintRecord,
  BackendEscalationEvent,
  NOTIFICATION_LOG_MARKER,
  SlaSummaryEntry,
} from "./api.ts";
import { CategoryType, Complaint, StatusType, TimelineEvent, UrgencyType } from "../types.ts";

const CATEGORY_MAP: Record<BackendComplaintRecord["category"], CategoryType> = {
  roads: "Roads",
  garbage: "Sanitation",
  water: "Water",
  electricity: "Electricity",
  streetlights: "Electricity",
};

const URGENCY_MAP: Record<BackendComplaintRecord["urgency"], UrgencyType> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

const STATUS_MAP: Record<BackendComplaintRecord["status"], StatusType> = {
  filed: "Filed",
  in_progress: "In Progress",
  escalated: "Escalated",
  resolved: "Resolved",
  closed: "Resolved",
};

const DEFAULT_CONTACT_BY_CATEGORY: Record<BackendComplaintRecord["category"], string> = {
  roads: "1913",
  garbage: "1913",
  water: "044-45674567",
  electricity: "94987-94987",
  streetlights: "1913",
};

function extractContactNumber(raw: string | undefined): string {
  if (!raw) return "";
  // Backend format is like "Metro Water Helpline: 044-45674567" — pull the
  // trailing number/phone segment for the `tel:` link + display.
  const parts = raw.split(":");
  return parts.length > 1 ? parts[parts.length - 1].trim() : raw.trim();
}

/**
 * Display-layer only placeholder. KURAL has no real assigned-officer roster
 * in the backend schema, so rather than leaving this blank/"Pending" for
 * every complaint, generate a stable, department-scoped placeholder.
 */
function officerPlaceholder(department: string): string {
  const dept = (department || "").trim();
  return dept ? `Assigned: ${dept} Duty Officer` : "Assigned: Duty Officer";
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Pending";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "Pending";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const hours = d.getHours();
  const mins = d.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  const formattedHour = hours % 12 || 12;
  return `${months[d.getMonth()]} ${d.getDate()}, ${formattedHour}:${mins} ${ampm}`;
}

/** Build the vertical detailed timeline (Filed -> Routed -> [Escalated/Reopened]* -> Resolved). */
export function buildTimeline(
  complaint: BackendComplaintRecord,
  trail: BackendEscalationEvent[]
): TimelineEvent[] {
  const events: TimelineEvent[] = [
    {
      status: "Filed",
      title: "Filed",
      description: "Complaint registered and transcribed/extracted by KURAL AI.",
      date: formatDate(complaint.filed_at),
      isCompleted: true,
    },
    {
      status: "Routed",
      title: `Routed to ${complaint.department}`,
      description: `Auto-classified as "${complaint.category}" and assigned to ${complaint.department}.`,
      date: formatDate(complaint.filed_at),
      isCompleted: true,
    },
  ];

  for (const ev of trail) {
    // B2: simulated citizen-notification entries share the same escalation_trail
    // table (no schema change) but are marked with previous_status===new_status
    // plus this text prefix — render them as a distinct, non-transition event
    // rather than a second "Escalated"/"Resolved" milestone.
    if (ev.reason.includes(NOTIFICATION_LOG_MARKER)) {
      events.push({
        status: ev.new_status === "resolved" ? "Resolved" : "Escalated",
        title: "📱 Citizen Notified (Simulated SMS)",
        description: ev.reason.replace(NOTIFICATION_LOG_MARKER, "").trim(),
        date: formatDate(ev.triggered_at),
        isCompleted: true,
        isNotification: true,
      });
      continue;
    }
    if (ev.new_status === "escalated") {
      const wasReopened = ev.llm_audit_result === "reopen";
      events.push({
        status: "Escalated",
        title: wasReopened ? "Reopened — Resolution Rejected by AI Audit" : "SLA Breached — Auto-Escalated",
        description: ev.reason,
        date: formatDate(ev.triggered_at),
        isCompleted: true,
      });
    } else if (ev.new_status === "resolved") {
      events.push({
        status: "Resolved",
        title: "Resolved — Verified Genuine by AI Audit",
        description: ev.reason,
        date: formatDate(ev.triggered_at),
        isCompleted: true,
      });
    }
  }

  const hasResolvedEvent = events.some((e) => e.status === "Resolved");
  if (!hasResolvedEvent) {
    events.push({
      status: "Resolved",
      title: "Resolved",
      description: "Awaiting officer resolution and AI audit.",
      date: "Pending",
      isCompleted: false,
    });
  }

  return events;
}

/** Convert a backend complaint (+ optional escalation trail) into the frontend Complaint shape. */
export function toFrontendComplaint(
  record: BackendComplaintRecord,
  trail: BackendEscalationEvent[] = [],
  slaSummary?: Record<string, SlaSummaryEntry>
): Complaint {
  const wardArea = record.ward.includes(" - ") ? record.ward.split(" - ").slice(1).join(" - ") : record.ward;
  const contactRaw = slaSummary?.[record.category]?.contact;
  const contact = extractContactNumber(contactRaw) || DEFAULT_CONTACT_BY_CATEGORY[record.category];

  return {
    id: record.id,
    ticketId: record.ticket_id || record.id,
    title: record.summary || "Civic complaint",
    description: record.raw_transcript,
    location: wardArea,
    ward: record.ward,
    urgency: URGENCY_MAP[record.urgency] ?? "Medium",
    category: CATEGORY_MAP[record.category] ?? "Others",
    status: STATUS_MAP[record.status] ?? "Filed",
    department: record.department,
    contact,
    officer: officerPlaceholder(record.department),
    createdAt: record.filed_at,
    timeline: buildTimeline(record, trail),
    urgencyReason: record.urgency_reason || undefined,
    duplicateCount: record.duplicate_count || 0,
    duplicateOf: record.duplicate_of || undefined,
  };
}
