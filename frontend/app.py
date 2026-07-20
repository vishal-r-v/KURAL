"""
frontend/app.py — Streamlit dashboard for KURAL.

Provides:
- Voice/text complaint submission UI
- Live complaint list with status badges + auto-refresh
- Complaint detail view with escalation timeline
- Demo controls: "Simulate Time Passing" + "Trigger Escalation"
- Resolution submission with LLM audit result display
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BACKEND_URL = os.getenv("KURAL_BACKEND_URL", "http://localhost:8000")

# B2: must match backend.db.NOTIFICATION_LOG_MARKER — this Streamlit app talks
# to the backend purely over HTTP, so it can't import the constant directly.
NOTIFICATION_LOG_MARKER = "[SIMULATED SMS]"

# Status → (emoji, color)
STATUS_META = {
    "filed":       ("📋", "#4A90D9", "#1a2740"),
    "in_progress": ("⚙️",  "#F5A623", "#2a1f0a"),
    "escalated":   ("🚨", "#E74C3C", "#2a0a0a"),
    "resolved":    ("✅", "#27AE60", "#0a2a14"),
    "closed":      ("🔒", "#7F8C8D", "#1a1a1a"),
}

URGENCY_META = {
    "high":   ("🔴", "HIGH"),
    "medium": ("🟡", "MEDIUM"),
    "low":    ("🟢", "LOW"),
}

CATEGORY_ICONS = {
    "roads":        "🛣️",
    "garbage":      "🗑️",
    "water":        "💧",
    "electricity":  "⚡",
    "streetlights": "💡",
}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="KURAL — Civic Voice Agent",
    page_icon="🗣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* Import fonts. Noto Sans Tamil is required so Tamil transcripts / ward
   names render as real glyphs instead of "tofu" boxes ([]) — Inter and
   Space Grotesk have no Tamil Unicode coverage on their own. Appended
   (not prepended) to every font-family value below so Latin text keeps
   using Inter/Space Grotesk and only Tamil characters fall back to it. */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;600;700&family=Noto+Sans+Tamil:wght@400;500;600;700&display=swap');

/* Root variables */
:root {
    --bg-primary: #0a0f1e;
    --bg-secondary: #111827;
    --bg-card: #1a2035;
    --bg-card-hover: #1e2540;
    --accent-blue: #3b82f6;
    --accent-purple: #8b5cf6;
    --accent-cyan: #06b6d4;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-orange: #f59e0b;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --border: #1e293b;
    --border-accent: #2d3f5f;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
    --shadow-lg: 0 8px 48px rgba(0,0,0,0.5);
    --radius: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
}

/* Global styles */
.stApp {
    background: var(--bg-primary) !important;
    font-family: 'Inter', 'Noto Sans Tamil', sans-serif;
    color: var(--text-primary);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border);
}

/* Headings */
h1, h2, h3 { font-family: 'Space Grotesk', 'Noto Sans Tamil', sans-serif; color: var(--text-primary); }
h1 { font-size: 2rem; font-weight: 700; }
h2 { font-size: 1.4rem; font-weight: 600; }
h3 { font-size: 1.1rem; font-weight: 600; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1.4rem !important;
    font-weight: 600 !important;
    font-family: 'Inter', 'Noto Sans Tamil', sans-serif !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 12px rgba(59,130,246,0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(59,130,246,0.5) !important;
}

/* Inputs */
.stTextArea textarea, .stTextInput input, .stSelectbox select {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-accent) !important;
    color: var(--text-primary) !important;
    border-radius: 10px !important;
    font-family: 'Inter', 'Noto Sans Tamil', sans-serif !important;
}

/* Metric cards */
.kural-metric {
    background: var(--bg-card);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius-lg);
    padding: 1.2rem 1.4rem;
    text-align: center;
    transition: all 0.2s ease;
}
.kural-metric:hover { background: var(--bg-card-hover); border-color: var(--accent-blue); }
.kural-metric-value { font-size: 2.2rem; font-weight: 700; font-family: 'Space Grotesk', 'Noto Sans Tamil', sans-serif; }
.kural-metric-label { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.3rem; }

/* Status badges */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Complaint cards */
.complaint-card {
    background: var(--bg-card);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius-lg);
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}
.complaint-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
}
.complaint-card.escalated::before { background: var(--accent-red); }
.complaint-card.filed::before { background: var(--accent-blue); }
.complaint-card.in_progress::before { background: var(--accent-orange); }
.complaint-card.resolved::before { background: var(--accent-green); }
.complaint-card:hover { border-color: var(--accent-blue); box-shadow: var(--shadow); }

/* Timeline */
.timeline-event {
    display: flex;
    gap: 1rem;
    padding: 0.8rem 0;
    border-bottom: 1px solid var(--border);
}
.timeline-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-top: 0.4rem;
    flex-shrink: 0;
}
.timeline-dot.escalated { background: var(--accent-red); box-shadow: 0 0 8px var(--accent-red); }
.timeline-dot.resolved { background: var(--accent-green); }
.timeline-dot.filed { background: var(--accent-blue); }
.timeline-dot.notification { background: #818cf8; }

/* Hero banner */
.kural-hero {
    background: linear-gradient(135deg, #0f1f3d 0%, #1a0a2e 50%, #0d1f0d 100%);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius-xl);
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.kural-hero::after {
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%);
    pointer-events: none;
}
.kural-hero h1 { font-size: 2.2rem; margin: 0; }
.kural-hero p { color: var(--text-secondary); margin: 0.5rem 0 0; font-size: 0.95rem; }

/* Section headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-family: 'Space Grotesk', 'Noto Sans Tamil', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}

/* Alerts */
.kural-alert {
    padding: 0.9rem 1.2rem;
    border-radius: var(--radius);
    margin: 0.5rem 0;
    font-size: 0.9rem;
}
.kural-alert.success { background: #052e1a; border: 1px solid #10b981; color: #6ee7b7; }
.kural-alert.error { background: #2e0505; border: 1px solid #ef4444; color: #fca5a5; }
.kural-alert.warning { background: #2e1a05; border: 1px solid #f59e0b; color: #fcd34d; }
.kural-alert.info { background: #05162e; border: 1px solid #3b82f6; color: #93c5fd; }

/* Dividers */
hr { border-color: var(--border) !important; }

/* Streamlit expander */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}

/* Hide Streamlit footer/branding */
footer { display: none !important; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict = None) -> Optional[dict]:
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Backend not running. Start it with: `uvicorn backend.main:app --reload`")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, data: dict = None, files: dict = None) -> Optional[dict]:
    try:
        if files:
            r = requests.post(f"{BACKEND_URL}{path}", files=files, timeout=60)
        else:
            r = requests.post(f"{BACKEND_URL}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Backend not running. Start it with: `uvicorn backend.main:app --reload`")
        return None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(f"API error: {detail}")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Status badge HTML
# ---------------------------------------------------------------------------

def status_badge(status: str) -> str:
    emoji, color, bg = STATUS_META.get(status, ("❓", "#94a3b8", "#1a1a1a"))
    return (
        f'<span class="status-badge" style="background:{bg}; color:{color}; '
        f'border: 1px solid {color}40;">{emoji} {status.replace("_"," ").upper()}</span>'
    )


def urgency_badge(urgency: str) -> str:
    icon, label = URGENCY_META.get(urgency, ("⚪", urgency.upper()))
    colors = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
    c = colors.get(urgency, "#94a3b8")
    return (
        f'<span class="status-badge" style="background:{c}18; color:{c}; '
        f'border: 1px solid {c}40;">{icon} {label}</span>'
    )


def officer_placeholder(department: str) -> str:
    """Display-layer only. No backend schema change: KURAL doesn't track a real
    assigned-officer roster, so this generates a stable, department-scoped
    placeholder instead of leaving the UI blank/"Pending" for every complaint."""
    dept = (department or "").strip()
    if not dept:
        return "Duty Officer"
    return f"Assigned: {dept} Duty Officer"


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 1.5rem;">
        <div style="font-size:2.5rem;">🗣️</div>
        <div style="font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.4rem; color:#f1f5f9;">KURAL</div>
        <div style="color:#64748b; font-size:0.8rem; margin-top:0.2rem;">AI Civic Grievance Agent</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        ["🏠 Dashboard", "📢 File Complaint", "🔍 Complaint Detail", "🎮 Demo Controls"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Quick stats in sidebar
    data = api_get("/complaints", params={"limit": 1})
    if data:
        total = data.get("total", 0)
        escalated_data = api_get("/complaints", params={"status": "escalated", "limit": 1})
        escalated_count = escalated_data.get("total", 0) if escalated_data else 0

        st.markdown(f"""
        <div style="padding:0.5rem;">
            <div style="color:#64748b; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.5rem;">LIVE STATS</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;">
                <span style="color:#94a3b8;">Total Complaints</span>
                <span style="font-weight:700; color:#3b82f6;">{total}</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#94a3b8;">🚨 Escalated</span>
                <span style="font-weight:700; color:#ef4444;">{escalated_count}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="color:#475569; font-size:0.75rem; text-align:center;">
        Built for AI for Bharat Hackathon 2026<br>
        Track: Smart Civic Infrastructure
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------

if page == "🏠 Dashboard":
    st.markdown("""
    <div class="kural-hero">
        <h1>🗣️ KURAL Dashboard</h1>
        <p>Real-time civic complaint tracker for Chennai — Tamil · Tanglish · English</p>
    </div>
    """, unsafe_allow_html=True)

    # Metrics row
    all_data = api_get("/complaints", params={"limit": 200})
    if all_data:
        complaints = all_data.get("complaints", [])
        total = all_data.get("total", 0)

        status_counts = {}
        for c in complaints:
            s = c.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        filed = status_counts.get("filed", 0)
        in_progress = status_counts.get("in_progress", 0)
        escalated = status_counts.get("escalated", 0)
        resolved = status_counts.get("resolved", 0)

        col1, col2, col3, col4, col5 = st.columns(5)
        metrics = [
            (col1, str(total), "Total", "#3b82f6"),
            (col2, str(filed), "Filed", "#4A90D9"),
            (col3, str(in_progress), "In Progress", "#f59e0b"),
            (col4, str(escalated), "🚨 Escalated", "#ef4444"),
            (col5, str(resolved), "Resolved", "#10b981"),
        ]
        for col, val, label, color in metrics:
            with col:
                st.markdown(f"""
                <div class="kural-metric">
                    <div class="kural-metric-value" style="color:{color};">{val}</div>
                    <div class="kural-metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Status filter
        col_filter, col_refresh = st.columns([3, 1])
        with col_filter:
            status_filter = st.selectbox(
                "Filter by status",
                ["All", "filed", "in_progress", "escalated", "resolved"],
                label_visibility="visible",
            )
        with col_refresh:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Refresh", key="dashboard_refresh"):
                st.rerun()

        # Filter complaints
        filtered = complaints if status_filter == "All" else [
            c for c in complaints if c.get("status") == status_filter
        ]

        st.markdown(f"""
        <div class="section-header">
            📋 Complaints {f'({status_filter})' if status_filter != 'All' else '(All)'}
            <span style="color:#64748b; font-size:0.8rem; margin-left:auto;">{len(filtered)} shown</span>
        </div>
        """, unsafe_allow_html=True)

        if not filtered:
            st.markdown("""
            <div class="kural-alert info">
                No complaints yet. Go to <strong>📢 File Complaint</strong> to submit one.
            </div>
            """, unsafe_allow_html=True)
        else:
            for c in filtered:
                status = c.get("status", "unknown")
                category = c.get("category", "")
                cat_icon = CATEGORY_ICONS.get(category, "📌")
                urgency = c.get("urgency", "")
                esc_count = c.get("escalation_count", 0)
                filed_at = c.get("filed_at", "")[:16].replace("T", " ")
                sla = c.get("sla_deadline", "")[:16].replace("T", " ")

                esc_badge = (
                    f'<span style="color:#ef4444; font-size:0.8rem; font-weight:600;">'
                    f'⚠️ ESC x{esc_count}</span>'
                ) if esc_count > 0 else ""

                # NOTE: rendered as a single-line HTML string (not a multi-line f-string).
                # Streamlit's markdown renderer treats indented multi-line HTML blocks
                # inconsistently — deeply nested divs with source-level indentation were
                # observed live to fall back to a literal/escaped code block for the
                # trailing lines. A single line sidesteps that raw-HTML-block ambiguity.
                card_html = (
                    f'<div class="complaint-card {status}">'
                    f'<div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.5rem;">'
                    f'<div>'
                    f'<div style="font-weight:600; font-size:1rem; margin-bottom:0.3rem;">{cat_icon} {c.get("summary", "No summary")[:80]}</div>'
                    f'<div style="color:#64748b; font-size:0.8rem; display:flex; gap:1rem; flex-wrap:wrap;">'
                    f'<span>📍 {c.get("ward","")}</span>'
                    f'<span>🏢 {c.get("department","")}</span>'
                    f'<span>📅 {filed_at}</span>'
                    f'<span>⏱ SLA: {sla}</span>'
                    f'</div>'
                    f'</div>'
                    f'<div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.3rem;">'
                    f'{status_badge(status)}{urgency_badge(urgency)}{esc_badge}'
                    f'</div>'
                    f'</div>'
                    f'<div style="color:#475569; font-size:0.75rem; margin-top:0.5rem; font-family:monospace;">🎫 {c.get("ticket_id") or c.get("id","")[:12]+"…"}</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="kural-alert error">
            Cannot connect to KURAL backend. Make sure it's running on port 8000.
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page: File Complaint
# ---------------------------------------------------------------------------

elif page == "📢 File Complaint":
    st.markdown("## 📢 File a Complaint")
    st.markdown('<p style="color:#94a3b8;">Upload audio or type your complaint in Tamil, Tanglish, or English.</p>', unsafe_allow_html=True)

    tab_audio, tab_text = st.tabs(["🎙️ Voice Upload", "✏️ Text Input"])

    with tab_audio:
        st.markdown("""
        <div class="kural-alert info">
            Upload an audio file (.wav, .mp3, .m4a, .webm) of your complaint in Tamil, Tanglish, or English.
            The AI will transcribe it and extract the details automatically.
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Choose audio file",
            type=["wav", "mp3", "m4a", "webm", "ogg"],
            key="audio_upload",
        )

        if uploaded_file:
            st.audio(uploaded_file)
            st.markdown(f"""
            <div style="color:#94a3b8; font-size:0.85rem; margin-top:0.3rem;">
                📁 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)
            </div>
            """, unsafe_allow_html=True)

            if st.button("🚀 Submit Voice Complaint", key="submit_voice"):
                with st.spinner("🔊 Transcribing with Whisper…"):
                    time.sleep(0.5)  # UX beat

                audio_bytes = uploaded_file.read()
                suffix = Path(uploaded_file.name).suffix or ".wav"

                with st.spinner("🧠 Extracting complaint details with Claude…"):
                    result = api_post(
                        "/complaint/voice",
                        files={"audio": (uploaded_file.name, audio_bytes, uploaded_file.type or "audio/wav")},
                    )

                if result:
                    c = result.get("complaint", {})
                    transcript = result.get("transcript", "")
                    st.markdown(f"""
                    <div class="kural-alert success">
                        ✅ <strong>Complaint filed!</strong> Ticket ID: <strong>{c.get('ticket_id','')}</strong>
                    </div>
                    """, unsafe_allow_html=True)

                    if result.get("ward_matched") is False:
                        st.markdown(f"""
                        <div class="kural-alert warning">
                            ⚠️ <strong>Ward could not be confidently identified</strong> from the transcript —
                            defaulted to <strong>{c.get('ward','')}</strong>. Please verify the location manually
                            before this complaint reaches the department.
                        </div>
                        """, unsafe_allow_html=True)

                    dup = result.get("duplicate") or {}
                    if dup.get("is_duplicate"):
                        st.markdown(f"""
                        <div class="kural-alert info">
                            📌 <strong>{dup.get('duplicate_count', 1)} citizen(s)</strong> have now reported this same issue nearby —
                            linked as a duplicate of complaint <strong>{dup.get('original_ticket_id') or dup.get('original_complaint_id') or ''}</strong>
                            instead of opening a separate ticket.
                        </div>
                        """, unsafe_allow_html=True)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**📝 Transcript:**")
                        st.markdown(f'<div style="background:#1a2035; padding:0.8rem; border-radius:8px; color:#94a3b8; font-size:0.9rem;">{transcript}</div>', unsafe_allow_html=True)
                    with col_b:
                        st.markdown("**📊 Extracted Details:**")
                        st.markdown(f"""
                        <div style="background:#1a2035; padding:0.8rem; border-radius:8px; font-size:0.9rem;">
                            <div style="margin-bottom:0.3rem;">🏷️ <strong>Category:</strong> {CATEGORY_ICONS.get(c.get('category',''),'📌')} {c.get('category','').upper()}</div>
                            <div style="margin-bottom:0.3rem;">📍 <strong>Ward:</strong> {c.get('ward','')}</div>
                            <div style="margin-bottom:0.3rem;">🏢 <strong>Department:</strong> {c.get('department','')}</div>
                            <div style="margin-bottom:0.3rem;">{urgency_badge(c.get('urgency',''))}</div>
                            <div style="margin-bottom:0.3rem; color:#94a3b8; font-size:0.8rem; font-style:italic;">{c.get('urgency_reason','')}</div>
                            <div>📝 {c.get('summary','')}</div>
                        </div>
                        """, unsafe_allow_html=True)

    with tab_text:
        st.markdown("""
        <div class="kural-alert info">
            Type your complaint below. You can write in Tamil, Tanglish (Tamil + English mix), or English.
            Example: <em>"Adyar area-la garbage collect pannala 3 days achu. Very bad smell coming."</em>
        </div>
        """, unsafe_allow_html=True)

        # Sample complaints
        #
        # NOTE: once a widget with a `key` has been instantiated, Streamlit's
        # widget state takes priority over the `value=` argument on reruns — writing
        # to a *different* session_state key (as this originally did via
        # "text_input") is silently ignored by the text_area. Live testing caught
        # this: the sample buttons visibly did nothing. The fix is to write
        # directly into the text_area's own widget key ("text_complaint_area").
        st.markdown("**Quick samples:**")
        sample_col1, sample_col2, sample_col3 = st.columns(3)
        with sample_col1:
            if st.button("🗑️ Garbage (Tamil)", key="sample1"):
                st.session_state["text_complaint_area"] = "Adyar area-la 3 naal aaga garbage collect pannala. ரொம்ப நாற்றமா இருக்கு. Please immediate action edungal."
        with sample_col2:
            if st.button("💧 Water (English)", key="sample2"):
                st.session_state["text_complaint_area"] = "No water supply in Velachery for the past 2 days. Pipe burst near Vijaya Nagar main road. People are suffering. High urgency please fix immediately."
        with sample_col3:
            if st.button("🛣️ Pothole (Tanglish)", key="sample3"):
                st.session_state["text_complaint_area"] = "T.Nagar Pondy Bazaar near signal-la oru periya pothole iruku. Yesterday bike accident achu. Road-a repair pannanum urgently."

        text_complaint = st.text_area(
            "Your complaint",
            height=120,
            placeholder="Type your complaint in Tamil, Tanglish, or English…",
            key="text_complaint_area",
        )

        if st.button("🚀 Submit Text Complaint", key="submit_text"):
            if not text_complaint or len(text_complaint.strip()) < 10:
                st.error("Please enter a complaint (at least 10 characters).")
            else:
                with st.spinner("🧠 Extracting complaint details with Claude…"):
                    result = api_post("/complaint/text", data={"text": text_complaint})

                if result:
                    c = result.get("complaint", {})
                    st.markdown(f"""
                    <div class="kural-alert success">
                        ✅ <strong>Complaint filed!</strong> Routed to <strong>{c.get('department','')}</strong>
                    </div>
                    """, unsafe_allow_html=True)

                    if result.get("ward_matched") is False:
                        st.markdown(f"""
                        <div class="kural-alert warning">
                            ⚠️ <strong>Ward could not be confidently identified</strong> from the complaint text —
                            defaulted to <strong>{c.get('ward','')}</strong>. Please verify the location manually
                            before this complaint reaches the department.
                        </div>
                        """, unsafe_allow_html=True)

                    dup = result.get("duplicate") or {}
                    if dup.get("is_duplicate"):
                        st.markdown(f"""
                        <div class="kural-alert info">
                            📌 <strong>{dup.get('duplicate_count', 1)} citizen(s)</strong> have now reported this same issue nearby —
                            linked as a duplicate of complaint <strong>{dup.get('original_ticket_id') or dup.get('original_complaint_id') or ''}</strong>
                            instead of opening a separate ticket.
                        </div>
                        """, unsafe_allow_html=True)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**📊 Complaint Details:**")
                        st.json({
                            "ticket_id": c.get("ticket_id",""),
                            "category": c.get("category",""),
                            "ward": c.get("ward",""),
                            "department": c.get("department",""),
                            "urgency": c.get("urgency",""),
                            "urgency_reason": c.get("urgency_reason",""),
                            "status": c.get("status",""),
                        })
                    with col_b:
                        st.markdown("**📝 Summary:**")
                        st.markdown(f'<div style="background:#1a2035; padding:0.8rem; border-radius:8px; color:#94a3b8;">{c.get("summary","")}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page: Complaint Detail
# ---------------------------------------------------------------------------

elif page == "🔍 Complaint Detail":
    st.markdown("## 🔍 Complaint Detail & Escalation Trail")

    # Load all complaints for selector
    all_data = api_get("/complaints", params={"limit": 100})

    if all_data and all_data.get("complaints"):
        complaints = all_data["complaints"]
        options = {
            f"{c.get('ticket_id') or c.get('id','')[:8]+'…'} | {CATEGORY_ICONS.get(c.get('category',''),'📌')} {c.get('category','')} | {c.get('ward','')} | {c.get('status','').upper()}": c.get("id","")
            for c in complaints
        }
        selected_label = st.selectbox("Select a complaint", list(options.keys()))
        selected_id = options[selected_label]

        detail = api_get(f"/complaints/{selected_id}")
        if detail:
            c = detail.get("complaint", {})
            trail = detail.get("escalation_trail", [])

            # Header
            status = c.get("status","")
            emoji, color, bg = STATUS_META.get(status, ("❓", "#94a3b8", "#1a1a1a"))
            # Single-line HTML (see note on the complaint-card block above) to avoid
            # Streamlit's markdown renderer mis-parsing deeply nested, indented HTML.
            header_html = (
                f'<div style="background:{bg}; border: 1px solid {color}40; border-radius:12px; padding:1.2rem 1.5rem; margin-bottom:1rem;">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">'
                f'<div>'
                f'<div style="font-size:1.2rem; font-weight:700; margin-bottom:0.3rem;">{CATEGORY_ICONS.get(c.get("category",""),"📌")} {c.get("summary","")}</div>'
                f'<div style="color:#94a3b8; font-size:0.85rem;">🎫 {c.get("ticket_id","")} &nbsp;|&nbsp; 📍 {c.get("ward","")} &nbsp;|&nbsp; 🏢 {c.get("department","")}</div>'
                f'</div>'
                f'<div>{status_badge(status)}</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(header_html, unsafe_allow_html=True)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Category", f"{CATEGORY_ICONS.get(c.get('category',''),'📌')} {c.get('category','').title()}")
            col2.metric("Urgency", c.get("urgency","").upper())
            col3.metric("Escalations", c.get("escalation_count", 0))
            col4.metric("SLA Deadline", c.get("sla_deadline","")[:16].replace("T"," "))
            col5.metric("Officer", officer_placeholder(c.get("department","")))

            # B3: Claude's one-sentence urgency rationale, right under the badges.
            if c.get("urgency_reason"):
                st.caption(f"🧠 **Why this urgency?** {c.get('urgency_reason')}")

            # B1: duplicate detection banners
            duplicate_count = c.get("duplicate_count", 0)
            duplicate_of = c.get("duplicate_of")
            if duplicate_count:
                st.markdown(f"""
                <div class="kural-alert info">
                    👥 <strong>{duplicate_count} other citizen(s)</strong> have reported this exact same issue
                    (same category + ward, filed within 24h) — they were linked here instead of opening separate tickets.
                </div>
                """, unsafe_allow_html=True)
            if duplicate_of:
                # Best-effort lookup of the original's citizen-facing ticket_id for
                # display; silently falls back to the raw internal id if it fails
                # (e.g. backend hiccup) rather than spamming an error here.
                original_ticket = duplicate_of
                try:
                    orig_resp = requests.get(f"{BACKEND_URL}/complaints/{duplicate_of}", timeout=5)
                    if orig_resp.ok:
                        original_ticket = orig_resp.json().get("complaint", {}).get("ticket_id") or duplicate_of
                except Exception:
                    pass
                st.markdown(f"""
                <div class="kural-alert info">
                    🔗 This complaint appears to be a duplicate of complaint <strong>{original_ticket}</strong>.
                </div>
                """, unsafe_allow_html=True)

            # Escalation trail
            st.markdown(f"""
            <div class="section-header" style="margin-top:1.5rem;">
                ⏱️ Escalation Trail
                <span style="color:#64748b; font-size:0.8rem; margin-left:auto;">{len(trail)} events</span>
            </div>
            """, unsafe_allow_html=True)

            if not trail:
                st.markdown("""
                <div class="kural-alert info">
                    No escalation events yet. Use <strong>🎮 Demo Controls</strong> to simulate SLA breach.
                </div>
                """, unsafe_allow_html=True)
            else:
                for event in trail:
                    ev_status = event.get("new_status","")
                    reason = event.get("reason","")
                    # B2: simulated notification entries share the same table (no
                    # schema change) but are marked via previous_status==new_status
                    # plus this text prefix — render distinctly, not as another
                    # escalated/resolved milestone.
                    is_notification = NOTIFICATION_LOG_MARKER in reason
                    if is_notification:
                        dot_class = "notification"
                        label_html = (
                            '<span style="background:#312e81; color:#a5b4fc; padding:0.15rem 0.6rem; '
                            'border-radius:10px; font-size:0.75rem; font-weight:700;">📱 SIMULATED SMS</span>'
                        )
                        reason_display = reason.replace(NOTIFICATION_LOG_MARKER, "").strip()
                    else:
                        dot_class = ev_status if ev_status in ("escalated","resolved","filed") else "filed"
                        label_html = status_badge(ev_status)
                        reason_display = reason

                    audit = event.get("llm_audit_result","")
                    audit_html = (
                        f'<span style="background:#052e1a; color:#10b981; padding:0.15rem 0.5rem; '
                        f'border-radius:10px; font-size:0.75rem; margin-left:0.5rem;">LLM: {audit}</span>'
                    ) if audit else ""

                    # Single-line HTML (see note on the complaint-card block above) to avoid
                    # Streamlit's markdown renderer mis-parsing deeply nested, indented HTML —
                    # this is the escalation timeline, the most visually important live element.
                    event_html = (
                        f'<div class="timeline-event">'
                        f'<div>'
                        f'<div class="timeline-dot {dot_class}" style="margin-top:6px;"></div>'
                        f'<div style="width:2px; background:#1e293b; flex:1; margin:0.3rem auto 0; min-height:20px;"></div>'
                        f'</div>'
                        f'<div style="flex:1;">'
                        f'<div style="font-size:0.85rem; color:#94a3b8; margin-bottom:0.2rem;">'
                        f'{event.get("triggered_at","")[:16].replace("T"," ")} UTC {label_html} {audit_html}'
                        f'</div>'
                        f'<div style="font-size:0.9rem; color:#cbd5e1;">{reason_display}</div>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(event_html, unsafe_allow_html=True)

            # Resolution form
            if status not in ("resolved", "closed"):
                st.markdown("""
                <div class="section-header" style="margin-top:1.5rem;">
                    ✅ Submit Resolution
                </div>
                """, unsafe_allow_html=True)
                st.markdown("""
                <div class="kural-alert warning">
                    The LLM will audit your resolution note for genuineness before closing the complaint.
                </div>
                """, unsafe_allow_html=True)

                res_note = st.text_area(
                    "Resolution note (describe what was actually done)",
                    height=100,
                    placeholder="e.g., 'Garbage collected on 19/07/2026. Area cleaned and disinfected by SWM team. Supervisor: R.Kumar.'",
                    key="resolution_note",
                )
                if st.button("✅ Submit Resolution", key="submit_resolution"):
                    if not res_note or len(res_note.strip()) < 10:
                        st.error("Please provide a detailed resolution note.")
                    else:
                        with st.spinner("🧠 LLM auditing resolution…"):
                            result = api_post(
                                f"/complaints/{selected_id}/resolve",
                                data={"note": res_note},
                            )
                        if result:
                            verdict = result.get("status","")
                            audit = result.get("audit", {})
                            if verdict == "resolved":
                                st.markdown(f"""
                                <div class="kural-alert success">
                                    ✅ <strong>Resolved!</strong> LLM audit: {audit.get('reasoning','')}
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class="kural-alert warning">
                                    ⚠️ <strong>Resolution flagged for review.</strong><br>
                                    LLM verdict: {audit.get('reasoning','')}<br>
                                    Recommended: {audit.get('recommended_action','')}
                                </div>
                                """, unsafe_allow_html=True)
                            st.rerun()
    else:
        st.markdown("""
        <div class="kural-alert info">
            No complaints filed yet. Go to <strong>📢 File Complaint</strong> to submit one.
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page: Demo Controls
# ---------------------------------------------------------------------------

elif page == "🎮 Demo Controls":
    st.markdown("## 🎮 Demo Controls")
    st.markdown("""
    <div class="kural-alert warning">
        ⚡ <strong>Judge Demo Mode.</strong> These controls let you demonstrate the escalation loop
        live without waiting hours for real SLA deadlines to pass.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Step-by-step demo guide
    st.markdown("""
    <div class="section-header">📋 Demo Script</div>
    """, unsafe_allow_html=True)

    st.markdown("""
    **Step 1:** File a complaint (go to 📢 File Complaint tab, use a sample text)

    **Step 2:** Come back here → click **"Simulate Time Passing"** (shifts SLA by 200h)

    **Step 3:** Click **"Trigger Escalation Check"** — watch it escalate in real time

    **Step 4:** Go to 🔍 Complaint Detail to see the escalation trail with timestamps

    **Step 5 (optional):** Submit a resolution note — Claude audits it live
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="section-header">⏩ Step 1: Simulate Time Passing</div>
        """, unsafe_allow_html=True)
        st.markdown('<p style="color:#94a3b8; font-size:0.9rem;">Shifts SLA deadlines backward, making active complaints appear overdue.</p>', unsafe_allow_html=True)

        hours_shift = st.number_input(
            "Hours to shift backward",
            min_value=1,
            max_value=10000,
            value=200,
            step=24,
            key="hours_shift",
        )

        # Optional specific complaint
        all_data = api_get("/complaints", params={"limit": 100})
        complaints = all_data.get("complaints", []) if all_data else []
        active = [c for c in complaints if c.get("status") not in ("resolved","closed")]

        target = "All active complaints"
        if active:
            options = ["All active complaints"] + [
                f"{c.get('id','')[:8]}… ({c.get('category','')}, {c.get('ward','')})"
                for c in active
            ]
            target = st.selectbox("Target", options, key="sim_target")

        if st.button("⏩ Simulate Time Passing", key="simulate_btn"):
            payload = {"hours": int(hours_shift)}
            if target != "All active complaints":
                cid = active[options.index(target) - 1].get("id","")
                payload["complaint_id"] = cid

            result = api_post("/demo/simulate-time", data=payload)
            if result:
                st.markdown(f"""
                <div class="kural-alert success">
                    ✅ {result.get('message','')}
                </div>
                """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="section-header">🚨 Step 2: Trigger Escalation Check</div>
        """, unsafe_allow_html=True)
        st.markdown('<p style="color:#94a3b8; font-size:0.9rem;">Runs the SLA poller immediately — escalates all overdue complaints right now.</p>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🚨 Trigger Escalation Check NOW", key="escalate_btn"):
            result = api_post("/demo/trigger-escalation")
            if result:
                escalated_ids = result.get("escalated", [])
                count = result.get("count", 0)
                if count > 0:
                    st.markdown(f"""
                    <div class="kural-alert error">
                        🚨 <strong>{count} complaint(s) ESCALATED!</strong><br>
                        {"<br>".join([f"• {eid[:12]}…" for eid in escalated_ids])}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="kural-alert info">
                        {result.get('message','')}
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")

    # Live complaint status table for demo
    st.markdown("""
    <div class="section-header">📊 Live Complaint Status (auto-view)</div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Refresh Status", key="demo_refresh"):
        st.rerun()

    if complaints:
        for c in complaints[:10]:  # show top 10
            status = c.get("status","")
            emoji, color, bg = STATUS_META.get(status, ("❓","#94a3b8","#1a1a1a"))
            esc = c.get("escalation_count",0)
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                        background:{bg}; border:1px solid {color}30; border-radius:8px;
                        padding:0.6rem 1rem; margin-bottom:0.4rem; font-size:0.88rem;">
                <span style="color:#94a3b8;">{c.get('id','')[:8]}…</span>
                <span>{CATEGORY_ICONS.get(c.get('category',''),'📌')} {c.get('category','').title()}</span>
                <span style="color:#94a3b8;">📍 {c.get('ward','')[:20]}</span>
                {status_badge(status)}
                <span style="color:#ef4444; font-weight:600;">{'⚠️ x'+str(esc) if esc > 0 else ''}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="kural-alert info">No complaints filed yet.</div>
        """, unsafe_allow_html=True)

    # Auto-refresh toggle
    auto_refresh = st.checkbox("⚡ Auto-refresh every 5s (for live demo)", key="auto_refresh")
    if auto_refresh:
        time.sleep(5)
        st.rerun()
