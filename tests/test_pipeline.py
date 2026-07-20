"""
tests/test_pipeline.py — End-to-end pipeline tests for KURAL.

Tests the full complaint lifecycle:
1. LLM extraction from Tamil/Tanglish/English text
2. Routing logic (ward resolution, department mapping, SLA computation)
3. DB operations (create, read, update, escalation trail)
4. Escalation engine (SLA breach detection, status transition)
5. Resolution audit (LLM verdict logic)

Run with: pytest tests/ -v
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Setup: ensure we can import backend modules
# ---------------------------------------------------------------------------

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use an in-memory/temp DB for tests
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("NVIDIA_NIM_API_KEY", "test-nim-key-not-real")
os.environ.setdefault("WHISPER_MODEL", "base")


# ---------------------------------------------------------------------------
# Routing tests (no external calls)
# ---------------------------------------------------------------------------


class TestRouting:
    def test_ward_resolution_exact(self):
        from backend.routing import resolve_ward
        assert "Adyar" in resolve_ward("Adyar")

    def test_ward_resolution_case_insensitive(self):
        from backend.routing import resolve_ward
        assert "Velachery" in resolve_ward("velachery")

    def test_ward_resolution_partial(self):
        from backend.routing import resolve_ward
        # T.Nagar should match "t nagar" or "tnagar"
        result = resolve_ward("Pondy Bazaar")
        assert "T.Nagar" in result or "Egmore" in result  # landmark match

    def test_ward_resolution_fallback(self):
        from backend.routing import resolve_ward
        result = resolve_ward("UnknownMysteryPlace2025")
        assert result  # should return something (default ward)

    def test_ward_resolution_confidence_flag(self):
        """Live-verified gap: unmatched wards must be flagged, not silently presented as confident."""
        from backend.routing import resolve_ward_with_confidence
        ward, matched = resolve_ward_with_confidence("Adyar")
        assert matched is True
        # Porur is a real Chennai locality but intentionally not in our (curated
        # subset of) seed wards — exercises the genuine-fallback path.
        ward, matched = resolve_ward_with_confidence("Porur signal, near unnamed lake")
        assert matched is False
        assert ward  # still returns a usable default

    def test_route_complaint_flags_unmatched_ward(self):
        from backend.routing import route_complaint
        result = route_complaint("roads", "Porur signal, near unnamed lake")
        assert result.ward_matched is False
        result = route_complaint("garbage", "Adyar")
        assert result.ward_matched is True

    def test_department_mapping_all_categories(self):
        from backend.routing import get_department_for_category
        categories = ["roads", "garbage", "water", "electricity", "streetlights"]
        for cat in categories:
            dept = get_department_for_category(cat)
            assert dept["name"]
            assert dept["sla_hours"] > 0

    def test_sla_hours_correct(self):
        from backend.routing import get_department_for_category
        assert get_department_for_category("garbage")["sla_hours"] == 12
        assert get_department_for_category("water")["sla_hours"] == 24
        assert get_department_for_category("electricity")["sla_hours"] == 24
        assert get_department_for_category("streetlights")["sla_hours"] == 72
        assert get_department_for_category("roads")["sla_hours"] == 168

    def test_route_complaint_returns_full_result(self):
        from backend.routing import route_complaint
        result = route_complaint("garbage", "Adyar")
        assert "GCC" in result.department_name or "Solid" in result.department_name
        assert "Adyar" in result.ward_display
        assert result.sla_hours == 12
        assert result.sla_deadline > datetime.now(timezone.utc)

    def test_unknown_category_raises(self):
        from backend.routing import get_department_for_category
        with pytest.raises(KeyError):
            get_department_for_category("foobar_unknown")

    def test_get_all_ward_names(self):
        from backend.routing import get_all_ward_names
        wards = get_all_ward_names()
        assert len(wards) >= 5
        assert any("Adyar" in w for w in wards)
        assert any("Velachery" in w for w in wards)

    def test_ward_coverage_expanded_to_30_plus_localities(self):
        """Part C: seed_data.json should now cover ~30-40 real Chennai localities."""
        from backend.routing import get_all_ward_names
        wards = get_all_ward_names()
        assert 30 <= len(wards) <= 45
        # Every ward name should follow the real "Ward N - Locality" format.
        assert all(w.startswith("Ward ") and " - " in w for w in wards)
        # No duplicate ward numbers.
        ward_numbers = [w.split(" - ")[0] for w in wards]
        assert len(ward_numbers) == len(set(ward_numbers))

    @pytest.mark.parametrize(
        "extracted_ward,expected_substring",
        [
            ("Besant Nagar", "Besant Nagar"),
            ("Vadapalani", "Vadapalani"),
            ("Guindy", "Guindy"),
            ("Mylapore", "Mylapore"),
            ("Thiruvanmiyur", "Thiruvanmiyur"),
            ("Ashok Nagar", "Ashok Nagar"),
            ("Kilpauk Medical College", "Kilpauk"),  # landmark match
        ],
    )
    def test_new_localities_resolve_confidently(self, extracted_ward, expected_substring):
        """Part C verification: newly-added localities must fuzzy-match confidently, not fall back."""
        from backend.routing import resolve_ward_with_confidence
        ward, matched = resolve_ward_with_confidence(extracted_ward)
        assert matched is True
        assert expected_substring in ward


# ---------------------------------------------------------------------------
# Models tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_complaint_model_valid(self):
        from backend.models import Complaint, Category, Urgency
        c = Complaint(
            category=Category.garbage,
            ward="Adyar",
            urgency=Urgency.high,
            urgency_reason="High — uncollected garbage for 3 days poses a health hazard.",
            summary="Garbage not collected for 3 days near Adyar Bridge.",
        )
        assert c.category == Category.garbage
        assert c.urgency == Urgency.high

    def test_complaint_summary_too_short_raises(self):
        from backend.models import Complaint
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            Complaint(
                category="garbage",
                ward="Adyar",
                urgency="high",
                urgency_reason="High — health hazard from uncollected garbage.",
                summary="x",  # too short
            )

    def test_complaint_invalid_category_raises(self):
        from backend.models import Complaint
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            Complaint(
                category="flying_cars",  # not valid
                ward="Adyar",
                urgency="high",
                urgency_reason="High — health hazard from uncollected garbage.",
                summary="This is a valid summary for the test.",
            )


# ---------------------------------------------------------------------------
# DB tests (async, using temp file DB)
# ---------------------------------------------------------------------------


@pytest.fixture
async def temp_db(tmp_path):
    """Set up a temporary DB for each test."""
    db_path = str(tmp_path / "test_kural.db")
    with patch.dict(os.environ, {"DB_PATH": db_path}):
        # Reload config to pick up new DB_PATH
        import importlib
        import backend.config as cfg
        import backend.db as db_module
        # Patch get_db_path in db module
        with patch("backend.db.get_db_path", return_value=db_path):
            await db_module.init_db()
            yield db_module


@pytest.mark.asyncio
async def test_db_create_and_read(tmp_path):
    """Test complaint creation and retrieval."""
    db_path = str(tmp_path / "test_kural.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        from datetime import timedelta, timezone
        sla = datetime.now(timezone.utc) + timedelta(hours=12)

        record = await db_module.create_complaint(
            raw_transcript="Adyar-la garbage collect pannala",
            category="garbage",
            ward="Ward 82 - Adyar",
            department="Solid Waste Management, GCC",
            urgency="high",
            summary="Garbage not collected in Adyar for 3 days.",
            sla_deadline=sla,
        )
        assert record.id
        assert record.category.value == "garbage"
        assert record.status.value == "filed"
        assert record.escalation_count == 0

        # Read it back
        fetched = await db_module.get_complaint(record.id)
        assert fetched.id == record.id
        assert fetched.ward == "Ward 82 - Adyar"


@pytest.mark.asyncio
async def test_db_status_update(tmp_path):
    """Test status transitions."""
    db_path = str(tmp_path / "test2_kural.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        from backend.models import ComplaintStatus
        sla = datetime.now(timezone.utc) + timedelta(hours=24)

        record = await db_module.create_complaint(
            raw_transcript="Water supply not there",
            category="water",
            ward="Ward 91 - Velachery",
            department="Chennai Metro Water",
            urgency="medium",
            summary="No water supply in Velachery for 2 days.",
            sla_deadline=sla,
        )

        await db_module.update_complaint_status(record.id, ComplaintStatus.escalated)
        updated = await db_module.get_complaint(record.id)
        assert updated.status == ComplaintStatus.escalated


@pytest.mark.asyncio
async def test_db_escalation_trail(tmp_path):
    """Test escalation event recording."""
    db_path = str(tmp_path / "test3_kural.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        from backend.models import ComplaintStatus
        sla = datetime.now(timezone.utc) - timedelta(hours=1)  # already overdue

        record = await db_module.create_complaint(
            raw_transcript="No streetlight working",
            category="streetlights",
            ward="Ward 55 - T.Nagar",
            department="GCC Electrical Dept",
            urgency="medium",
            summary="Streetlights not working on Usman Road, T.Nagar.",
            sla_deadline=sla,
        )

        event = await db_module.add_escalation_event(
            complaint_id=record.id,
            reason="SLA deadline breached",
            previous_status=ComplaintStatus.filed,
            new_status=ComplaintStatus.escalated,
        )
        assert event.id
        assert event.complaint_id == record.id

        trail = await db_module.get_escalation_trail(record.id)
        assert len(trail) == 1
        assert trail[0].new_status == ComplaintStatus.escalated


@pytest.mark.asyncio
async def test_db_get_overdue(tmp_path):
    """Test that overdue complaints are correctly identified."""
    db_path = str(tmp_path / "test4_kural.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        # Create one overdue and one not-overdue complaint
        past_sla = datetime.now(timezone.utc) - timedelta(hours=5)
        future_sla = datetime.now(timezone.utc) + timedelta(hours=5)

        overdue_rec = await db_module.create_complaint(
            raw_transcript="overdue complaint",
            category="garbage",
            ward="Ward 82 - Adyar",
            department="Solid Waste Management, GCC",
            urgency="high",
            summary="Overdue garbage complaint for testing purposes.",
            sla_deadline=past_sla,
        )
        fresh_rec = await db_module.create_complaint(
            raw_transcript="fresh complaint",
            category="water",
            ward="Ward 91 - Velachery",
            department="Chennai Metro Water",
            urgency="low",
            summary="Fresh water complaint not yet due for testing.",
            sla_deadline=future_sla,
        )

        overdue_list = await db_module.get_overdue_complaints()
        overdue_ids = [c.id for c in overdue_list]
        assert overdue_rec.id in overdue_ids
        assert fresh_rec.id not in overdue_ids


@pytest.mark.asyncio
async def test_db_simulate_time_shift(tmp_path):
    """Test that time simulation correctly shifts SLA deadlines."""
    db_path = str(tmp_path / "test5_kural.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        future_sla = datetime.now(timezone.utc) + timedelta(hours=100)
        record = await db_module.create_complaint(
            raw_transcript="roads complaint",
            category="roads",
            ward="Ward 55 - T.Nagar",
            department="PWD / GCC Engineering Dept",
            urgency="medium",
            summary="Large pothole on T.Nagar road causing traffic disruption.",
            sla_deadline=future_sla,
        )

        # Shift by 200 hours — should make it overdue
        affected = await db_module.simulate_time_shift(200)
        assert affected >= 1

        overdue = await db_module.get_overdue_complaints()
        overdue_ids = [c.id for c in overdue]
        assert record.id in overdue_ids


# ---------------------------------------------------------------------------
# Extraction tests (mocked NIM + Claude)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraction_via_nim_mocked():
    """Test the low-level NIM extraction call directly (NIM is the secondary fallback provider)."""
    from unittest.mock import patch, MagicMock

    # Build a mock OpenAI-style response with a tool_call
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "extract_complaint"
    mock_tool_call.function.arguments = json.dumps({
        "category": "garbage",
        "ward": "Adyar",
        "urgency": "high",
        "urgency_reason": "High — uncollected garbage for 3 days is a health hazard.",
        "summary": "Garbage not collected in Adyar for 3 days causing health hazard.",
    })
    mock_tool_call.id = "call_nim_abc"

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_nim_instance = MagicMock()
    mock_nim_instance.chat.completions.create.return_value = mock_response

    # Patch the OpenAI class inside the extraction module directly
    with patch("backend.extraction.OpenAI", return_value=mock_nim_instance):
        from backend.extraction import _extract_via_nim
        result = await _extract_via_nim(
            "Adyar area-la 3 naal aaga garbage collect pannala. Romba naatram."
        )
        assert result.category.value == "garbage"
        assert result.ward == "Adyar"
        assert result.urgency.value == "high"


@pytest.mark.asyncio
async def test_extraction_claude_primary_mocked():
    """Test that extract_complaint() uses Claude first and never touches NIM when Claude succeeds."""
    from unittest.mock import patch, MagicMock

    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "extract_complaint"
    mock_block.id = "tool_abc123"
    mock_block.input = {
        "category": "garbage",
        "ward": "Adyar",
        "urgency": "high",
        "urgency_reason": "High — uncollected garbage for 3 days is a health hazard.",
        "summary": "Garbage not collected in Adyar for 3 days causing health hazard.",
    }
    mock_response.content = [mock_block]

    mock_claude_instance = MagicMock()
    mock_claude_instance.messages.create.return_value = mock_response

    # NIM should never be called since Claude (primary) succeeds immediately.
    mock_nim_instance = MagicMock()
    mock_nim_instance.chat.completions.create.side_effect = AssertionError(
        "NIM should not be called when Claude succeeds"
    )

    with patch("backend.extraction.OpenAI", return_value=mock_nim_instance), \
         patch("backend.extraction.anthropic.Anthropic", return_value=mock_claude_instance):
        from backend.extraction import extract_complaint
        result = await extract_complaint(
            "Adyar area-la 3 naal aaga garbage collect pannala."
        )
        assert result.category.value == "garbage"
        assert mock_claude_instance.messages.create.call_count >= 1
        assert mock_nim_instance.chat.completions.create.call_count == 0


@pytest.mark.asyncio
async def test_extraction_nim_fallback_mocked():
    """Test that a Claude failure falls back to NVIDIA NIM extraction."""
    from unittest.mock import patch, MagicMock

    # Patch Claude to fail, NIM to succeed
    mock_claude_instance = MagicMock()
    mock_claude_instance.messages.create.side_effect = RuntimeError("Claude simulated failure")

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "extract_complaint"
    mock_tool_call.function.arguments = json.dumps({
        "category": "garbage",
        "ward": "Adyar",
        "urgency": "high",
        "urgency_reason": "High — uncollected garbage for 3 days is a health hazard.",
        "summary": "Garbage not collected in Adyar for 3 days causing health hazard.",
    })
    mock_tool_call.id = "call_nim_abc"
    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_nim_response = MagicMock()
    mock_nim_response.choices = [mock_choice]

    mock_nim_instance = MagicMock()
    mock_nim_instance.chat.completions.create.return_value = mock_nim_response

    with patch("backend.extraction.OpenAI", return_value=mock_nim_instance), \
         patch("backend.extraction.anthropic.Anthropic", return_value=mock_claude_instance):
        from backend.extraction import extract_complaint
        result = await extract_complaint(
            "Adyar area-la 3 naal aaga garbage collect pannala."
        )
        assert result.category.value == "garbage"
        assert mock_nim_instance.chat.completions.create.call_count >= 1


@pytest.mark.asyncio
async def test_extraction_retry_on_validation_error():
    """Test that NIM validation errors trigger retry with corrective context."""
    from unittest.mock import patch, MagicMock

    def make_nim_response(args_dict):
        tc = MagicMock()
        tc.function.name = "extract_complaint"
        tc.function.arguments = json.dumps(args_dict)
        tc.id = "call_x"
        choice = MagicMock()
        choice.message.tool_calls = [tc]
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    bad_resp = make_nim_response({
        "category": "invalid_category",  # fails Pydantic
        "ward": "Adyar",
        "urgency": "high",
        "urgency_reason": "High — health hazard from uncollected garbage.",
        "summary": "Valid summary text here for the complaint.",
    })
    good_resp = make_nim_response({
        "category": "garbage",
        "ward": "Adyar",
        "urgency": "high",
        "urgency_reason": "High — health hazard from uncollected garbage.",
        "summary": "Valid garbage complaint summary after correction.",
    })

    mock_nim_instance = MagicMock()
    mock_nim_instance.chat.completions.create.side_effect = [bad_resp, good_resp]

    with patch("backend.extraction.OpenAI", return_value=mock_nim_instance):
        from backend.extraction import _extract_via_nim
        result = await _extract_via_nim("Some complaint text")
        assert result.category.value == "garbage"
        # Called twice: once with bad category, once corrected
        assert mock_nim_instance.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_db_urgency_reason_persisted(tmp_path):
    """B3: urgency_reason should round-trip through create_complaint/get_complaint."""
    db_path = str(tmp_path / "test_urgency_reason.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        sla = datetime.now(timezone.utc) + timedelta(hours=24)
        record = await db_module.create_complaint(
            raw_transcript="Exposed live wire near bus stop",
            category="electricity",
            ward="Ward 91 - Velachery",
            department="TANGEDCO",
            urgency="high",
            urgency_reason="High — exposed live wire poses immediate safety risk.",
            summary="Exposed live wire near Velachery bus stop.",
            sla_deadline=sla,
        )
        assert record.urgency_reason == "High — exposed live wire poses immediate safety risk."

        fetched = await db_module.get_complaint(record.id)
        assert fetched.urgency_reason == record.urgency_reason


@pytest.mark.asyncio
async def test_db_duplicate_detection(tmp_path):
    """B1: a second complaint with the same category+ward within the window links to the first."""
    db_path = str(tmp_path / "test_dedup.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        sla = datetime.now(timezone.utc) + timedelta(hours=12)
        original = await db_module.create_complaint(
            raw_transcript="Garbage pileup near Adyar signal",
            category="garbage",
            ward="Ward 82 - Adyar",
            department="Solid Waste Management, GCC",
            urgency="medium",
            summary="Garbage overflow near Adyar signal for 2 days.",
            sla_deadline=sla,
        )

        # No duplicate yet — nothing filed against this category+ward.
        dup = await db_module.find_recent_duplicate("garbage", "Ward 82 - Adyar")
        assert dup is not None
        assert dup.id == original.id

        await db_module.increment_duplicate_count(original.id)
        refreshed = await db_module.get_complaint(original.id)
        assert refreshed.duplicate_count == 1

        # A different ward/category should NOT match.
        no_match = await db_module.find_recent_duplicate("garbage", "Ward 91 - Velachery")
        assert no_match is None

        # A resolved complaint should no longer be treated as an open duplicate target.
        await db_module.set_resolution_note(original.id, "Cleared by GCC crew on-site.")
        after_resolve = await db_module.find_recent_duplicate("garbage", "Ward 82 - Adyar")
        assert after_resolve is None


@pytest.mark.asyncio
async def test_db_notification_log(tmp_path):
    """B2: simulated notification entries land in the escalation trail, clearly marked."""
    db_path = str(tmp_path / "test_notify.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        from backend.models import ComplaintStatus
        await db_module.init_db()

        sla = datetime.now(timezone.utc) + timedelta(hours=12)
        record = await db_module.create_complaint(
            raw_transcript="Pothole on main road",
            category="roads",
            ward="Ward 55 - T.Nagar",
            department="PWD / GCC Engineering Dept",
            urgency="medium",
            summary="Large pothole on T.Nagar main road.",
            sla_deadline=sla,
        )

        event = await db_module.add_notification_log(
            record.id,
            ComplaintStatus.escalated,
            "Would notify citizen via SMS: your complaint has been escalated to PWD.",
        )
        assert db_module.NOTIFICATION_LOG_MARKER in event.reason
        assert event.previous_status == event.new_status == ComplaintStatus.escalated

        trail = await db_module.get_escalation_trail(record.id)
        assert len(trail) == 1
        assert db_module.NOTIFICATION_LOG_MARKER in trail[0].reason


# ---------------------------------------------------------------------------
# Escalation engine tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalation_poll_escalates_overdue(tmp_path):
    """Test that the SLA poll escalates overdue complaints."""
    db_path = str(tmp_path / "test_esc.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        # Create an overdue complaint
        past_sla = datetime.now(timezone.utc) - timedelta(hours=5)
        record = await db_module.create_complaint(
            raw_transcript="overdue escalation test",
            category="garbage",
            ward="Ward 82 - Adyar",
            department="Solid Waste Management, GCC",
            urgency="high",
            summary="Test overdue garbage complaint for escalation engine testing.",
            sla_deadline=past_sla,
        )

        # The escalation module imports db functions locally inside poll_sla_deadlines().
        # Patch at the db module level so local imports pick up the same DB path.
        import backend.db
        from backend.escalation import poll_sla_deadlines
        await poll_sla_deadlines()

        updated = await db_module.get_complaint(record.id)
        assert updated.status.value == "escalated"
        assert updated.escalation_count == 1

        trail = await db_module.get_escalation_trail(record.id)
        # One real state-transition event + one B2 simulated-notification event.
        assert len(trail) == 2
        assert trail[0].new_status.value == "escalated"
        assert db_module.NOTIFICATION_LOG_MARKER in trail[1].reason


# ---------------------------------------------------------------------------
# Part B (Final Wrap-Up Directive) — structured ticket_id tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_ticket_id_format_and_sequence(tmp_path):
    """New complaints get a GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE} ticket_id, incrementing per dept+year."""
    db_path = str(tmp_path / "test_ticket_id.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        sla = datetime.now(timezone.utc) + timedelta(hours=12)
        year = datetime.now(timezone.utc).year

        first = await db_module.create_complaint(
            raw_transcript="Garbage pileup",
            category="garbage",
            ward="Ward 82 - Adyar",
            department="Solid Waste Management, GCC",
            urgency="medium",
            summary="Garbage overflow near Adyar signal for 2 days.",
            sla_deadline=sla,
            dept_code="SWM",
        )
        second = await db_module.create_complaint(
            raw_transcript="Another garbage pileup",
            category="garbage",
            ward="Ward 91 - Velachery",
            department="Solid Waste Management, GCC",
            urgency="low",
            summary="Overflowing bins near Velachery MRTS.",
            sla_deadline=sla,
            dept_code="SWM",
        )
        # A different department code must not share the SWM sequence.
        electricity_rec = await db_module.create_complaint(
            raw_transcript="Sparking transformer",
            category="electricity",
            ward="Ward 34 - Egmore",
            department="TANGEDCO",
            urgency="high",
            summary="Sparking transformer near Egmore station.",
            sla_deadline=sla,
            dept_code="TNGDC",
        )

        assert first.ticket_id == f"GCC/SWM/{year}/00001"
        assert second.ticket_id == f"GCC/SWM/{year}/00002"
        assert electricity_rec.ticket_id == f"GCC/TNGDC/{year}/00001"


@pytest.mark.asyncio
async def test_db_get_complaint_by_identifier_ticket_id_and_id_fallback(tmp_path):
    """get_complaint_by_identifier() accepts either the ticket_id or the internal UUID."""
    db_path = str(tmp_path / "test_identifier.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        sla = datetime.now(timezone.utc) + timedelta(hours=12)
        record = await db_module.create_complaint(
            raw_transcript="Pothole on main road",
            category="roads",
            ward="Ward 55 - T.Nagar",
            department="PWD / GCC Engineering Dept",
            urgency="medium",
            summary="Large pothole on T.Nagar main road.",
            sla_deadline=sla,
            dept_code="PWD",
        )

        by_ticket = await db_module.get_complaint_by_identifier(record.ticket_id)
        assert by_ticket.id == record.id

        by_id = await db_module.get_complaint_by_identifier(record.id)
        assert by_id.id == record.id

        with pytest.raises(ValueError):
            await db_module.get_complaint_by_identifier("GCC/NOPE/9999/99999")


@pytest.mark.asyncio
async def test_db_backfill_assigns_ticket_ids_to_legacy_rows(tmp_path):
    """Rows inserted directly (pre-ticket_id, e.g. old seed data) get backfilled on init_db()."""
    db_path = str(tmp_path / "test_backfill.db")
    with patch("backend.db.get_db_path", return_value=db_path):
        from backend import db as db_module
        await db_module.init_db()

        # Simulate a legacy row inserted before ticket_id existed (NULL ticket_id).
        import uuid as uuid_module
        legacy_id = str(uuid_module.uuid4())
        now = datetime.now(timezone.utc)
        async with db_module.get_db() as conn:
            await conn.execute(
                """
                INSERT INTO complaints
                    (id, raw_transcript, category, ward, department, urgency, status,
                     summary, filed_at, sla_deadline, last_checked_at, escalation_count,
                     urgency_reason, ticket_id)
                VALUES (?, ?, 'water', 'Ward 43 - Mylapore', 'Chennai Metro Water', 'medium',
                        'filed', 'Legacy row missing ticket_id', ?, ?, ?, 0, '', NULL)
                """,
                (legacy_id, "legacy transcript", now.isoformat(), now.isoformat(), now.isoformat()),
            )
            await conn.commit()

        # Re-running init_db() should backfill the missing ticket_id (no partial state).
        await db_module.init_db()

        backfilled = await db_module.get_complaint(legacy_id)
        assert backfilled.ticket_id
        assert backfilled.ticket_id.startswith("GCC/CMWSSB/")


# ---------------------------------------------------------------------------
# Seed data integrity tests
# ---------------------------------------------------------------------------


class TestSeedData:
    def test_seed_data_exists(self):
        seed_path = Path(__file__).parent.parent / "backend" / "seed_data.json"
        assert seed_path.exists(), "seed_data.json not found"

    def test_seed_data_has_all_categories(self):
        seed_path = Path(__file__).parent.parent / "backend" / "seed_data.json"
        with open(seed_path) as f:
            data = json.load(f)
        required = {"roads", "garbage", "water", "electricity", "streetlights"}
        assert required.issubset(set(data["departments"].keys()))

    def test_seed_data_has_wards(self):
        seed_path = Path(__file__).parent.parent / "backend" / "seed_data.json"
        with open(seed_path) as f:
            data = json.load(f)
        assert len(data["wards"]) >= 5
        areas = [w["area"] for w in data["wards"]]
        assert "Adyar" in areas
        assert "Velachery" in areas

    def test_sla_values_sensible(self):
        seed_path = Path(__file__).parent.parent / "backend" / "seed_data.json"
        with open(seed_path) as f:
            data = json.load(f)
        for cat, dept in data["departments"].items():
            assert 1 <= dept["sla_hours"] <= 720, f"SLA for {cat} seems wrong: {dept['sla_hours']}h"
