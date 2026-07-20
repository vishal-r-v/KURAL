# KURAL 🗣️ — AI Civic Grievance Agent

**AI for Bharat Hackathon 2026** | Track: Smart Public Transport & Civic Infrastructure

KURAL is a voice-first AI civic grievance agent for Indian citizens. It accepts complaints in **Tamil, Tanglish, and English**, routes them to the correct Chennai department, and autonomously audits resolutions — escalating when officers submit vague or insufficient resolution notes.

## 🎯 The Differentiator

**LLM-audited escalation loop** — not just rules-based SLA timers. Claude evaluates whether a resolution note describes a *genuine fix* before closing a complaint. This is visible, live, in the demo.

---

## 📌 Important Disclosure — What's Real vs. Simulated

**Everything in KURAL is real and live** — real Claude API calls for extraction and resolution auditing, real Whisper speech-to-text, a real SQLite database, a real APScheduler-driven SLA/escalation engine, and real Chennai ward/department/SLA data.

**The one deliberate exception:** there is no public write-API for any Chennai/Indian municipal grievance system (GCC, CPGRAMS, TANGEDCO, CMWSSB) — this was independently researched and confirmed. "Filing" a complaint into a government system is therefore simulated by writing to KURAL's own SQLite database, which acts as the system of record for this prototype. This is the **only** simplification in the entire project; nothing else is mocked or stubbed.

---

## 🏗️ Architecture

```
Citizen (React website — kural_web/, primary UI)
   → FastAPI backend (backend/main.py)
   → Whisper STT (Tamil-tuned, handles code-mixed speech)
   → Claude LLM extraction (function calling + Pydantic validation + retry loop)
   → Routing engine (real Chennai ward/department seed data, 38 localities)
   → APScheduler (deterministic SLA polling — LLM NEVER controls timing)
   → Escalation trigger → LLM audits resolution note (advisory only)
   → SQLite (system of record — complaints, escalation trail, ticket sequence)

Streamlit dashboard (frontend/app.py) reads the same live backend as an
internal admin/demo view alongside the React site — not a separate pipeline.
```

**Two frontends, one backend:**
- **`kural_web/`** (React + TypeScript + Vite) — the primary citizen-facing website: file a complaint (voice or text), track by ticket ID, complaint detail with escalation timeline, public dashboard with a real Leaflet/OpenStreetMap ward-coverage map, a filterable complaint history table, and a **prototype-only** citizen login (Aadhaar + password stored in the browser — not linked to UIDAI). Bilingual (English/Tamil, with self-hosted Noto Sans Tamil for correct glyph rendering).
- **`frontend/app.py`** (Streamlit) — internal admin/demo dashboard against the same live API, used for quick backend verification and live demo controls (simulate time, trigger escalation).

**Critical design boundary:** The LLM is restricted to two narrow roles:
1. **Intake extraction** — parse complaint from transcript
2. **Resolution audit** — evaluate whether an officer's resolution is genuine

All state transitions, SLA deadlines, and escalation triggers are deterministic (APScheduler). This hybrid pattern prevents the fragility and unpredictability of LLM-controlled workflows.

---

## 📋 Setup

### Prerequisites
- Python 3.10+
- `ffmpeg` installed system-wide (required by Whisper)
- An Anthropic API key

**Install ffmpeg (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

**Install ffmpeg (macOS):**
```bash
brew install ffmpeg
```

### 1. Clone and install
```bash
git clone <repo-url>
cd KURAL

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here
```

### 3. Run the backend
```bash
uvicorn backend.main:app --reload --port 8000
```
The API is now at http://localhost:8000. Docs at http://localhost:8000/docs.

### 4. Run the admin dashboard (Streamlit)
```bash
streamlit run frontend/app.py
```
Dashboard at http://localhost:8501.

### 5. Run the citizen website (React)
```bash
cd kural_web
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```
Website at http://localhost:3000. The backend URL is configurable via `kural_web/.env` → `VITE_API_BASE_URL` (defaults to `http://localhost:8000`, no hardcoded URLs in the source).

### 6. (Optional) Pre-seed realistic demo data
```bash
python -m backend.seed_demo_data          # inserts ~18 synthetic complaints, skips if already seeded
python -m backend.seed_demo_data --wipe   # wipes existing complaints first, then reseeds
```
Clearly marked as synthetic demo data (`[DEMO SEED DATA — synthetic, not a real citizen report]` in every seeded transcript) — makes the Public Dashboard and ward map tell a real story before any live complaint is filed in the session.

---

## 🎮 Demo: Live Escalation Loop

This demonstrates the core novelty — watch a complaint get escalated in real time:

**Option A — Via Streamlit UI:**
1. Go to **📢 File Complaint** → use a sample text complaint
2. Go to **🎮 Demo Controls** → click **"⏩ Simulate Time Passing"** (200h)
3. Click **"🚨 Trigger Escalation Check NOW"**
4. Go to **🔍 Complaint Detail** → see the escalation trail

**Option B — Via API (curl):**
```bash
# 1. File a text complaint
curl -X POST http://localhost:8000/complaint/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Adyar area garbage not collected for 3 days. Very bad smell."}'

# Note the complaint ID from the response

# 2. Simulate time passing (shifts SLA 200h backward)
curl -X POST http://localhost:8000/demo/simulate-time \
  -H "Content-Type: application/json" \
  -d '{"hours": 200}'

# 3. Trigger escalation check
curl -X POST http://localhost:8000/demo/trigger-escalation

# 4. Check complaint status
curl http://localhost:8000/complaints/<COMPLAINT_ID>
```

**Option C — Submit a voice complaint:**
```bash
curl -X POST http://localhost:8000/complaint/voice \
  -F "audio=@sample_audio/garbage_adyar.wav"
```

---

## 🧪 Run Tests

```bash
pytest tests/ -v
```

Expected output: all tests pass (routing, DB, extraction mock, escalation engine).

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/complaint/voice` | Upload audio → full pipeline |
| POST | `/complaint/text` | Text complaint (demo fallback) |
| GET | `/complaints` | List all complaints (filter by status) |
| GET | `/complaints/{id}` | Complaint + escalation trail — `{id}` accepts either the citizen-facing `ticket_id` (e.g. `GCC/SWM/2026/00012`) or the internal UUID |
| POST | `/complaints/{id}/resolve` | Submit resolution note (triggers LLM audit; rejected resolutions are re-escalated, not just logged) |
| POST | `/demo/simulate-time` | Shift SLA deadlines backward |
| POST | `/demo/trigger-escalation` | Fire SLA check immediately |
| GET | `/meta/wards` | All 38 Chennai ward names, plus `ward_details` (name + approximate lat/lng, used by the React ward map) |
| GET | `/meta/sla` | SLA hours by category |

Full interactive docs: http://localhost:8000/docs

**Ticket IDs:** every complaint gets a structured, citizen-friendly `ticket_id` — `GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE}` (e.g. `GCC/SWM/2026/00012`), generated from a per-department, per-year sequence counter. The internal UUID `id` still exists unchanged for backward-compatible API routing; `ticket_id` is what citizens see and search by.

---

## 🗂️ Project Structure

```
kural/
├── backend/
│   ├── main.py            # FastAPI routes
│   ├── models.py          # Pydantic schemas
│   ├── db.py              # SQLite async CRUD, migrations, ticket_id generation
│   ├── stt.py             # Whisper transcription
│   ├── extraction.py      # Claude function-calling + retry loop
│   ├── routing.py         # Ward/department routing, fuzzy matching
│   ├── escalation.py      # APScheduler + LLM audit
│   ├── seed_data.json     # Real Chennai ward/dept data (38 localities, lat/lng)
│   ├── seed_demo_data.py  # One-time synthetic demo-data seed script
│   └── config.py          # Env var loading
├── frontend/
│   └── app.py             # Streamlit admin/demo dashboard
├── kural_web/              # React + TypeScript + Vite citizen website (primary UI)
│   ├── src/
│   │   ├── components/     # HomeView, FileComplaintView, TrackComplaintView,
│   │   │                   # DashboardView, HistoryView, WardMap, AboutView…
│   │   └── lib/            # api.ts (fetch abstraction), adapters.ts, types.ts
│   └── public/fonts/       # Self-hosted Noto Sans Tamil (offline-safe glyph coverage)
├── tests/
│   └── test_pipeline.py   # End-to-end tests
├── sample_audio/           # Test audio clips
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚠️ Known Limitations

1. **Whisper Tamil accuracy**: The `base` model has moderate accuracy for Tamil. Using `small` or `medium` (set `WHISPER_MODEL=small` in `.env`) improves accuracy but is slower.
2. **Simulated government filing** (see disclosure at the top of this README): department *routing* is real Chennai data, but there is no public write-API to actually file into GCC/CPGRAMS/TANGEDCO/CMWSSB, so filing writes to KURAL's own DB.
3. **Prototype citizen login**: the Aadhaar login in the React navbar is demo-only (localStorage). It is **not** connected to UIDAI or any government identity system.
4. **Single-user prototype**: No real auth/multi-tenancy. Designed for demo purposes.
5. **SQLite concurrency**: Fine for demo; would need PostgreSQL for production.
6. **ffmpeg required**: Whisper needs ffmpeg installed on the system.

---

## 🏆 Judging Criteria Alignment

| Criterion | Implementation |
|-----------|---------------|
| Innovation (25%) | LLM-audited escalation loop — evaluates resolution genuineness, not just SLA timer |
| Technical Implementation (25%) | Full async pipeline: Whisper → Claude function-calling → APScheduler → SQLite |
| Feasibility/Scalability (20%) | Hybrid deterministic+LLM architecture; SQLite → PostgreSQL upgrade path |
| UI/UX (15%) | React citizen website (bilingual, Tamil-font-correct, live ward map, complaint history) + Streamlit admin dashboard |
| Social Impact (15%) | Designed for Tamil-speaking Chennai citizens; real ward/department data |

---

## 👤 Author

KURAL — AI for Bharat Hackathon 2026 | Individual submission
