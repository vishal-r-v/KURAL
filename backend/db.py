"""
db.py — SQLite database setup and query layer for KURAL.

Uses aiosqlite for async operations within FastAPI.
Provides all CRUD functions needed by the complaint pipeline.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiosqlite

from backend.config import get_db_path
from backend.models import (
    Category,
    ComplaintRecord,
    ComplaintStatus,
    EscalationEvent,
    Urgency,
)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_CREATE_COMPLAINTS = """
CREATE TABLE IF NOT EXISTS complaints (
    id              TEXT PRIMARY KEY,
    raw_transcript  TEXT NOT NULL,
    category        TEXT NOT NULL,
    ward            TEXT NOT NULL,
    department      TEXT NOT NULL,
    urgency         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'filed',
    summary         TEXT NOT NULL DEFAULT '',
    filed_at        TIMESTAMP NOT NULL,
    sla_deadline    TIMESTAMP NOT NULL,
    last_checked_at TIMESTAMP,
    escalation_count INTEGER NOT NULL DEFAULT 0,
    resolution_note TEXT,
    urgency_reason  TEXT NOT NULL DEFAULT '',
    duplicate_of    TEXT REFERENCES complaints(id),
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    ticket_id       TEXT
);
"""

# Additive columns for DBs created before this migration existed. Fresh DBs
# already get these via _CREATE_COMPLAINTS above; ALTER TABLE is a no-op
# (skipped) if the column already exists — see _ensure_columns().
#
# ticket_id has no inline UNIQUE here because SQLite's ALTER TABLE ADD COLUMN
# can't add a UNIQUE constraint to an existing table in one step; uniqueness
# is instead enforced by a separate `CREATE UNIQUE INDEX` (see
# _CREATE_TICKET_ID_INDEX below), created only AFTER _backfill_ticket_ids()
# has filled in every legacy row so the index never sees duplicate NULLs
# racing a partially-backfilled table.
_COMPLAINTS_MIGRATIONS: list[tuple[str, str]] = [
    ("urgency_reason", "ALTER TABLE complaints ADD COLUMN urgency_reason TEXT NOT NULL DEFAULT ''"),
    ("duplicate_of", "ALTER TABLE complaints ADD COLUMN duplicate_of TEXT REFERENCES complaints(id)"),
    ("duplicate_count", "ALTER TABLE complaints ADD COLUMN duplicate_count INTEGER NOT NULL DEFAULT 0"),
    ("ticket_id", "ALTER TABLE complaints ADD COLUMN ticket_id TEXT"),
]

_CREATE_TICKET_ID_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_complaints_ticket_id ON complaints(ticket_id);"
)

_CREATE_ESCALATION_TRAIL = """
CREATE TABLE IF NOT EXISTS escalation_trail (
    id              TEXT PRIMARY KEY,
    complaint_id    TEXT NOT NULL REFERENCES complaints(id),
    triggered_at    TIMESTAMP NOT NULL,
    reason          TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    new_status      TEXT NOT NULL,
    llm_audit_result TEXT
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);",
    "CREATE INDEX IF NOT EXISTS idx_complaints_sla ON complaints(sla_deadline);",
    "CREATE INDEX IF NOT EXISTS idx_escalation_complaint ON escalation_trail(complaint_id);",
]


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager yielding a database connection."""
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        yield conn


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


async def _ensure_columns(conn: aiosqlite.Connection) -> None:
    """Add any additive columns missing from a pre-existing `complaints` table."""
    async with conn.execute("PRAGMA table_info(complaints)") as cursor:
        existing = {row[1] for row in await cursor.fetchall()}
    for column, ddl in _COMPLAINTS_MIGRATIONS:
        if column not in existing:
            await conn.execute(ddl)


async def init_db() -> None:
    """Create tables and indexes if they don't exist. Called at app startup."""
    async with get_db() as conn:
        await conn.execute(_CREATE_COMPLAINTS)
        await conn.execute(_CREATE_ESCALATION_TRAIL)
        await _ensure_columns(conn)
        await _backfill_ticket_ids(conn)
        for idx_sql in _CREATE_INDEXES:
            await conn.execute(idx_sql)
        await conn.execute(_CREATE_TICKET_ID_INDEX)
        await conn.commit()


async def _backfill_ticket_ids(conn: aiosqlite.Connection) -> None:
    """
    Assign a `ticket_id` to any pre-existing row that doesn't have one yet
    (rows created before the GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE} ticket format
    was introduced). Processed oldest-filed-first so sequence numbers stay
    chronological within each department+year, same as newly-filed complaints.
    """
    from backend.routing import get_dept_code_for_category

    async with conn.execute(
        "SELECT id, category, filed_at FROM complaints WHERE ticket_id IS NULL ORDER BY filed_at ASC"
    ) as cursor:
        rows = await cursor.fetchall()

    for row in rows:
        d = dict(row)
        dept_code = get_dept_code_for_category(d["category"])
        filed_at = _parse_dt(d["filed_at"]) or datetime.now(timezone.utc)
        ticket_id = await generate_ticket_id(conn, dept_code, filed_at.year)
        await conn.execute(
            "UPDATE complaints SET ticket_id = ? WHERE id = ?",
            (ticket_id, d["id"]),
        )


async def generate_ticket_id(conn: aiosqlite.Connection, dept_code: str, year: int) -> str:
    """
    Generate the next sequential citizen-facing ticket_id for a given
    department+year, in the format GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE}
    (e.g. 'GCC/SWM/2026/00147'), resembling real Indian grievance-system
    ticket formats (CPGRAMS-style). This is additive/citizen-display only —
    the internal UUID `id` remains the real primary key used everywhere
    else in the codebase.

    Looks at the highest existing sequence for this dept+year and
    increments it. Good enough for a single-process demo (no dedicated
    counter table needed) — call sites always run inside the same
    connection/transaction as the row insert/update that consumes the
    result, so there's no cross-request race in practice.
    """
    prefix = f"GCC/{dept_code}/{year}/"
    async with conn.execute(
        "SELECT ticket_id FROM complaints WHERE ticket_id LIKE ? ORDER BY ticket_id DESC LIMIT 1",
        (f"{prefix}%",),
    ) as cursor:
        row = await cursor.fetchone()

    last_seq = 0
    if row and row[0]:
        try:
            last_seq = int(row[0].rsplit("/", 1)[-1])
        except ValueError:
            last_seq = 0

    return f"{prefix}{last_seq + 1:05d}"


# ---------------------------------------------------------------------------
# Complaint CRUD
# ---------------------------------------------------------------------------


def _row_to_complaint(row: aiosqlite.Row) -> ComplaintRecord:
    """Convert a DB row dict to a ComplaintRecord."""
    d = dict(row)
    return ComplaintRecord(
        id=d["id"],
        raw_transcript=d["raw_transcript"],
        category=Category(d["category"]),
        ward=d["ward"],
        department=d["department"],
        urgency=Urgency(d["urgency"]),
        status=ComplaintStatus(d["status"]),
        summary=d.get("summary", ""),
        filed_at=_parse_dt(d["filed_at"]),
        sla_deadline=_parse_dt(d["sla_deadline"]),
        last_checked_at=_parse_dt(d["last_checked_at"]) if d["last_checked_at"] else None,
        escalation_count=d["escalation_count"],
        resolution_note=d["resolution_note"],
        urgency_reason=d.get("urgency_reason") or "",
        duplicate_of=d.get("duplicate_of"),
        duplicate_count=d.get("duplicate_count") or 0,
        ticket_id=d.get("ticket_id") or "",
    )


def _parse_dt(value: str | datetime | None) -> datetime | None:
    """Parse datetime from SQLite string or passthrough if already datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # SQLite returns ISO strings; parse them
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


async def create_complaint(
    *,
    raw_transcript: str,
    category: str,
    ward: str,
    department: str,
    urgency: str,
    summary: str,
    sla_deadline: datetime,
    urgency_reason: str = "",
    duplicate_of: Optional[str] = None,
    dept_code: str = "GEN",
) -> ComplaintRecord:
    """Insert a new complaint and return the created record."""
    complaint_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with get_db() as conn:
        ticket_id = await generate_ticket_id(conn, dept_code, now.year)
        await conn.execute(
            """
            INSERT INTO complaints
                (id, raw_transcript, category, ward, department, urgency, status,
                 summary, filed_at, sla_deadline, last_checked_at, escalation_count,
                 urgency_reason, duplicate_of, ticket_id)
            VALUES (?, ?, ?, ?, ?, ?, 'filed', ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                complaint_id,
                raw_transcript,
                category,
                ward,
                department,
                urgency,
                summary,
                now.isoformat(),
                sla_deadline.isoformat(),
                now.isoformat(),
                urgency_reason,
                duplicate_of,
                ticket_id,
            ),
        )
        await conn.commit()

    return await get_complaint(complaint_id)


async def get_complaint(complaint_id: str) -> ComplaintRecord:
    """Fetch a single complaint by ID. Raises ValueError if not found."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Complaint {complaint_id!r} not found")
            return _row_to_complaint(row)


async def get_complaint_by_identifier(identifier: str) -> ComplaintRecord:
    """
    Citizen-facing complaint lookup (Part B — real ticket ID format).

    Accepts either the public `ticket_id` (e.g. 'GCC/SWM/2026/00147' — the
    primary identifier citizens are shown and expected to remember/quote)
    OR the internal UUID `id`, which keeps working as a fallback so
    anything that already links by internal id (e.g. links from the
    duplicate-detection feature) doesn't break. Raises ValueError if
    neither matches.
    """
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM complaints WHERE ticket_id = ?", (identifier,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            async with conn.execute(
                "SELECT * FROM complaints WHERE id = ?", (identifier,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ValueError(f"Complaint {identifier!r} not found")
        return _row_to_complaint(row)


async def list_complaints(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ComplaintRecord]:
    """List complaints, optionally filtered by status."""
    async with get_db() as conn:
        if status:
            sql = "SELECT * FROM complaints WHERE status = ? ORDER BY filed_at DESC LIMIT ? OFFSET ?"
            params = (status, limit, offset)
        else:
            sql = "SELECT * FROM complaints ORDER BY filed_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)

        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_complaint(r) for r in rows]


async def count_complaints(status: Optional[str] = None) -> int:
    """Count complaints, optionally filtered by status."""
    async with get_db() as conn:
        if status:
            sql = "SELECT COUNT(*) FROM complaints WHERE status = ?"
            params = (status,)
        else:
            sql = "SELECT COUNT(*) FROM complaints"
            params = ()

        async with conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def update_complaint_status(
    complaint_id: str,
    new_status: ComplaintStatus,
) -> None:
    """Update a complaint's status and last_checked_at timestamp."""
    now = datetime.now(timezone.utc)
    async with get_db() as conn:
        await conn.execute(
            "UPDATE complaints SET status = ?, last_checked_at = ? WHERE id = ?",
            (new_status.value, now.isoformat(), complaint_id),
        )
        await conn.commit()


async def increment_escalation_count(complaint_id: str) -> None:
    """Increment the escalation counter for a complaint."""
    async with get_db() as conn:
        await conn.execute(
            "UPDATE complaints SET escalation_count = escalation_count + 1 WHERE id = ?",
            (complaint_id,),
        )
        await conn.commit()


async def set_resolution_note(complaint_id: str, note: str) -> None:
    """Attach a resolution note and mark complaint as resolved."""
    now = datetime.now(timezone.utc)
    async with get_db() as conn:
        await conn.execute(
            """
            UPDATE complaints
            SET resolution_note = ?, status = 'resolved', last_checked_at = ?
            WHERE id = ?
            """,
            (note, now.isoformat(), complaint_id),
        )
        await conn.commit()


async def simulate_time_shift(hours: int, complaint_id: Optional[str] = None) -> int:
    """
    Shift SLA deadlines backward by `hours` hours (for demo purposes).
    Returns the number of complaints affected.
    """
    from datetime import timedelta

    async with get_db() as conn:
        if complaint_id:
            result = await conn.execute(
                """
                UPDATE complaints
                SET sla_deadline = datetime(sla_deadline, ?)
                WHERE id = ? AND status NOT IN ('resolved', 'closed')
                """,
                (f"-{hours} hours", complaint_id),
            )
        else:
            result = await conn.execute(
                """
                UPDATE complaints
                SET sla_deadline = datetime(sla_deadline, ?)
                WHERE status NOT IN ('resolved', 'closed')
                """,
                (f"-{hours} hours",),
            )
        await conn.commit()
        return result.rowcount


async def find_recent_duplicate(
    category: str,
    ward: str,
    hours: int = 24,
) -> Optional[ComplaintRecord]:
    """
    B1 — Duplicate complaint detection.

    Look for an existing, still-unresolved complaint with the same
    category + ward filed within the last `hours` hours (demo-compressible
    window). If found, the caller should link the new complaint to it
    instead of treating it as a fully independent report.

    Returns the OLDEST matching complaint (the "original"), or None.
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM complaints
            WHERE category = ? AND ward = ?
              AND status NOT IN ('resolved', 'closed')
              AND filed_at >= ?
            ORDER BY filed_at ASC
            LIMIT 1
            """,
            (category, ward, cutoff.isoformat()),
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_complaint(row) if row else None


async def increment_duplicate_count(complaint_id: str) -> None:
    """Increment the duplicate counter on the ORIGINAL complaint of a dedup group."""
    async with get_db() as conn:
        await conn.execute(
            "UPDATE complaints SET duplicate_count = duplicate_count + 1 WHERE id = ?",
            (complaint_id,),
        )
        await conn.commit()


async def get_overdue_complaints() -> list[ComplaintRecord]:
    """Return all active complaints whose SLA deadline has passed."""
    now = datetime.now(timezone.utc)
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM complaints
            WHERE status IN ('filed', 'in_progress')
              AND sla_deadline < ?
            ORDER BY sla_deadline ASC
            """,
            (now.isoformat(),),
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_complaint(r) for r in rows]


# ---------------------------------------------------------------------------
# Escalation Trail CRUD
# ---------------------------------------------------------------------------


def _row_to_escalation(row: aiosqlite.Row) -> EscalationEvent:
    """Convert a DB row to an EscalationEvent."""
    d = dict(row)
    return EscalationEvent(
        id=d["id"],
        complaint_id=d["complaint_id"],
        triggered_at=_parse_dt(d["triggered_at"]),
        reason=d["reason"],
        previous_status=ComplaintStatus(d["previous_status"]),
        new_status=ComplaintStatus(d["new_status"]),
        llm_audit_result=d.get("llm_audit_result"),
    )


async def add_escalation_event(
    complaint_id: str,
    reason: str,
    previous_status: ComplaintStatus,
    new_status: ComplaintStatus,
    llm_audit_result: Optional[str] = None,
) -> EscalationEvent:
    """Record an escalation event in the trail."""
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO escalation_trail
                (id, complaint_id, triggered_at, reason, previous_status, new_status, llm_audit_result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                complaint_id,
                now.isoformat(),
                reason,
                previous_status.value,
                new_status.value,
                llm_audit_result,
            ),
        )
        await conn.commit()

    return EscalationEvent(
        id=event_id,
        complaint_id=complaint_id,
        triggered_at=now,
        reason=reason,
        previous_status=previous_status,
        new_status=new_status,
        llm_audit_result=llm_audit_result,
    )


# B2 — Simulated citizen notification log. No real SMS/notification
# infrastructure exists (or is planned) — this marker lets callers append a
# clearly-labelled "would have notified the citizen" entry to the SAME
# escalation_trail table (no schema change needed) whenever a complaint
# transitions to escalated/resolved. `previous_status == new_status` here
# is intentional: it signals "this row is a notification log entry, not an
# actual state transition" to any reader (frontend adapters filter on it).
NOTIFICATION_LOG_MARKER = "[SIMULATED SMS]"


async def add_notification_log(
    complaint_id: str,
    status: ComplaintStatus,
    message: str,
) -> EscalationEvent:
    """Append a simulated citizen-notification entry to the escalation trail."""
    return await add_escalation_event(
        complaint_id=complaint_id,
        reason=f"{NOTIFICATION_LOG_MARKER} {message}",
        previous_status=status,
        new_status=status,
    )


async def get_escalation_trail(complaint_id: str) -> list[EscalationEvent]:
    """Return all escalation events for a complaint, ordered chronologically."""
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM escalation_trail
            WHERE complaint_id = ?
            ORDER BY triggered_at ASC
            """,
            (complaint_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_escalation(r) for r in rows]
