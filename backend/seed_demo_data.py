"""
seed_demo_data.py — One-time demo seed script for KURAL.

⚠️  THIS IS DEMO SEED DATA, NOT REAL CITIZEN DATA. ⚠️
Every complaint inserted by this script is synthetic, clearly fabricated for
demo purposes, and its transcript/summary text says so. It exists purely so
the Public Dashboard (category/ward/department distribution, avg resolution
time) tells a real story the moment a judge opens it, before any live
complaint has been filed in the session itself.

Inserts ~18 complaints spanning all 5 categories and 10 Chennai wards, with a
realistic mix of statuses (resolved / escalated / in_progress / filed) and
`filed_at` timestamps staggered over the past two weeks. Also seeds a
correctly-formed escalation trail (including B2's simulated-notification log
entries) for the escalated/resolved records, and one deliberate B1 duplicate
pair so the dedup feature has something to show immediately.

Usage:
    source venv/bin/activate
    python -m backend.seed_demo_data            # insert seed data (skips if already seeded)
    python -m backend.seed_demo_data --wipe      # delete ALL complaints first, then seed
    python -m backend.seed_demo_data --force     # seed again even if already seeded
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from backend import db
from backend.routing import get_department_for_category, get_dept_code_for_category

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

# A fixed marker embedded in every seeded transcript so this data is always
# identifiable/removable later, and so nobody mistakes it for a real report.
_SEED_MARKER = "[DEMO SEED DATA — synthetic, not a real citizen report]"

_NOW = datetime.now(timezone.utc)


def _dept(category: str) -> tuple[str, int, str]:
    d = get_department_for_category(category)
    return d["name"], d["sla_hours"], get_dept_code_for_category(category)


def _hours_ago(hours: float) -> datetime:
    return _NOW - timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Seed records
# ---------------------------------------------------------------------------
# `filed_hours_ago` staggers filing times across the past 2 weeks (336h).
# `resolved_hours_after_filing` / `escalated_hours_after_filing` place the
# escalation-trail event realistically between filing and now.

_RECORDS = [
    dict(
        category="garbage", ward="Ward 173 - Adyar", urgency="high",
        urgency_reason="High — uncollected garbage for several days near a residential block is a health hazard.",
        summary="Garbage overflow uncollected for 4 days near Adyar Bridge residential block.",
        status="resolved", filed_hours_ago=13 * 24, resolved_hours_after_filing=6,
        resolution_note="GCC sanitation crew cleared the backlog and resumed the daily collection route on 2026-07-06.",
    ),
    dict(
        category="water", ward="Ward 175 - Velachery", urgency="medium",
        urgency_reason="Medium — no water supply for two days causes daily disruption but no immediate safety risk.",
        summary="No water supply near Phoenix Mall, Velachery for 2 days.",
        status="resolved", filed_hours_ago=12 * 24, resolved_hours_after_filing=18,
        resolution_note="Metro Water repaired a burst distribution pipe near Vijaya Nagar and restored supply.",
    ),
    dict(
        category="roads", ward="Ward 146 - T.Nagar", urgency="medium",
        urgency_reason="Medium — a growing pothole on a busy commercial road risks vehicle damage and minor accidents.",
        summary="Large pothole near Panagal Park causing traffic slowdowns.",
        status="resolved", filed_hours_ago=11 * 24, resolved_hours_after_filing=96,
        resolution_note="PWD filled and re-surfaced the pothole with bitumen mix; road inspected after 48 hours.",
    ),
    dict(
        category="electricity", ward="Ward 125 - Egmore", urgency="high",
        urgency_reason="High — a sparking transformer near a bus stop poses an immediate electrocution risk.",
        summary="Sparking transformer near Egmore Railway Station bus stop.",
        status="resolved", filed_hours_ago=10 * 24, resolved_hours_after_filing=5,
        resolution_note="TANGEDCO isolated and replaced the faulty transformer unit same day, area re-energized safely.",
    ),
    dict(
        category="streetlights", ward="Ward 193 - Sholinganallur", urgency="low",
        urgency_reason="Low — a single non-functional streetlight is a minor nuisance without acute safety impact.",
        summary="Streetlight near OMR service road not working for a week.",
        status="resolved", filed_hours_ago=9 * 24, resolved_hours_after_filing=60,
        resolution_note="GCC Electrical replaced the faulty photocell sensor and confirmed the light cycles correctly at dusk.",
    ),
    dict(
        category="garbage", ward="Ward 57 - Perambur", urgency="medium",
        urgency_reason="Medium — overflowing bins near a railway colony cause daily odor and pest disruption.",
        summary="Overflowing garbage bins near Perambur ICF Colony.",
        status="resolved", filed_hours_ago=8 * 24, resolved_hours_after_filing=10,
        resolution_note="Extra collection truck deployed to Perambur zone; bins emptied and route frequency increased.",
    ),
    dict(
        category="water", ward="Ward 167 - Mylapore", urgency="high",
        urgency_reason="High — sewage mixing with drinking water supply is an immediate public health risk.",
        summary="Sewage contamination suspected in water supply near Kapaleeshwarar Temple.",
        status="escalated", filed_hours_ago=7 * 24, escalated_hours_after_filing=25,
    ),
    dict(
        category="roads", ward="Ward 88 - Anna Nagar", urgency="medium",
        urgency_reason="Medium — a collapsed stormwater drain cover on a residential street is a fall hazard.",
        summary="Collapsed drain cover near Anna Nagar Tower creating a fall hazard.",
        status="escalated", filed_hours_ago=6 * 24, escalated_hours_after_filing=170,
    ),
    dict(
        category="electricity", ward="Ward 93 - Aminjikarai", urgency="high",
        urgency_reason="High — a low-hanging live cable over a school route poses an immediate danger to children.",
        summary="Low-hanging live electrical cable near Aminjikarai Bus Stand school route.",
        status="escalated", filed_hours_ago=5 * 24, escalated_hours_after_filing=26,
    ),
    dict(
        category="garbage", ward="Ward 184 - Kottivakkam", urgency="low",
        urgency_reason="Low — a single missed weekly pickup is a minor inconvenience, not urgent.",
        summary="Missed garbage pickup near Kottivakkam Beach this week.",
        status="resolved", filed_hours_ago=5 * 24, resolved_hours_after_filing=14,
        resolution_note="Collection crew completed the missed Kottivakkam route the following morning.",
    ),
    dict(
        category="streetlights", ward="Ward 173 - Adyar", urgency="medium",
        urgency_reason="Medium — three consecutive dark streetlights on a busy stretch raise nighttime safety concerns.",
        summary="Three consecutive streetlights out near Besant Nagar stretch.",
        status="escalated", filed_hours_ago=4 * 24, escalated_hours_after_filing=75,
    ),
    dict(
        category="water", ward="Ward 175 - Velachery", urgency="medium",
        urgency_reason="Medium — low water pressure for multiple households disrupts daily routines.",
        summary="Low water pressure affecting several households near Velachery MRTS.",
        status="resolved", filed_hours_ago=4 * 24, resolved_hours_after_filing=20,
        resolution_note="Metro Water cleared a sediment blockage in the local distribution line; pressure verified normal.",
    ),
    dict(
        category="roads", ward="Ward 146 - T.Nagar", urgency="low",
        urgency_reason="Low — faded lane markings are a minor inconvenience rather than a safety hazard.",
        summary="Faded lane markings near Ranganathan Street.",
        status="resolved", filed_hours_ago=3 * 24, resolved_hours_after_filing=40,
        resolution_note="PWD repainted lane markings along Ranganathan Street during the scheduled maintenance pass.",
    ),
    dict(
        category="garbage", ward="Ward 125 - Egmore", urgency="high",
        urgency_reason="High — a large uncleared garbage heap near a hospital entrance is a health hazard.",
        summary="Large garbage heap uncleared near a hospital entrance in Egmore.",
        status="in_progress", filed_hours_ago=2 * 24,
    ),
    dict(
        category="electricity", ward="Ward 193 - Sholinganallur", urgency="medium",
        urgency_reason="Medium — intermittent power cuts in an IT corridor disrupt daily work but pose no direct danger.",
        summary="Frequent power cuts near Tidel Park affecting local businesses.",
        status="in_progress", filed_hours_ago=1.5 * 24,
    ),
    dict(
        category="water", ward="Ward 167 - Mylapore", urgency="high",
        urgency_reason="High — no water supply for a full day near a temple market area affects many households.",
        summary="No water supply near Luz Church for over a day.",
        status="filed", filed_hours_ago=1 * 24,
        seed_as_duplicate_original=True,
    ),
    dict(
        category="water", ward="Ward 167 - Mylapore", urgency="high",
        urgency_reason="High — same ongoing no-water-supply issue reported independently by a second household.",
        summary="No water supply near Luz Church, second household reporting the same outage.",
        status="filed", filed_hours_ago=0.9 * 24,
        duplicate_of_index=15,  # points at the record above (0-indexed)
    ),
    dict(
        category="streetlights", ward="Ward 57 - Perambur", urgency="low",
        urgency_reason="Low — a single flickering streetlight is a minor nuisance, newly reported.",
        summary="Flickering streetlight near Perambur Railway Station.",
        status="filed", filed_hours_ago=0.5 * 24,
    ),
]


async def _insert_complaint(conn, rec: dict, duplicate_of_id: str | None) -> str:
    department, sla_hours, dept_code = _dept(rec["category"])
    filed_at = _hours_ago(rec["filed_hours_ago"])

    status = rec["status"]
    if status in ("filed", "in_progress"):
        # Keep these comfortably NOT overdue so the seeded data doesn't get
        # auto-escalated by the live SLA poller a minute after seeding.
        sla_deadline = _NOW + timedelta(hours=max(sla_hours, 6))
        last_checked_at = filed_at
        resolution_note = None
        escalation_count = 0
    elif status == "escalated":
        sla_deadline = filed_at + timedelta(hours=sla_hours)
        last_checked_at = filed_at + timedelta(hours=rec["escalated_hours_after_filing"])
        resolution_note = None
        escalation_count = 1
    else:  # resolved
        sla_deadline = filed_at + timedelta(hours=sla_hours)
        last_checked_at = filed_at + timedelta(hours=rec["resolved_hours_after_filing"])
        resolution_note = rec["resolution_note"]
        escalation_count = 0

    complaint_id = str(uuid.uuid4())
    raw_transcript = f"{_SEED_MARKER} {rec['summary']}"
    # Generated in filed_at chronological order (records are listed
    # oldest-first) so seeded sequence numbers read naturally, same as
    # live-filed complaints — see db.generate_ticket_id().
    ticket_id = await db.generate_ticket_id(conn, dept_code, filed_at.year)

    await conn.execute(
        """
        INSERT INTO complaints
            (id, raw_transcript, category, ward, department, urgency, status,
             summary, filed_at, sla_deadline, last_checked_at, escalation_count,
             resolution_note, urgency_reason, duplicate_of, duplicate_count, ticket_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            complaint_id,
            raw_transcript,
            rec["category"],
            rec["ward"],
            department,
            rec["urgency"],
            status,
            rec["summary"],
            filed_at.isoformat(),
            sla_deadline.isoformat(),
            last_checked_at.isoformat(),
            escalation_count,
            resolution_note,
            rec["urgency_reason"],
            duplicate_of_id,
            ticket_id,
        ),
    )

    # Escalation trail, so the complaint-detail timeline looks real immediately.
    if status == "escalated":
        escalated_at = filed_at + timedelta(hours=rec["escalated_hours_after_filing"])
        await conn.execute(
            """
            INSERT INTO escalation_trail
                (id, complaint_id, triggered_at, reason, previous_status, new_status, llm_audit_result)
            VALUES (?, ?, ?, ?, 'filed', 'escalated', NULL)
            """,
            (
                str(uuid.uuid4()), complaint_id, escalated_at.isoformat(),
                f"SLA deadline breached ({sla_hours}h SLA for {rec['category']}). Department: {department}.",
            ),
        )
        await conn.execute(
            """
            INSERT INTO escalation_trail
                (id, complaint_id, triggered_at, reason, previous_status, new_status, llm_audit_result)
            VALUES (?, ?, ?, ?, 'escalated', 'escalated', NULL)
            """,
            (
                str(uuid.uuid4()), complaint_id, escalated_at.isoformat(),
                f"{db.NOTIFICATION_LOG_MARKER} Would notify citizen via SMS: your complaint has been escalated to {department}.",
            ),
        )
    elif status == "resolved":
        resolved_at = filed_at + timedelta(hours=rec["resolved_hours_after_filing"])
        await conn.execute(
            """
            INSERT INTO escalation_trail
                (id, complaint_id, triggered_at, reason, previous_status, new_status, llm_audit_result)
            VALUES (?, ?, ?, ?, 'filed', 'resolved', 'genuine')
            """,
            (
                str(uuid.uuid4()), complaint_id, resolved_at.isoformat(),
                f"Resolution submitted and audited as genuine. {resolution_note}",
            ),
        )
        await conn.execute(
            """
            INSERT INTO escalation_trail
                (id, complaint_id, triggered_at, reason, previous_status, new_status, llm_audit_result)
            VALUES (?, ?, ?, ?, 'resolved', 'resolved', NULL)
            """,
            (
                str(uuid.uuid4()), complaint_id, resolved_at.isoformat(),
                f"{db.NOTIFICATION_LOG_MARKER} Would notify citizen via SMS: your complaint has been resolved by {department}.",
            ),
        )

    return complaint_id


async def seed(wipe: bool = False, force: bool = False) -> None:
    await db.init_db()

    async with db.get_db() as conn:
        if wipe:
            logger.info("Wiping existing complaints + escalation_trail tables…")
            await conn.execute("DELETE FROM escalation_trail")
            await conn.execute("DELETE FROM complaints")
            await conn.commit()

        async with conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE raw_transcript LIKE ?",
            (f"{_SEED_MARKER}%",),
        ) as cursor:
            row = await cursor.fetchone()
            already_seeded = row[0] if row else 0

        if already_seeded and not force and not wipe:
            logger.info(
                f"Found {already_seeded} existing seed complaint(s) — skipping "
                f"(use --force to seed again, or --wipe to reset first)."
            )
            return

        ids: list[str] = []
        for i, rec in enumerate(_RECORDS):
            duplicate_of_id = None
            if "duplicate_of_index" in rec:
                duplicate_of_id = ids[rec["duplicate_of_index"]]
            complaint_id = await _insert_complaint(conn, rec, duplicate_of_id)
            ids.append(complaint_id)

        # B1 duplicate pair: bump the original's duplicate_count now that the
        # second report has been linked to it.
        for i, rec in enumerate(_RECORDS):
            if "duplicate_of_index" in rec:
                original_id = ids[rec["duplicate_of_index"]]
                await conn.execute(
                    "UPDATE complaints SET duplicate_count = duplicate_count + 1 WHERE id = ?",
                    (original_id,),
                )

        await conn.commit()
        logger.info(f"Seeded {len(ids)} demo complaints ({_SEED_MARKER}).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wipe", action="store_true", help="Delete ALL complaints before seeding.")
    parser.add_argument("--force", action="store_true", help="Seed again even if seed data already exists.")
    args = parser.parse_args()
    asyncio.run(seed(wipe=args.wipe, force=args.force))


if __name__ == "__main__":
    main()
