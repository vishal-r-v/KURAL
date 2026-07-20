"""
routing.py — Ward/department mapping and SLA assignment for KURAL.

Maps extracted complaint category and ward to real Chennai department
data from seed_data.json. Computes SLA deadlines based on department
response-time commitments.

Pure logic, no LLM calls — deterministic routing only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data loading
# ---------------------------------------------------------------------------

_SEED_DATA_PATH = Path(__file__).parent / "seed_data.json"


@lru_cache(maxsize=1)
def _load_seed_data() -> dict:
    """Load and cache seed data from JSON file."""
    with open(_SEED_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_departments() -> dict:
    """Return the full departments dict from seed data."""
    return _load_seed_data()["departments"]


def get_wards() -> list[dict]:
    """Return the full wards list from seed data."""
    return _load_seed_data()["wards"]


# ---------------------------------------------------------------------------
# Ward resolution
# ---------------------------------------------------------------------------

def resolve_ward_with_confidence(extracted_ward: str) -> tuple[str, bool]:
    """
    Match an LLM-extracted ward name to a canonical ward display name.

    Performs fuzzy case-insensitive substring matching against:
    1. Ward display names (e.g., "Ward 82 - Adyar")
    2. Ward area names (e.g., "Adyar")
    3. Landmark names (e.g., "Adyar Bridge")

    Falls back to the default ward if no match found.

    Live-verified 2026-07-19: a complaint mentioning "Marina area" (a real,
    well-known Chennai landmark not in our seed data) silently routed to the
    default ward (Egmore) with zero indication of the fallback. That's a
    correctness/trust risk in a live demo, so this function now also reports
    whether the match was confident — callers (routing.route_complaint,
    main.py) surface this so it's never presented as a resolved location.

    Args:
        extracted_ward: Raw area/ward string from LLM extraction.

    Returns:
        Tuple of (canonical ward display string, matched: bool). matched is
        False when no known ward/landmark matched and the default was used.
    """
    seed = _load_seed_data()
    wards = seed["wards"]
    query = extracted_ward.lower().strip()

    # Try exact area match first
    for ward in wards:
        if query == ward["area"].lower():
            logger.debug(f"Resolved ward '{extracted_ward}' → '{ward['display']}' (exact area)")
            return ward["display"], True

    # Try substring match on display name
    for ward in wards:
        if query in ward["display"].lower() or ward["area"].lower() in query:
            logger.debug(f"Resolved ward '{extracted_ward}' → '{ward['display']}' (display substr)")
            return ward["display"], True

    # Try landmark match
    for ward in wards:
        for landmark in ward.get("landmarks", []):
            if landmark.lower() in query or query in landmark.lower():
                logger.debug(
                    f"Resolved ward '{extracted_ward}' → '{ward['display']}' "
                    f"(landmark: {landmark})"
                )
                return ward["display"], True

    # Fallback — no confident match found
    default = seed.get("default_ward", wards[0]["display"])
    logger.warning(
        f"Ward '{extracted_ward}' did not match any known ward. "
        f"Using default: '{default}' (UNCONFIRMED — flag for manual review)"
    )
    return default, False


def resolve_ward(extracted_ward: str) -> str:
    """Backward-compatible wrapper — see resolve_ward_with_confidence() for match confidence."""
    ward_display, _matched = resolve_ward_with_confidence(extracted_ward)
    return ward_display


# ---------------------------------------------------------------------------
# Department routing
# ---------------------------------------------------------------------------


def get_department_for_category(category: str) -> dict:
    """
    Return the department dict for a given complaint category.

    Args:
        category: One of roads/garbage/water/electricity/streetlights.

    Returns:
        Department dict with name, full_name, contact, sla_hours.

    Raises:
        KeyError: If category is not in seed data.
    """
    departments = get_departments()
    if category not in departments:
        raise KeyError(
            f"Unknown category '{category}'. "
            f"Valid categories: {list(departments.keys())}"
        )
    return departments[category]


def get_dept_code_for_category(category: str) -> str:
    """
    Return the short department code used in citizen-facing ticket IDs
    (GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE}) — e.g. 'SWM' for garbage.
    Falls back to 'GEN' if a category somehow has no code in seed data.
    """
    dept = get_department_for_category(category)
    return dept.get("code", "GEN")


def compute_sla_deadline(category: str, filed_at: Optional[datetime] = None) -> datetime:
    """
    Compute the SLA deadline for a complaint based on its category.

    Args:
        category: Complaint category string.
        filed_at: Filing timestamp (defaults to now UTC).

    Returns:
        SLA deadline datetime (UTC-aware).
    """
    if filed_at is None:
        filed_at = datetime.now(timezone.utc)

    dept = get_department_for_category(category)
    sla_hours = dept["sla_hours"]
    deadline = filed_at + timedelta(hours=sla_hours)

    logger.debug(
        f"SLA for '{category}': {sla_hours}h → deadline {deadline.isoformat()}"
    )
    return deadline


# ---------------------------------------------------------------------------
# Main routing entry point
# ---------------------------------------------------------------------------


class RouteResult:
    """Result of routing a complaint to a department."""

    def __init__(
        self,
        department_name: str,
        ward_display: str,
        sla_hours: int,
        sla_deadline: datetime,
        ward_matched: bool = True,
        dept_code: str = "GEN",
    ):
        self.department_name = department_name
        self.ward_display = ward_display
        self.sla_hours = sla_hours
        self.sla_deadline = sla_deadline
        # False when resolve_ward() had to fall back to the default ward —
        # i.e. the citizen mentioned a real place we don't have in seed data.
        # Surfaced by main.py so it's never presented as a confident match.
        self.ward_matched = ward_matched
        # Short department code (PWD/SWM/CMWSSB/TNGDC/ELEC) used to build the
        # citizen-facing ticket_id — see db.generate_ticket_id().
        self.dept_code = dept_code

    def __repr__(self) -> str:
        return (
            f"RouteResult(dept={self.department_name!r}, "
            f"ward={self.ward_display!r}, "
            f"sla={self.sla_hours}h, "
            f"ward_matched={self.ward_matched}, "
            f"dept_code={self.dept_code!r})"
        )


def route_complaint(category: str, extracted_ward: str) -> RouteResult:
    """
    Route a complaint to the correct department and compute SLA deadline.

    Args:
        category: Complaint category (roads/garbage/water/electricity/streetlights).
        extracted_ward: Raw ward/area string from LLM extraction.

    Returns:
        RouteResult with department name, canonical ward, SLA deadline, and
        whether the ward was confidently matched (vs. defaulted).
    """
    dept = get_department_for_category(category)
    ward_display, ward_matched = resolve_ward_with_confidence(extracted_ward)
    now = datetime.now(timezone.utc)
    sla_deadline = now + timedelta(hours=dept["sla_hours"])

    result = RouteResult(
        department_name=dept["name"],
        ward_display=ward_display,
        sla_hours=dept["sla_hours"],
        sla_deadline=sla_deadline,
        ward_matched=ward_matched,
        dept_code=dept.get("code", "GEN"),
    )

    logger.info(
        f"Routed: category='{category}' → dept='{dept['name']}', "
        f"ward='{ward_display}' (matched={ward_matched}), SLA={dept['sla_hours']}h"
    )
    return result


def get_all_ward_names() -> list[str]:
    """Return list of all canonical ward display names (for UI dropdowns)."""
    return [w["display"] for w in get_wards()]


def get_sla_summary() -> dict[str, int]:
    """Return a dict of category → SLA hours (for display in UI)."""
    return {cat: dept["sla_hours"] for cat, dept in get_departments().items()}
