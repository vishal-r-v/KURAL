"""
models.py — Pydantic schemas for KURAL.

Defines the core data model for complaints, extracted entities,
and escalation events. Used throughout the pipeline for validation
and serialization.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Category(str, Enum):
    """Complaint categories mapped to Chennai departments."""

    roads = "roads"
    garbage = "garbage"
    water = "water"
    electricity = "electricity"
    streetlights = "streetlights"


class Urgency(str, Enum):
    """Urgency level extracted from the complaint."""

    low = "low"
    medium = "medium"
    high = "high"


class ComplaintStatus(str, Enum):
    """Lifecycle states for a complaint."""

    filed = "filed"
    in_progress = "in_progress"
    escalated = "escalated"
    resolved = "resolved"
    closed = "closed"


# ---------------------------------------------------------------------------
# LLM Extraction Schema
# ---------------------------------------------------------------------------


class Complaint(BaseModel):
    """
    Structured complaint data extracted by Claude from raw transcript.
    This is the schema used in Claude function-calling.
    """

    category: Category = Field(
        ...,
        description=(
            "The civic issue category: roads, garbage, water, electricity, or streetlights."
        ),
    )
    ward: str = Field(
        ...,
        description=(
            "The Chennai ward name or area where the issue is located. "
            "Examples: 'Adyar', 'Velachery', 'T.Nagar', 'Egmore', 'Sholinganallur'. "
            "If not explicitly mentioned, infer from area landmarks described."
        ),
    )
    urgency: Urgency = Field(
        ...,
        description=(
            "Urgency level based on safety risk and impact: "
            "high (immediate danger), medium (daily disruption), low (minor nuisance)."
        ),
    )
    urgency_reason: str = Field(
        ...,
        description=(
            "One-sentence rationale for the urgency level, referencing the specific "
            "safety/impact detail that drove the classification. "
            "Example: 'High — exposed electrical wire poses immediate safety risk.'"
        ),
        min_length=5,
        max_length=200,
    )
    summary: str = Field(
        ...,
        description="A concise 1-2 sentence English summary of the complaint.",
        min_length=10,
        max_length=300,
    )


# ---------------------------------------------------------------------------
# Database Record Schemas
# ---------------------------------------------------------------------------


class ComplaintRecord(BaseModel):
    """Full complaint record as stored in and retrieved from SQLite."""

    id: str
    # Citizen-facing structured ticket ID (Part B): GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE},
    # e.g. 'GCC/SWM/2026/00147'. Additive — `id` above remains the real
    # internal primary key used for all API routing; ticket_id is what
    # citizens see and quote back (Track lookup accepts either).
    ticket_id: str = ""
    raw_transcript: str
    category: Category
    ward: str
    department: str
    urgency: Urgency
    status: ComplaintStatus
    filed_at: datetime
    sla_deadline: datetime
    last_checked_at: Optional[datetime] = None
    escalation_count: int = 0
    resolution_note: Optional[str] = None
    summary: str
    urgency_reason: str = ""
    # Duplicate detection (B1): if this complaint was filed within the dedup
    # window of an existing unresolved complaint with the same category+ward,
    # `duplicate_of` points at that original complaint's id. `duplicate_count`
    # lives on the ORIGINAL and counts how many later reports were linked to it.
    duplicate_of: Optional[str] = None
    duplicate_count: int = 0

    model_config = {"from_attributes": True}


class EscalationEvent(BaseModel):
    """A single escalation event in a complaint's trail."""

    id: str
    complaint_id: str
    triggered_at: datetime
    reason: str
    previous_status: ComplaintStatus
    new_status: ComplaintStatus
    llm_audit_result: Optional[str] = None  # "genuine" | "reopen" | None


# ---------------------------------------------------------------------------
# API Request/Response Schemas
# ---------------------------------------------------------------------------


class TextComplaintRequest(BaseModel):
    """Request body for text-based complaint submission (demo fallback)."""

    text: str = Field(
        ...,
        description="Raw complaint text in Tamil, Tanglish, or English.",
        min_length=5,
    )


class ResolutionRequest(BaseModel):
    """Request body for submitting a resolution note."""

    note: str = Field(
        ...,
        description="Officer's resolution note describing how the issue was resolved.",
        min_length=10,
    )


class SimulateTimeRequest(BaseModel):
    """Request body for demo time-simulation endpoint."""

    hours: int = Field(
        default=200,
        description="How many hours to shift SLA deadlines backward (simulates time passing).",
        ge=1,
        le=10000,
    )
    complaint_id: Optional[str] = Field(
        default=None,
        description="If set, only shift this specific complaint. Otherwise shifts all.",
    )


class ComplaintListResponse(BaseModel):
    """Response for GET /complaints."""

    complaints: list[ComplaintRecord]
    total: int


class ComplaintDetailResponse(BaseModel):
    """Response for GET /complaints/{id} — includes escalation trail."""

    complaint: ComplaintRecord
    escalation_trail: list[EscalationEvent]


class LLMAuditResult(BaseModel):
    """Result of Claude's resolution audit."""

    verdict: str  # "genuine" | "reopen"
    confidence: str  # "high" | "medium" | "low"
    reasoning: str
    recommended_action: str
