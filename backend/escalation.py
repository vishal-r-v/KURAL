"""
escalation.py — APScheduler SLA engine and LLM resolution audit for KURAL.

Critical architecture boundary:
- The SCHEDULER (APScheduler) controls all timing and state transitions.
  It polls for overdue complaints and escalates them deterministically.
- The LLM is ONLY called as an audit function when a resolution note is
  submitted — it evaluates whether the resolution is genuine and recommends
  whether to close or reopen the complaint.

Primary LLM:  NVIDIA NIM (Llama-3.3-70b-instruct) via OpenAI-compatible API
Fallback LLM: Anthropic Claude

The LLM NEVER controls flow, timing, or SLA transitions directly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic
from openai import OpenAI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import (
    get_anthropic_api_key,
    get_claude_model,
    get_nim_api_key,
    get_nim_base_url,
    get_nim_model,
    get_sla_poll_interval_seconds,
    nim_is_configured,
)
from backend.models import ComplaintStatus, LLMAuditResult

logger = logging.getLogger(__name__)

# See backend/extraction.py for rationale — a per-call timeout plus running
# the synchronous SDK call in a thread keeps the FastAPI event loop (and thus
# the APScheduler SLA poller sharing that loop) responsive even if a provider
# hangs. Verified live: an unbounded NIM call froze the entire app.
_LLM_TIMEOUT_SECONDS = 20.0

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None

# ---------------------------------------------------------------------------
# Shared audit tool schema
# ---------------------------------------------------------------------------

_AUDIT_FUNCTION_PARAMS = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["genuine", "reopen"],
            "description": (
                "'genuine' if the resolution note clearly describes what was fixed "
                "and the issue is likely resolved. "
                "'reopen' if the note is vague, dismissive, or the described action "
                "seems insufficient for the complaint."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence level in the verdict.",
        },
        "reasoning": {
            "type": "string",
            "description": (
                "1-2 sentence explanation of the verdict, referencing specific "
                "content from the resolution note and original complaint."
            ),
        },
        "recommended_action": {
            "type": "string",
            "description": (
                "Specific recommended next step, e.g., "
                "'Close complaint — pothole filled and road surface inspected.' or "
                "'Reopen — note says issue noted but no action described.'"
            ),
        },
    },
    "required": ["verdict", "confidence", "reasoning", "recommended_action"],
}

# OpenAI-format tool (for NIM)
_NIM_AUDIT_TOOL = {
    "type": "function",
    "function": {
        "name": "audit_resolution",
        "description": (
            "Evaluate whether a civic complaint resolution note describes a genuine resolution "
            "or is vague/incomplete. Recommend whether to close the complaint or reopen it."
        ),
        "parameters": _AUDIT_FUNCTION_PARAMS,
    },
}

# Anthropic-format tool (for Claude fallback)
_CLAUDE_AUDIT_TOOL = {
    "name": "audit_resolution",
    "description": _NIM_AUDIT_TOOL["function"]["description"],
    "input_schema": _AUDIT_FUNCTION_PARAMS,
}

_AUDIT_SYSTEM = """You are a civic grievance audit specialist for Chennai Municipal Corporation.
Your job is to evaluate whether resolution notes from field officers represent genuine resolutions.

Red flags for reopening:
- Vague language: "issue noted", "will be addressed", "inspected"
- No specific action described
- Action doesn't match complaint type
- No timeline or completion mentioned

Signs of genuine resolution:
- Specific action taken: "pothole filled with bitumen mix on [date]"
- Resources deployed: "garbage truck deployed, area cleared"
- Supervisor sign-off or measurements mentioned

Always call the audit_resolution function."""


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global APScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            job_defaults={"coalesce": True, "max_instances": 1}
        )
    return _scheduler


def start_scheduler() -> None:
    """Start the SLA polling scheduler. Called at FastAPI startup."""
    scheduler = get_scheduler()
    poll_interval = get_sla_poll_interval_seconds()
    scheduler.add_job(
        poll_sla_deadlines,
        trigger=IntervalTrigger(seconds=poll_interval),
        id="sla_poll",
        name="SLA Deadline Poller",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"SLA scheduler started — polling every {poll_interval}s")


def stop_scheduler() -> None:
    """Stop the scheduler. Called at FastAPI shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("SLA scheduler stopped")


# ---------------------------------------------------------------------------
# SLA polling job (deterministic — no LLM)
# ---------------------------------------------------------------------------


async def poll_sla_deadlines() -> None:
    """
    Check all active complaints for SLA breaches and escalate overdue ones.

    Deterministic — no LLM involved. APScheduler calls this on a fixed interval.
    """
    from backend.db import (
        add_escalation_event,
        add_notification_log,
        get_overdue_complaints,
        increment_escalation_count,
        update_complaint_status,
    )

    try:
        overdue = await get_overdue_complaints()
        if not overdue:
            logger.debug("SLA poll: no overdue complaints")
            return

        logger.info(f"SLA poll: found {len(overdue)} overdue complaint(s)")

        for complaint in overdue:
            now = datetime.now(timezone.utc)
            hours_overdue = (now - complaint.sla_deadline).total_seconds() / 3600
            reason = (
                f"SLA deadline breached: {complaint.sla_deadline.strftime('%Y-%m-%d %H:%M UTC')} "
                f"({hours_overdue:.1f}h overdue). "
                f"Department: {complaint.department}. "
                f"Complaint: {complaint.summary}"
            )
            prev_status = complaint.status
            await update_complaint_status(complaint.id, ComplaintStatus.escalated)
            await increment_escalation_count(complaint.id)
            await add_escalation_event(
                complaint_id=complaint.id,
                reason=reason,
                previous_status=prev_status,
                new_status=ComplaintStatus.escalated,
            )
            # B2 — simulated citizen notification (see db.add_notification_log).
            await add_notification_log(
                complaint.id,
                ComplaintStatus.escalated,
                f"Would notify citizen via SMS: your complaint has been escalated to {complaint.department}.",
            )
            logger.warning(
                f"ESCALATED: {complaint.id[:8]}… | "
                f"category={complaint.category} | ward={complaint.ward} | "
                f"overdue={hours_overdue:.1f}h"
            )
    except Exception as exc:
        logger.error(f"SLA poll failed: {exc}", exc_info=True)


async def trigger_escalation_check_now() -> list[str]:
    """Manually fire an immediate SLA check (used by /demo/trigger-escalation)."""
    from backend.db import (
        add_escalation_event,
        add_notification_log,
        get_overdue_complaints,
        increment_escalation_count,
        update_complaint_status,
    )

    overdue = await get_overdue_complaints()
    escalated_ids = []

    for complaint in overdue:
        now = datetime.now(timezone.utc)
        hours_overdue = (now - complaint.sla_deadline).total_seconds() / 3600
        reason = (
            f"SLA deadline breached: {complaint.sla_deadline.strftime('%Y-%m-%d %H:%M UTC')} "
            f"({hours_overdue:.1f}h overdue). Department: {complaint.department}."
        )
        prev_status = complaint.status
        await update_complaint_status(complaint.id, ComplaintStatus.escalated)
        await increment_escalation_count(complaint.id)
        await add_escalation_event(
            complaint_id=complaint.id,
            reason=reason,
            previous_status=prev_status,
            new_status=ComplaintStatus.escalated,
        )
        # B2 — simulated citizen notification (see db.add_notification_log).
        await add_notification_log(
            complaint.id,
            ComplaintStatus.escalated,
            f"Would notify citizen via SMS: your complaint has been escalated to {complaint.department}.",
        )
        escalated_ids.append(complaint.id)

    return escalated_ids


# ---------------------------------------------------------------------------
# LLM Audit — NIM first, Claude fallback
# ---------------------------------------------------------------------------


async def _audit_via_nim(
    complaint_summary: str,
    complaint_category: str,
    resolution_note: str,
) -> LLMAuditResult:
    """Run resolution audit using NVIDIA NIM (Llama-3.3-70b)."""
    client = OpenAI(
        api_key=get_nim_api_key(),
        base_url=get_nim_base_url(),
        timeout=_LLM_TIMEOUT_SECONDS,
        max_retries=0,  # see backend/extraction.py — avoid compounding SDK retries
    )

    prompt = (
        f"Original complaint (category: {complaint_category}):\n{complaint_summary}\n\n"
        f"Resolution note submitted by officer:\n{resolution_note}\n\n"
        f"Audit this resolution and call the audit_resolution function."
    )

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=get_nim_model(),
        messages=[
            {"role": "system", "content": _AUDIT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        tools=[_NIM_AUDIT_TOOL],
        tool_choice={"type": "function", "function": {"name": "audit_resolution"}},
        temperature=0.1,
        max_tokens=512,
    )

    choice = response.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None)
    if not tool_calls:
        raise RuntimeError("[NIM] audit_resolution tool was not called")

    raw = tool_calls[0].function.arguments
    data = json.loads(raw) if isinstance(raw, str) else raw
    result = LLMAuditResult(**data)
    logger.info(f"[NIM] Audit verdict: {result.verdict} ({result.confidence}) — {result.reasoning}")
    return result


async def _audit_via_claude(
    complaint_summary: str,
    complaint_category: str,
    resolution_note: str,
) -> LLMAuditResult:
    """Run resolution audit using Anthropic Claude (fallback)."""
    client = anthropic.Anthropic(
        api_key=get_anthropic_api_key(),
        timeout=_LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )
    prompt = (
        f"Original complaint (category: {complaint_category}):\n{complaint_summary}\n\n"
        f"Resolution note submitted by officer:\n{resolution_note}\n\n"
        f"Audit this resolution and call the audit_resolution function."
    )

    response = await asyncio.to_thread(
        client.messages.create,
        model=get_claude_model(),
        max_tokens=512,
        system=_AUDIT_SYSTEM,
        tools=[_CLAUDE_AUDIT_TOOL],
        tool_choice={"type": "tool", "name": "audit_resolution"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "audit_resolution":
            result = LLMAuditResult(**block.input)
            logger.info(f"[Claude] Audit verdict: {result.verdict} ({result.confidence})")
            return result

    raise RuntimeError("[Claude] audit_resolution tool was not called")


async def audit_resolution(
    complaint_summary: str,
    complaint_category: str,
    resolution_note: str,
) -> LLMAuditResult:
    """
    Evaluate whether an officer's resolution note is genuine.

    Uses Claude (primary — fast and reliable in live testing) → falls back
    to NVIDIA NIM → fails open with a 'reopen' verdict if both are
    unavailable. See backend/extraction.py for the priority rationale.

    This is the ONLY place the LLM influences a resolution outcome.
    """
    # Try Claude first
    claude_error: Optional[Exception] = None
    try:
        logger.info("Using Claude (primary) for resolution audit")
        return await _audit_via_claude(complaint_summary, complaint_category, resolution_note)
    except Exception as exc:
        claude_error = exc
        logger.warning(f"Claude audit failed — falling back to NVIDIA NIM. Reason: {exc}")

    # NIM fallback
    if not nim_is_configured():
        logger.error("Claude audit failed and NVIDIA NIM is not configured")
        return LLMAuditResult(
            verdict="reopen",
            confidence="low",
            reasoning=f"Audit service unavailable: {claude_error}",
            recommended_action="Manual review required — LLM audit failed.",
        )

    try:
        logger.info("Using NVIDIA NIM (fallback) for resolution audit")
        return await _audit_via_nim(complaint_summary, complaint_category, resolution_note)
    except Exception as exc:
        logger.error(f"Both Claude and NIM audit failed: {exc}")
        # Fail open — flag for manual review rather than silently closing
        return LLMAuditResult(
            verdict="reopen",
            confidence="low",
            reasoning=f"Audit service unavailable: {exc}",
            recommended_action="Manual review required — LLM audit failed.",
        )
