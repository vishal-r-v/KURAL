"""
extraction.py — LLM-based complaint extraction for KURAL.

Primary:  NVIDIA NIM (Llama-3.3-70b-instruct) via OpenAI-compatible API
Fallback: Anthropic Claude (function-calling)

The extraction loop:
  1. Try NVIDIA NIM with OpenAI tool-calling format
  2. Validate result with Pydantic; retry (up to 5×) on failure,
     feeding the error back to the model as a correction prompt
  3. If NIM is unavailable or exhausts retries, fall back to Claude

Architecture note: The LLM is ONLY used here for structured extraction.
It does NOT control flow, timing, or state transitions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from pydantic import ValidationError

import anthropic
from openai import OpenAI

from backend.config import (

    get_anthropic_api_key,
    get_claude_model,
    get_nim_api_key,
    get_nim_base_url,
    get_nim_model,
    nim_is_configured,
)
from backend.models import Complaint

logger = logging.getLogger(__name__)

# Hard per-call timeout for LLM API requests. Without this, a slow/hanging
# provider blocks the *entire* FastAPI asyncio event loop (both clients below
# are synchronous SDKs and are run via asyncio.to_thread — but the client
# itself still needs a bound, or a stalled connection could hang for its
# SDK default of ~10 minutes). Verified live: NVIDIA NIM took 70s on one call
# and hung >9 minutes with no response on another — this timeout plus
# to_thread() keeps the app responsive to other requests even when a
# provider misbehaves.
_LLM_TIMEOUT_SECONDS = 20.0

# ---------------------------------------------------------------------------
# Shared tool / function schema
# ---------------------------------------------------------------------------

# OpenAI-format tool definition (used by NVIDIA NIM / Llama)
_NIM_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_complaint",
        "description": (
            "Extract structured civic complaint data from a raw voice transcript. "
            "The transcript may be in Tamil, Tanglish (Tamil+English code-mix), or English. "
            "Extract the most likely category, ward/area, urgency, and a clean English summary."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["roads", "garbage", "water", "electricity", "streetlights"],
                    "description": (
                        "The civic issue category. Choose the best match:\n"
                        "- roads: potholes, road damage, road flooding\n"
                        "- garbage: uncollected waste, overflowing bins, littering\n"
                        "- water: no water supply, pipe leakage, sewage overflow\n"
                        "- electricity: power outage, wire hazards, transformer issues\n"
                        "- streetlights: broken/non-functional street lights"
                    ),
                },
                "ward": {
                    "type": "string",
                    "description": (
                        "The Chennai ward or area name. Extract from landmarks, street names, "
                        "or area names mentioned. Common areas: Adyar, Velachery, T.Nagar, "
                        "Egmore, Sholinganallur, Perambur, Mylapore, Anna Nagar, Tambaram. "
                        "If ambiguous, use the most specific area name mentioned."
                    ),
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": (
                        "Urgency based on safety and impact:\n"
                        "- high: immediate danger (open wire, sewage flooding, major accident risk)\n"
                        "- medium: daily disruption (no water for hours, road pothole, unlit road)\n"
                        "- low: minor nuisance (single missed garbage pickup, minor flicker)"
                    ),
                },
                "urgency_reason": {
                    "type": "string",
                    "description": (
                        "One-sentence rationale for the urgency level, citing the specific "
                        "safety/impact detail from the transcript that drove the classification. "
                        "Example: 'High \u2014 exposed electrical wire poses immediate safety risk to pedestrians.' "
                        "Keep it under 200 characters."
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "A concise 1-2 sentence English summary of the complaint. "
                        "Include: what the problem is, where it is, duration if mentioned. "
                        "Keep under 300 characters."
                    ),
                },
            },
            "required": ["category", "ward", "urgency", "urgency_reason", "summary"],
        },
    },
}

# Anthropic-format tool definition (used for Claude fallback)
_CLAUDE_TOOL = {
    "name": "extract_complaint",
    "description": _NIM_TOOL["function"]["description"],
    "input_schema": {
        "type": "object",
        "properties": _NIM_TOOL["function"]["parameters"]["properties"],
        "required": _NIM_TOOL["function"]["parameters"]["required"],
    },
}

_SYSTEM_PROMPT = """You are a civic complaint intake specialist for Chennai, India.
Your job is to extract structured data from voice complaint transcripts.
Transcripts may be in Tamil, Tanglish (Tamil-English code-mix), or English.

Key knowledge:
- Chennai wards: Ward 82-Adyar, Ward 91-Velachery, Ward 55-T.Nagar, Ward 34-Egmore, Ward 118-Sholinganallur
- Common civic departments: PWD/GCC Roads, Solid Waste Management, Chennai Metro Water (CMWSSB), TANGEDCO, GCC Electrical
- Tamil civic vocabulary: சாலை (road), குப்பை (garbage), தண்ணீர் (water), மின்சாரம் (electricity), தெரு விளக்கு (streetlight)

Always provide a genuine, complaint-specific urgency_reason — never a generic
restatement of the urgency label itself.

Always call the extract_complaint function. Never respond with plain text."""


# ---------------------------------------------------------------------------
# NVIDIA NIM extraction (primary)
# ---------------------------------------------------------------------------


async def _extract_via_nim(transcript: str, max_retries: int = 5) -> Complaint:
    """
    Extract complaint using NVIDIA NIM (Llama-3.3-70b) via OpenAI-compatible API.

    Uses tool-calling in OpenAI format. Retries on Pydantic validation failure,
    feeding the error back to the model as a correction message.
    """
    client = OpenAI(
        api_key=get_nim_api_key(),
        base_url=get_nim_base_url(),
        timeout=_LLM_TIMEOUT_SECONDS,
        # The SDK's own internal retry-on-transient-error (default 2) stacks
        # on top of our retry loop and _LLM_TIMEOUT_SECONDS, compounding
        # worst-case latency. We own retry/fallback strategy here, so disable it.
        max_retries=0,
    )
    model = get_nim_model()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Extract the complaint data from this transcript:\n\n{transcript}",
        },
    ]

    last_error: str = ""

    for attempt in range(1, max_retries + 1):
        logger.info(f"[NIM] Extraction attempt {attempt}/{max_retries}")

        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=messages,
                tools=[_NIM_TOOL],
                tool_choice={"type": "function", "function": {"name": "extract_complaint"}},
                temperature=0.1,
                max_tokens=512,
            )

            choice = response.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)

            if not tool_calls:
                # No tool call returned — add to conversation and retry
                last_error = "No tool call returned. You must call extract_complaint."
                logger.warning(f"[NIM] Attempt {attempt}: {last_error}")
                messages.append({"role": "assistant", "content": choice.message.content or ""})
                messages.append({
                    "role": "user",
                    "content": f"Error: {last_error} Please call extract_complaint now.",
                })
                continue

            # Parse the tool call arguments
            raw_args = tool_calls[0].function.arguments
            if isinstance(raw_args, str):
                raw_data = json.loads(raw_args)
            else:
                raw_data = raw_args

            logger.debug(f"[NIM] Raw extraction: {json.dumps(raw_data, ensure_ascii=False)}")

            try:
                complaint = Complaint(**raw_data)
                logger.info(
                    f"[NIM] ✓ Extraction OK on attempt {attempt}: "
                    f"category={complaint.category}, ward={complaint.ward}, urgency={complaint.urgency}"
                )
                return complaint

            except ValidationError as ve:
                last_error = str(ve)
                logger.warning(f"[NIM] Attempt {attempt}: Validation failed — {last_error}")

                # Feed the error back for correction
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_calls[0].id,
                            "type": "function",
                            "function": {
                                "name": "extract_complaint",
                                "arguments": raw_args if isinstance(raw_args, str) else json.dumps(raw_args),
                            },
                        }
                    ],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_calls[0].id,
                    "content": f"Validation error: {last_error}. Fix the invalid fields and call extract_complaint again.",
                })

        except Exception as exc:
            logger.error(f"[NIM] Attempt {attempt}: API error — {exc}")
            # Fail fast on any API-level error (auth, timeout, connection, rate
            # limit). The retry loop above is for Pydantic validation errors,
            # where a corrective follow-up message can actually fix the next
            # attempt. Retrying an identical request after a timeout rarely
            # helps and burns the latency budget — verified live, NIM timed
            # out at ~60s per attempt, so 5 retries here would mean ~5 minutes
            # before the Claude fallback ever gets a chance to run.
            raise RuntimeError(f"NVIDIA NIM request failed: {exc}") from exc

    raise RuntimeError(
        f"[NIM] Extraction failed after {max_retries} attempts. Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Claude extraction (fallback)
# ---------------------------------------------------------------------------


async def _extract_via_claude(transcript: str, max_retries: int = 5) -> Complaint:
    """
    Extract complaint using Anthropic Claude as fallback.
    Same retry-on-validation-error logic as NIM.
    """
    client = anthropic.Anthropic(
        api_key=get_anthropic_api_key(),
        timeout=_LLM_TIMEOUT_SECONDS,
        max_retries=0,  # see rationale on the NIM client above
    )
    model = get_claude_model()

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": f"Extract the complaint data from this transcript:\n\n{transcript}",
        }
    ]

    last_error: str = ""

    for attempt in range(1, max_retries + 1):
        logger.info(f"[Claude] Extraction attempt {attempt}/{max_retries}")

        try:
            system = _SYSTEM_PROMPT
            if last_error and attempt > 1:
                system += (
                    f"\n\nCORRECTION NEEDED: Previous extraction failed validation:\n{last_error}\n"
                    f"Fix the invalid fields and call extract_complaint again."
                )

            response = await asyncio.to_thread(
                client.messages.create,
                model=model,
                max_tokens=512,
                system=system,
                tools=[_CLAUDE_TOOL],
                tool_choice={"type": "tool", "name": "extract_complaint"},
                messages=messages,
            )

            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use" and block.name == "extract_complaint":
                    tool_use_block = block
                    break

            if tool_use_block is None:
                last_error = "No extract_complaint tool call was made."
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": f"Error: {last_error} Please try again."})
                continue

            try:
                complaint = Complaint(**tool_use_block.input)
                logger.info(
                    f"[Claude] ✓ Extraction OK on attempt {attempt}: "
                    f"category={complaint.category}, ward={complaint.ward}"
                )
                return complaint

            except ValidationError as ve:
                last_error = str(ve)
                logger.warning(f"[Claude] Attempt {attempt}: Validation failed — {last_error}")
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "content": f"Validation error: {last_error}. Fix and retry.",
                            "is_error": True,
                        }
                    ],
                })

        except Exception as exc:
            logger.error(f"[Claude] Attempt {attempt}: API error — {exc}")
            # Fail fast on any API-level error, same rationale as the NIM
            # path — retries here are for correctable Pydantic validation
            # errors, not for transient network/timeout/rate-limit failures.
            raise RuntimeError(f"Claude request failed: {exc}") from exc

    raise RuntimeError(
        f"[Claude] Extraction failed after {max_retries} attempts. Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Public entry point — Claude first, NVIDIA NIM as secondary fallback
# ---------------------------------------------------------------------------
#
# Priority decision (2026-07-19, live-verified): Claude is primary because it
# answered every live test call in ~3-5s with correct extractions. NVIDIA NIM
# (integrate.api.nvidia.com) was live-tested and was either very slow (~70s
# on one call) or timed out entirely on repeated attempts from this
# environment — an unbounded ~20s+ tax per complaint filed is not acceptable
# for a live demo. NIM is kept as a secondary fallback (not removed) in case
# it's required for a hackathon sponsor track or becomes reliable in another
# environment — see PROGRESS.md for the full writeup.


async def extract_complaint(transcript: str, max_retries: int = 5) -> Complaint:
    """
    Extract structured complaint data from a raw transcript.

    Tries Claude first (primary — fast and reliable in live testing). Falls
    back to NVIDIA NIM (Llama-3.3-70b) only if Claude fails outright. Both
    use the same retry-on-validation-error loop.

    Args:
        transcript: Raw complaint text (Tamil/Tanglish/English).
        max_retries: Max attempts per provider.

    Returns:
        Validated Complaint object.

    Raises:
        RuntimeError: If both providers fail.
    """
    claude_error: Optional[RuntimeError] = None
    try:
        logger.info("Using Claude (primary) for extraction")
        return await _extract_via_claude(transcript, max_retries=max_retries)
    except RuntimeError as claude_exc:
        claude_error = claude_exc
        logger.warning(f"Claude extraction failed — falling back to NVIDIA NIM. Reason: {claude_exc}")

    if not nim_is_configured():
        # No fallback available — re-raise the original Claude failure.
        raise claude_error

    return await _extract_via_nim(transcript, max_retries=max_retries)
