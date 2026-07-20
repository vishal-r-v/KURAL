"""
main.py — FastAPI application entry point for KURAL.

Routes:
  POST /complaint/voice        — audio file upload → full pipeline
  POST /complaint/text         — text input → pipeline (demo fallback)
  GET  /complaints             — list all complaints
  GET  /complaints/{id}        — single complaint + escalation trail
  POST /complaints/{id}/resolve — submit resolution note + LLM audit
  POST /demo/simulate-time     — shift SLA deadlines (demo trigger)
  POST /demo/trigger-escalation — manually fire SLA check now
  GET  /health                 — health check
  GET  /meta/wards             — list all Chennai wards
  GET  /meta/sla               — SLA hours by category

Architecture: All LLM calls happen inside extraction.py (intake)
and escalation.py (audit only). The scheduler in escalation.py
owns all state transitions. This main.py is purely a thin HTTP layer.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend import db, escalation
from backend.extraction import extract_complaint
from backend.models import (
    ComplaintDetailResponse,
    ComplaintListResponse,
    ComplaintStatus,
    ResolutionRequest,
    SimulateTimeRequest,
    TextComplaintRequest,
)
from backend.routing import get_all_ward_names, get_sla_summary, route_complaint
from backend.stt import transcribe_upload

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start scheduler on startup; clean up on shutdown."""
    logger.info("KURAL backend starting up…")
    await db.init_db()
    logger.info("Database initialized")
    escalation.start_scheduler()
    yield
    escalation.stop_scheduler()
    logger.info("KURAL backend shut down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="KURAL — AI Civic Grievance Agent",
    description=(
        "Voice-first civic grievance filing and escalation for Chennai citizens. "
        "Supports Tamil, Tanglish, and English."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hackathon: open CORS for Streamlit frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["system"])
async def health():
    """Basic liveness check."""
    return {"status": "ok", "service": "KURAL"}


# ---------------------------------------------------------------------------
# Metadata endpoints
# ---------------------------------------------------------------------------


@app.get("/meta/wards", tags=["metadata"])
async def list_wards():
    """
    List all Chennai wards available for routing.

    Returns both the flat `wards` name list (unchanged, existing consumers
    keep working) and a new additive `ward_details` list with each ward's
    `display` name plus its approximate `lat`/`lng` (used by the frontend's
    ward-coverage map — see Part E of the final wrap-up pass). No existing
    field was removed or renamed.
    """
    from backend.routing import get_wards

    return {
        "wards": get_all_ward_names(),
        "ward_details": [
            {
                "id": w["id"],
                "display": w["display"],
                "area": w.get("area", ""),
                "lat": w.get("lat"),
                "lng": w.get("lng"),
            }
            for w in get_wards()
        ],
    }


@app.get("/meta/sla", tags=["metadata"])
async def get_sla_info():
    """Return SLA hours by category and full department names."""
    from backend.routing import get_departments
    departments = get_departments()
    return {
        cat: {
            "department": info["name"],
            "sla_hours": info["sla_hours"],
            "contact": info.get("contact", ""),
        }
        for cat, info in departments.items()
    }


# ---------------------------------------------------------------------------
# Complaint submission — voice
# ---------------------------------------------------------------------------


@app.post("/complaint/voice", tags=["complaints"])
async def submit_voice_complaint(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, m4a, webm)"),
):
    """
    Accept a voice audio file and run the full pipeline:
    STT → LLM extraction → routing → DB persist.

    Returns the created complaint record.
    """
    # Validate file type
    allowed_types = {"audio/wav", "audio/wave", "audio/mpeg", "audio/mp3",
                     "audio/mp4", "audio/m4a", "audio/webm", "audio/ogg",
                     "video/webm", "application/octet-stream"}
    if audio.content_type and audio.content_type not in allowed_types:
        # Be permissive — some browsers send wrong content-type
        logger.warning(f"Unexpected content-type: {audio.content_type}")

    # Determine file suffix
    filename = audio.filename or "upload"
    suffix = Path(filename).suffix or ".wav"

    logger.info(f"Voice complaint received: {filename} ({audio.content_type})")

    # Read audio bytes
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    # STT transcription
    try:
        transcript = await transcribe_upload(audio_bytes, suffix=suffix)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=f"Transcription failed: {exc}")

    # LLM extraction — never echo raw SDK exception text to the client
    # (Anthropic/OpenAI error strings can include partial request metadata).
    try:
        complaint = await extract_complaint(transcript)
    except RuntimeError as exc:
        logger.exception("Complaint extraction failed after voice STT: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Complaint extraction failed. Please try again in a moment.",
        )

    # Routing
    route = route_complaint(complaint.category.value, complaint.ward)

    # B1 — duplicate detection: same category + ward, filed within the dedup
    # window, still unresolved. See db.find_recent_duplicate() for details.
    duplicate = await db.find_recent_duplicate(complaint.category.value, route.ward_display)

    # Persist
    record = await db.create_complaint(
        raw_transcript=transcript,
        category=complaint.category.value,
        ward=route.ward_display,
        department=route.department_name,
        urgency=complaint.urgency.value,
        summary=complaint.summary,
        sla_deadline=route.sla_deadline,
        urgency_reason=complaint.urgency_reason,
        duplicate_of=duplicate.id if duplicate else None,
        dept_code=route.dept_code,
    )
    if duplicate:
        await db.increment_duplicate_count(duplicate.id)

    logger.info(f"Complaint filed: {record.ticket_id} ({record.id[:8]}…) → {route.department_name}")

    message = f"Complaint filed successfully. Routed to {route.department_name}."
    if not route.ward_matched:
        message += (
            f" ⚠️ Ward could not be confidently identified from the complaint — "
            f"defaulted to {route.ward_display}. Please verify the location manually."
        )
    if duplicate:
        total_reports = duplicate.duplicate_count + 1
        message += (
            f" 📌 {total_reports} citizen(s) have now reported this same issue in "
            f"{route.ward_display} — linked as a duplicate of complaint {duplicate.ticket_id}."
        )

    return {
        "complaint": record.model_dump(mode="json"),
        "transcript": transcript,
        "sla_hours": route.sla_hours,
        "ward_matched": route.ward_matched,
        "duplicate": {
            "is_duplicate": duplicate is not None,
            "original_complaint_id": duplicate.id if duplicate else None,
            "original_ticket_id": duplicate.ticket_id if duplicate else None,
            "duplicate_count": (duplicate.duplicate_count + 1) if duplicate else 0,
        },
        "message": message,
    }


# ---------------------------------------------------------------------------
# Complaint submission — text (demo fallback)
# ---------------------------------------------------------------------------


@app.post("/complaint/text", tags=["complaints"])
async def submit_text_complaint(body: TextComplaintRequest):
    """
    Accept raw text and run extraction → routing → persist.
    Useful as a demo fallback when audio is unavailable.
    """
    logger.info(f"Text complaint received: {body.text[:80]}…")

    try:
        complaint = await extract_complaint(body.text)
    except RuntimeError as exc:
        # Log the real cause server-side; return a generic message so SDK
        # error strings (which can include partial request details) never
        # reach the browser / API consumer.
        logger.exception("Complaint extraction failed for text submission: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Complaint extraction failed. Please try again in a moment.",
        )

    route = route_complaint(complaint.category.value, complaint.ward)

    duplicate = await db.find_recent_duplicate(complaint.category.value, route.ward_display)

    record = await db.create_complaint(
        raw_transcript=body.text,
        category=complaint.category.value,
        ward=route.ward_display,
        department=route.department_name,
        urgency=complaint.urgency.value,
        summary=complaint.summary,
        sla_deadline=route.sla_deadline,
        urgency_reason=complaint.urgency_reason,
        duplicate_of=duplicate.id if duplicate else None,
        dept_code=route.dept_code,
    )
    if duplicate:
        await db.increment_duplicate_count(duplicate.id)

    message = f"Complaint filed. Routed to {route.department_name}."
    if not route.ward_matched:
        message += (
            f" ⚠️ Ward could not be confidently identified from the complaint — "
            f"defaulted to {route.ward_display}. Please verify the location manually."
        )
    if duplicate:
        total_reports = duplicate.duplicate_count + 1
        message += (
            f" 📌 {total_reports} citizen(s) have now reported this same issue in "
            f"{route.ward_display} — linked as a duplicate of complaint {duplicate.ticket_id}."
        )

    return {
        "complaint": record.model_dump(mode="json"),
        "sla_hours": route.sla_hours,
        "ward_matched": route.ward_matched,
        "duplicate": {
            "is_duplicate": duplicate is not None,
            "original_complaint_id": duplicate.id if duplicate else None,
            "original_ticket_id": duplicate.ticket_id if duplicate else None,
            "duplicate_count": (duplicate.duplicate_count + 1) if duplicate else 0,
        },
        "message": message,
    }


# ---------------------------------------------------------------------------
# Complaint retrieval
# ---------------------------------------------------------------------------


@app.get("/complaints", tags=["complaints"])
async def list_complaints(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List complaints with optional status filter."""
    # Validate status if provided
    if status and status not in [s.value for s in ComplaintStatus]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Valid: {[s.value for s in ComplaintStatus]}",
        )

    complaints = await db.list_complaints(status=status, limit=limit, offset=offset)
    total = await db.count_complaints(status=status)

    return {
        "complaints": [c.model_dump(mode="json") for c in complaints],
        "total": total,
    }


@app.get("/complaints/{complaint_id:path}", tags=["complaints"])
async def get_complaint(complaint_id: str):
    """
    Get a single complaint with its full escalation trail.

    `complaint_id` accepts EITHER the citizen-facing `ticket_id`
    (e.g. 'GCC/SWM/2026/00147' — the primary form citizens are shown and
    expected to use) OR the internal UUID `id` (kept working as a fallback).

    Uses the `:path` converter (not the default single-segment matcher)
    because `ticket_id` itself contains literal slashes
    (`GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE}`) — a plain `{complaint_id}` string
    param cannot match a value with embedded `/` even when the client
    percent-encodes it, since ASGI servers unquote the path before Starlette
    routes it.
    """
    try:
        complaint = await db.get_complaint_by_identifier(complaint_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Complaint {complaint_id!r} not found")

    trail = await db.get_escalation_trail(complaint.id)

    return {
        "complaint": complaint.model_dump(mode="json"),
        "escalation_trail": [e.model_dump(mode="json") for e in trail],
    }


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@app.post("/complaints/{complaint_id:path}/resolve", tags=["complaints"])
async def resolve_complaint(complaint_id: str, body: ResolutionRequest):
    """
    Submit a resolution note for a complaint.
    Runs LLM audit to evaluate resolution quality.

    `complaint_id` accepts either the citizen-facing `ticket_id` or the
    internal UUID `id` — see get_complaint() above for the same fallback
    and the same `:path` converter rationale (ticket_id contains slashes).
    """
    try:
        complaint = await db.get_complaint_by_identifier(complaint_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Complaint {complaint_id!r} not found")
    complaint_id = complaint.id

    if complaint.status == ComplaintStatus.resolved:
        raise HTTPException(status_code=400, detail="Complaint is already resolved")

    # LLM audit of resolution quality
    audit_result = await escalation.audit_resolution(
        complaint_summary=complaint.summary,
        complaint_category=complaint.category.value,
        resolution_note=body.note,
    )

    if audit_result.verdict == "genuine":
        # Mark as resolved
        await db.set_resolution_note(complaint_id, body.note)
        await db.add_escalation_event(
            complaint_id=complaint_id,
            reason=f"Resolution submitted and audited as genuine. {audit_result.reasoning}",
            previous_status=complaint.status,
            new_status=ComplaintStatus.resolved,
            llm_audit_result=audit_result.verdict,
        )
        # B2 — simulated citizen notification (no real SMS/notification
        # infrastructure; clearly labelled as such — see db.add_notification_log).
        await db.add_notification_log(
            complaint_id,
            ComplaintStatus.resolved,
            f"Would notify citizen via SMS: your complaint has been resolved by {complaint.department}.",
        )
        return {
            "status": "resolved",
            "audit": audit_result.model_dump(),
            "message": "Complaint resolved. LLM audit verified resolution as genuine.",
        }
    else:
        # Reopen / keep escalated. Mirrors the state-transition pattern the
        # SLA scheduler uses (backend/escalation.py): persist the new status
        # first so the trail's `new_status` matches what's actually stored —
        # without this, a rejected resolution would leave `status` stuck on
        # its old value (e.g. still "filed") while the trail claims
        # "escalated", which is exactly the kind of mismatch the Track page
        # and History view would surface as a visible bug.
        await db.update_complaint_status(complaint_id, ComplaintStatus.escalated)
        await db.increment_escalation_count(complaint_id)
        await db.add_escalation_event(
            complaint_id=complaint_id,
            reason=f"Resolution submitted but LLM audit flagged as insufficient. {audit_result.reasoning}",
            previous_status=complaint.status,
            new_status=ComplaintStatus.escalated,
            llm_audit_result=audit_result.verdict,
        )
        # B2 — simulated citizen notification (see db.add_notification_log).
        await db.add_notification_log(
            complaint_id,
            ComplaintStatus.escalated,
            f"Would notify citizen via SMS: your complaint's resolution was rejected and has been re-escalated to {complaint.department}.",
        )
        return {
            "status": "reopen",
            "audit": audit_result.model_dump(),
            "message": f"Resolution flagged for review: {audit_result.recommended_action}",
        }


# ---------------------------------------------------------------------------
# Demo endpoints
# ---------------------------------------------------------------------------


@app.post("/demo/simulate-time", tags=["demo"])
async def simulate_time(body: SimulateTimeRequest):
    """
    Shift SLA deadlines backward by `hours` hours for demo purposes.
    After calling this, use /demo/trigger-escalation to fire the SLA check.
    """
    affected = await db.simulate_time_shift(body.hours, body.complaint_id)
    return {
        "message": f"Shifted SLA deadlines backward by {body.hours}h for {affected} complaint(s)",
        "affected": affected,
        "hours_shifted": body.hours,
    }


@app.post("/demo/trigger-escalation", tags=["demo"])
async def trigger_escalation():
    """
    Immediately run the SLA polling check.
    Use after /demo/simulate-time to see escalations fire in real time.
    """
    escalated_ids = await escalation.trigger_escalation_check_now()
    return {
        "escalated": escalated_ids,
        "count": len(escalated_ids),
        "message": (
            f"Escalated {len(escalated_ids)} complaint(s)"
            if escalated_ids
            else "No overdue complaints found. Use /demo/simulate-time first."
        ),
    }
