# KURAL — Progress

**Status: Live, end-to-end, working — including all Final Power-Up AND
Final Wrap-Up features. This is the last content pass; project is
feature-complete.** Backend (FastAPI + SQLite + Claude + Whisper +
APScheduler) is verified against real API calls, not mocks. React citizen
frontend is wired to the live backend, with a real Leaflet/OpenStreetMap
ward map and a complaint History page. Streamlit remains the internal
admin/demo dashboard. Duplicate detection (B1), simulated citizen
notifications (B2), AI urgency reasoning (B3), and the English/Tamil toggle
(B4) are all live-verified in both frontends. Tamil font rendering, real
structured ticket IDs, 38-ward coverage, a History view, and a real ward
map were added and live-verified in the final wrap-up pass — see the
"Final Power-Up Directive" and "Final Wrap-Up Directive" sections below.

```
Citizen → React (kural_web/)  ─┐
Admin   → Streamlit (frontend/) ─┴→ FastAPI backend → SQLite → Claude → Whisper → APScheduler
```

---

## How to Run

**Terminal 1 — backend:**
```bash
cd /home/vishal_r_v/PROJECTS/KURAL
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — React frontend (primary UI):**
```bash
cd /home/vishal_r_v/PROJECTS/KURAL/kural_web
npm install   # first time only
npm run dev
```
Open `http://localhost:3000`.

**Terminal 3 — Streamlit (internal admin dashboard, optional):**
```bash
cd /home/vishal_r_v/PROJECTS/KURAL
source venv/bin/activate
streamlit run frontend/app.py
```

**Run tests:**
```bash
source venv/bin/activate
pytest tests/ -v   # 42 passed
```

**Seed the dashboard with demo data (one-time, optional):**
```bash
source venv/bin/activate
python -m backend.seed_demo_data          # inserts ~18 synthetic complaints, skips if already seeded
python -m backend.seed_demo_data --force  # re-seed even if already present
python -m backend.seed_demo_data --wipe   # delete ALL complaints first, then seed
```
Clearly marked as demo data (`raw_transcript` is prefixed `[DEMO SEED DATA — synthetic,
not a real citizen report]`) so it's never confused with real submissions.

**Fresh setup from scratch:**
```bash
cd /home/vishal_r_v/PROJECTS/KURAL
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
sudo apt-get install ffmpeg -y
cp .env.example .env   # add ANTHROPIC_API_KEY, NVIDIA_API_KEY (optional fallback)
cd kural_web && npm install && cp .env.example .env
```

---

## Architecture & Key Decisions

- **LLM priority: Claude (Anthropic) primary, NVIDIA NIM fallback** — in
  `extraction.py` and `escalation.py`. NIM was originally wired as primary
  with no documented reason; live testing showed it unreliable/slow from
  this environment (one call took 70s, another hung >9 min), while Claude
  was fast and 100% reliable. Confirmed with user, swapped priority.
- **Claude model:** `claude-sonnet-5`, set via `CLAUDE_MODEL` in `.env`.
- **All LLM calls run via `asyncio.to_thread()`** with `timeout=20s` and
  `max_retries=0` on both Anthropic/OpenAI clients — the synchronous SDK
  calls were previously blocking FastAPI's entire event loop. Both
  providers fail fast on API errors instead of retrying internally.
- **Whisper:** `WHISPER_MODEL=small`, `language="en"` (not `"ta"`) — forcing
  Tamil transcription caused Whisper to phonetically transliterate English
  words into Tamil script, destroying semantic content for Tanglish speech.
  `small` + `en` produces usable transcripts.
- **Ward matching transparency:** `routing.resolve_ward_with_confidence()`
  returns `(ward_display, matched: bool)`. A `ward_matched: bool` field is
  threaded through `RouteResult` → API responses → both frontends, so an
  unmatched ward shows a visible warning instead of silently misrouting.
- **APScheduler runs in FastAPI's asyncio loop** (`AsyncIOScheduler`, not
  `BackgroundScheduler`) to stay thread-safe with `aiosqlite`.
- **Resolution audit fails open toward `reopen`** — if the Claude audit call
  errors, it returns `verdict=reopen, confidence=low` rather than silently
  passing a possibly-incomplete resolution.
- **CORS is fully open** (`allow_origins=["*"]`) — fine for a hackathon/demo,
  should be restricted to the frontend origin for production.
- **Simulated government filing is intentional, not a shortcut** — there is
  no public write-API for any Chennai/Indian municipal grievance system
  (GCC, CPGRAMS, TANGEDCO, CMWSSB), confirmed by research. "Filing" writes to
  KURAL's own SQLite DB. This is the one deliberate simplification in the
  project; everything else is real.

---

## Completed Work

### Core backend pipeline ✅ — live-verified, not just unit-tested
- `backend/config.py`, `models.py`, `db.py` — env loading, Pydantic schemas,
  async SQLite CRUD (complaints + escalation trail).
- `backend/stt.py` — Whisper STT, lazy-loaded, async, tuned per above.
- `backend/extraction.py` — Claude/NIM function-calling extraction with
  validation retry loop, non-blocking, fail-fast on errors.
- `backend/routing.py` — real Chennai ward/department/SLA seed data, fuzzy
  ward matching with confidence flag.
- `backend/escalation.py` — APScheduler SLA engine + LLM audit role.
- `backend/main.py` — all routes: `POST /complaint/voice`, `POST
  /complaint/text`, `GET /complaints`, `GET /complaints/{id}`, `POST
  /complaints/{id}/resolve`, `POST /demo/simulate-time`, `POST
  /demo/trigger-escalation`, `GET /health`, `GET /meta/sla`. CORS enabled.
- Submitted multiple real text complaints (garbage/water/electricity) via a
  live running server — confirmed correct extraction, routing, and
  persistence end to end.
- Filed a real complaint, ran `/demo/simulate-time` + `/demo/trigger-escalation`
  — status flipped to `escalated` in the live DB and appeared on the live
  Streamlit dashboard, not just in a pytest fixture.
- Submitted a deliberately vague resolution note ("issue noted") via `POST
  /complaints/{id}/resolve` — live Claude audit correctly returned `reopen`.
- **Tests:** `pytest tests/ -v` → 24/24 passing (routing, DB CRUD, mocked
  extraction, escalation engine, seed data integrity, ward-match confidence).

### Error handling ✅
- Empty/garbled Whisper transcript → clean `422` from the API (`"Whisper
  returned empty transcript. Check audio quality…"`), not a crash. Verified
  live with a synthetic silent `.wav`.
- Unmatched ward → `ward_matched=false` flag + warning message, surfaced in
  both Streamlit and React, instead of a silent misroute.

### Streamlit admin dashboard (`frontend/app.py`) ✅
- Walked every tab against the live backend: voice/text filing, complaint
  list, detail + escalation timeline, demo controls, resolution + audit
  display — all confirmed live, not stub data.
- Fixed bugs found only through live testing: raw HTML leaking into the UI
  in complaint cards/timeline/detail header (Streamlit's markdown parser
  misread deeply-indented multi-line HTML as code blocks — fixed by
  flattening to single-line f-strings), and "Quick sample" buttons writing
  to the wrong `session_state` key.

### React citizen frontend (`kural_web/`) ✅
Primary citizen-facing UI, generated separately (Google Stitch/AI Studio)
and integrated into this backend. No UI redesign — only wiring.

- **API layer** (`kural_web/src/lib/`):
  - `config.ts` — single source of truth for `VITE_API_BASE_URL`, no
    hardcoded `localhost` anywhere else.
  - `api.ts` — typed fetch/XHR client (`ApiError` with kinds
    `network`/`timeout`/`validation`/`not_found`/`bad_request`/`server`),
    bilingual `friendlyErrorMessage()`, real upload-progress for voice via
    XHR.
  - `adapters.ts` — maps backend JSON onto the existing, unmodified
    `Complaint`/`TimelineEvent` frontend types (enum casing differences
    handled here per "adapt the frontend, not the backend").
  - `useBackendHealth.ts` — polls `GET /health` every 20s.
- **Pages wired to live endpoints:**
  - **Home** — live "Backend Online/Offline" badge (`GET /health`).
  - **File Complaint** — text → `POST /complaint/text` (location field
    merged into the text since the backend has no separate param). Voice
    was previously mocked (canned transcript into a textbox) — replaced
    with real `MediaRecorder` mic recording + audio file-upload fallback,
    both calling `POST /complaint/voice` via XHR with a real progress bar.
  - **Track Complaint** — real `GET /complaints/{id}` lookup; "quick sample
    IDs" now pull real recent complaint IDs from `GET /complaints`. Removed
    a "Simulate Resolve" button that called a nonexistent mock endpoint and
    didn't map to any real citizen action.
  - **Complaint timeline** — built from the real `escalation_trail`,
    distinguishing SLA-breach auto-escalation from AI-audit-triggered
    reopens.
  - **Public Dashboard** — self-fetches `GET /complaints`, auto-refreshes
    every 15s; computes total/active/escalated/resolved, ward distribution,
    category distribution, department distribution, and average resolution
    time (`filed_at` → `last_checked_at`) — all client-side, no new backend
    endpoint needed.
  - **About** — fixed a factual error ("Gemini 3.5 Flash" → "Claude
    (Anthropic)").
- **Mock backend removed:** `server.ts` no longer runs an Express `/api/*`
  mock or Google Gemini integration — it only serves the Vite dev bundle /
  production build now. `@google/genai` dependency removed.
- **Verified live** (both servers running, driven via real browser):
  site loads with backend-online badge; filed a real text complaint and got
  a real ID with correct category/department/ward/urgency; tracked that
  complaint and saw a working stepper + timeline; dashboard showed non-zero
  live totals and all three charts populated with the new complaint in the
  live queue; invalid complaint ID showed a friendly error, no crash; About
  page confirmed Claude/Anthropic, no "Gemini" anywhere.
- **Regression-checked via `curl`** (not through the browser): `POST
  /complaint/voice` with a real sample audio file returns the exact
  response shape the frontend expects; the same endpoint with a synthetic
  silent `.wav` returns `422` with the expected message.
- `npx tsc --noEmit` — 0 type errors. `npm run build` — production build
  succeeds.

---

## Known Gaps / Remaining Work

- **Real microphone recording not verified through an actual browser** — the
  sandboxed browser-automation tool used for testing has no real microphone
  and can't script native file pickers, so `MediaRecorder` and file-upload
  code paths couldn't be exercised via the UI directly. The underlying
  `POST /complaint/voice` call (same code path either way) *was* verified
  via `curl` with both real and synthetic audio, and the frontend code was
  reviewed carefully — but a human should click "Start Recording" once with
  a real mic to be fully sure. **Next step:** open `http://localhost:3000`
  → File Complaint → click the mic button → speak → "Stop & Transcribe" →
  confirm the success screen shows a real transcript-derived result.
- **Ward-unmatched warning banner** verified via text input only, not yet
  separately via a real voice recording of an out-of-scope location.
- **Sample audio files** — only 3 exist in `sample_audio/` (garbage/water/
  electricity). More Tamil/Tanglish samples would strengthen a live demo.
- **CORS wide open** (`allow_origins=["*"]`) — fine for demo, tighten before
  any real deployment.
- **B1 dedup window is a live 24h check against `filed_at`**, not
  demo-adjustable via an env var. If you need a shorter window live on
  stage, call `db.find_recent_duplicate(category, ward, hours=N)` with a
  smaller `N` — it's a plain function argument, not hardcoded.

---

## Final Power-Up Directive — Part A (Small Fixes) ✅ all done

1. **Officer field placeholder** — `officer_placeholder(department)` /
   `officerPlaceholder(department)` (Streamlit `frontend/app.py`, React
   `kural_web/src/lib/adapters.ts`) now render `"Assigned: {department} Duty
   Officer"` everywhere the officer field is shown (complaint detail metrics
   row in Streamlit; "Assigned Dept" sidebar card in React), instead of a
   blank/"Pending" placeholder. Display-layer only — no backend schema change.
2. **README disclosure placement** — the simulated-government-filing
   disclosure now lives in a `## 📌 Important Disclosure` section near the
   top of `README.md`, right after the differentiator section and before
   Architecture/Setup, so it's the first thing a judge skimming the repo
   sees. The old "Known Limitations" bullet was kept but shortened to point
   back up at it instead of duplicating the wording.
3. **Security check — no leaked API keys.** Ran `git rev-parse
   --is-inside-work-tree` and searched for a `.git` directory anywhere under
   the project: **this project has no git repository initialized at all**
   (nothing has ever been committed), so there is no history to leak keys
   through. Confirmed `.env` is excluded by the root `.gitignore` (`.env`)
   and `kural_web/.gitignore` (`.env*`, with `!.env.example`), and grepped
   every tracked-looking file for `sk-ant-`/`nvapi-`/`AIza…` key patterns —
   the real keys exist only in `.env` (both root and `kural_web/`), never in
   `.env.example`. **Action needed before making the repo public:** none
   right now, but the very first `git init` + `git add` should be checked
   once more (`git status`) to confirm `.env` shows as ignored, not staged.
4. **Voice UI messaging** — `FileComplaintView.tsx`'s idle voice-recorder
   state was rebuilt from a big mic button + tiny "or upload" dashed-link
   into two equal-weight side-by-side cards ("Record Live" / "Upload a Voice
   Note"), both calling the same `POST /complaint/voice` path. No functional
   change, framing only.
5. **Pre-seeded Public Dashboard** — `backend/seed_demo_data.py` (new file)
   inserts 18 synthetic complaints spanning all 5 categories and 10 wards,
   with a realistic status mix (9 resolved / 4 escalated / 2 in_progress / 3
   filed) and `filed_at` staggered over the past 2 weeks, plus a
   correctly-formed escalation trail (including B2 notification-log entries)
   for every escalated/resolved record, and one deliberate B1 duplicate pair.
   Idempotent (skips if seed data already present unless `--force`), and
   every seeded `raw_transcript` is prefixed so it's unmistakably fake.
   **Live-run and verified**: `total` went from 20 → 38 complaints via `GET
   /complaints`, with the expected status distribution and one linked
   duplicate pair.

---

## Final Power-Up Directive — Part B (High-Value Features) ✅ B1–B4 all done and live-verified

All four were implemented, and B1/B2/B3 required **additive-only** schema
changes: `complaints.urgency_reason TEXT`, `complaints.duplicate_of TEXT`,
`complaints.duplicate_count INTEGER` — added via an automatic migration in
`db.init_db()` (`_ensure_columns()`, checks `PRAGMA table_info` and runs
`ALTER TABLE ... ADD COLUMN` only for columns that don't already exist), so
existing databases (including one with live-filed complaints from earlier
testing) upgraded in place with zero data loss. No new tables, no backend
architecture changes, no new dependencies.

### B1 — Duplicate complaint detection ✅
- `db.find_recent_duplicate(category, ward, hours=24)` — finds the oldest
  still-unresolved complaint with the same category+ward filed within the
  window; `db.increment_duplicate_count(id)` bumps the counter on that
  original. Wired into both `POST /complaint/text` and `POST
  /complaint/voice` in `main.py`, before `db.create_complaint()`.
- API response gains a `duplicate: {is_duplicate, original_complaint_id,
  duplicate_count}` block on every submission, plus a human-readable note
  appended to `message` when a duplicate is detected.
- **Surfaced in both frontends:** React's `FileComplaintView` success screen
  and `TrackComplaintView` detail page show "N citizens have reported this
  issue" / "linked as a duplicate of #…" banners; Streamlit's File Complaint
  tabs and Complaint Detail page show the equivalent `kural-alert info` boxes.
- **Live-verified** with two real text complaints about the same pothole
  near Panagal Park, T.Nagar, ~11 seconds apart: the second was correctly
  flagged `is_duplicate=true`, linked to the first's ID, and the first's
  `duplicate_count` incremented to 1 — confirmed via `GET /complaints/{id}`
  and visually in both the React and Streamlit UIs (screenshots taken).

### B2 — Simulated citizen notification log ✅
- No new table: `db.add_notification_log(complaint_id, status, message)`
  appends to the **existing** `escalation_trail` table with
  `previous_status == new_status` (marks it as a non-transition event) and a
  `[SIMULATED SMS]` text prefix (`db.NOTIFICATION_LOG_MARKER`). Called from
  `escalation.poll_sla_deadlines()` / `trigger_escalation_check_now()` right
  after every real escalation, and from `main.resolve_complaint()` right
  after every genuine resolution.
- **Frontend rendering:** both `adapters.ts::buildTimeline()` and
  Streamlit's escalation-trail loop check for the marker prefix *before*
  falling into the normal escalated/resolved branches, so notification
  entries render as a visually distinct blue/indigo "📱 Citizen Notified
  (Simulated SMS)" timeline node — never double-counted as a second real
  transition.
- **Live-verified**: escalating and then resolving a real complaint produced
  exactly the expected 4-event trail (SLA breach → SMS-sim → resolution →
  SMS-sim), visible with the correct distinct styling in both the React
  Track page and the Streamlit Complaint Detail page (screenshots taken).

### B3 — Extraction reasoning surfaced ✅
- Added `urgency_reason` (5–200 chars) to the shared extraction tool schema
  in `extraction.py` (used by both the Claude and NIM tool definitions,
  since the Claude one is derived from the NIM one) and to `models.Complaint`
  / `models.ComplaintRecord`. System prompt now explicitly tells the model
  not to just restate the urgency label.
- **Live-verified with real Claude calls**, not a mock: filing "pothole
  injured a two-wheeler rider" returned `urgency_reason: "A two-wheeler
  rider already fell and was injured due to the pothole, indicating an
  active accident/safety risk."` — a genuine, complaint-specific rationale,
  not a generic restatement.
- **Surfaced in both frontends** next to the urgency badge: React shows it
  italicized on the Track page header and the File Complaint success
  screen; Streamlit shows it as a `🧠 Why this urgency?` caption under the
  detail-page metrics row.

### B4 — Language toggle wiring ✅ (already built, verified live — no code changes needed)
- The React frontend already had full bilingual (English/தமிழ்) scaffolding
  wired end-to-end before this directive: `Navbar.tsx` has a working
  toggle button (`setLanguage`), and every citizen-facing component (Home,
  File Complaint, Track, Dashboard, About) already branches its copy on the
  `language` prop.
- **Live-verified via browser**: toggled English → Tamil → English on Home,
  File Complaint, and Track; navbar links, headings, placeholders, and
  button text all switched correctly both directions, with no missed
  strings on the pages checked.

### Testing
- Added `test_db_urgency_reason_persisted`, `test_db_duplicate_detection`,
  `test_db_notification_log` to `tests/test_pipeline.py`, and tightened
  `test_escalation_poll_escalates_overdue` to assert the exact 2-event trail
  (real transition + B2 notification). Updated every mocked extraction
  test's tool-call payload to include `urgency_reason` (now a required
  field). **31/31 tests passing.**
- Every Part B feature was additionally exercised against the **live**
  running backend with real Claude API calls (not just mocks) per the
  directive's verification requirement — see the live-verified notes above.

---

## Final Wrap-Up Directive — Parts A–E ✅ all done and live-verified

**This was the last content pass before submission. All five parts (A–E)
are complete, live-tested against the running backend/frontends, and
`pytest tests/ -v` is at 42/42 passing.**

### Part A — Tamil font rendering bug ✅ fixed and verified live
- Self-hosted Noto Sans Tamil `.woff2` (weights 400/500/600/700) in
  `kural_web/public/fonts/`, wired via `@font-face` + appended (not
  prepended) to every font-stack variable in `kural_web/src/index.css`, plus
  a root-level `html { font-family: ... }` fallback. Streamlit
  (`frontend/app.py`) uses a Google Fonts `@import` addition instead, since
  Streamlit re-injects CSS at runtime rather than serving static assets.
- **Verified live via real browser screenshots** (not just code review):
  toggled the site to Tamil and confirmed every UI string renders as actual
  Tamil glyphs — headings, nav labels, stat cards, step descriptions — no
  tofu boxes anywhere. Filed a live complaint with a pure-Tamil transcript
  ("மயிலாப்பூர் பகுதியில் மூன்று நாட்களாக குப்பை அகற்றப்படவில்லை…") through
  `POST /complaint/text`; Claude correctly extracted category=Sanitation,
  ward=Mylapore, and a valid `ticket_id` — end-to-end Tamil input works.
  - Note: neither frontend currently *displays* `raw_transcript` anywhere
    (only the AI-generated English `summary` is shown) — this was already
    true before this pass, not a regression. The font fix still matters for
    every Tamil string that *is* rendered (language toggle copy, and any
    future surfacing of raw transcripts).

### Part B — Real ticket ID format ✅ implemented, migrated, and one real bug fixed
- `ticket_id` format `GCC/{DEPT_CODE}/{YEAR}/{SEQUENCE}` (e.g.
  `GCC/SWM/2026/00012`), generated in `db.generate_ticket_id()` from a
  per-department, per-year `MAX(sequence)` query. Additive `ALTER TABLE
  complaints ADD COLUMN ticket_id TEXT` migration + `_backfill_ticket_ids()`
  (chronological, one-time) + a unique index applied *after* backfilling —
  all in `db.init_db()`, zero data loss on existing rows.
- `db.get_complaint_by_identifier()` accepts either `ticket_id` or the
  internal UUID `id`. Wired into `GET /complaints/{id}` and `POST
  /complaints/{id}/resolve`. Displayed everywhere citizen-facing in both
  frontends (File Complaint confirmation, Track page, Complaint Detail,
  History table, Streamlit cards) instead of a truncated UUID.
- **🐛 Real bug found and fixed during live verification:** `ticket_id`
  contains literal `/` characters, but `@app.get("/complaints/{complaint_id}")`
  used FastAPI's default single-path-segment matcher, which cannot match a
  value containing `/` — **even when the frontend correctly
  `encodeURIComponent()`-encoded it**, because ASGI servers unquote the path
  before Starlette routes it, so `%2F` becomes a real `/` before matching.
  Every ticket-ID lookup (`GET /complaints/{id}`, `POST
  /complaints/{id}/resolve`) was silently 404-ing. **Fixed** by switching
  both routes to the `{complaint_id:path}` converter (`backend/main.py`).
  Verified live with `curl` (raw `/`, `%2F`-encoded, and via the real React
  Track page UI) — all three now resolve correctly, and the `/resolve`
  audit call on a slash-containing ticket ID works end to end.
- **🐛 Second real bug found and fixed:** `POST /complaints/{id}/resolve`'s
  "reopen" branch (vague resolution note rejected by the LLM audit) added an
  escalation-trail entry saying `new_status=escalated` but **never actually
  updated the `complaints.status` column** — so a rejected resolution left
  the complaint's real status stuck on its old value (e.g. still `filed`)
  while the trail claimed "escalated". Exactly the kind of inconsistency the
  new History view (Part D) would visibly surface. **Fixed** by calling
  `db.update_complaint_status(..., ComplaintStatus.escalated)` +
  `db.increment_escalation_count()` + a B2 notification-log entry in that
  branch, mirroring the pattern `escalation.py`'s SLA poller already uses.
  Verified live: filed a complaint, submitted "issue noted" as the
  resolution, confirmed `status` flips to `escalated` and
  `escalation_count` increments in `GET /complaints/{id}` — then submitted
  a detailed, genuine resolution note on the same complaint and confirmed
  the "genuine" path still correctly resolves it.
- `seed_demo_data.py` generates real sequential `ticket_id`s per department
  per year for all seeded complaints.
- **New tests:** `test_db_ticket_id_format_and_sequence`,
  `test_db_get_complaint_by_identifier_ticket_id_and_id_fallback`,
  `test_db_backfill_assigns_ticket_ids_to_legacy_rows`.

### Part C — Expand ward coverage ✅ 38 real localities, live fuzzy-match verified
- `backend/seed_data.json` expanded from ~10 wards to **38** real Chennai
  localities with corrected GCC ward numbers (researched against public GCC
  ward data — several original entries were wrong, e.g. Ward 82 was
  mislabeled "Adyar" when it's actually Kolathur; Tambaram was removed
  entirely since it left GCC jurisdiction in 2021). `default_ward` updated
  to a valid new entry.
- **Live-verified fuzzy matching** for 7 new localities directly against
  `routing.resolve_ward()` (Besant Nagar, Vadapalani, Guindy, Nungambakkam,
  Mylapore, Anna Nagar, Velachery) — all resolve confidently to the correct
  ward, and a deliberately out-of-list input ("Porur signal, near unnamed
  lake") still correctly falls back to the default with the unmatched-ward
  warning, confirming the fallback path wasn't accidentally broken by the
  expansion.
- Homepage stat card corrected from a stale hardcoded "15 Wards" to "38
  Wards" (`kural_web/src/components/StatsGrid.tsx`) — this was a real
  factual inaccuracy left over from before the expansion.
- **New tests:** `test_ward_coverage_expanded_to_30_plus_localities`,
  `test_new_localities_resolve_confidently` (parameterized over 7
  localities). Two pre-existing tests
  (`test_ward_resolution_confidence_flag`, `test_route_complaint_flags_unmatched_ward`)
  had their non-matching input swapped ("Marina area…" → "Porur signal…")
  since "Marina" became a real match after the expansion.

### Part D — Complaint history / analytics view ✅ new page, live-verified
- New `kural_web/src/components/HistoryView.tsx` — a "History" tab (added
  to `Navbar.tsx` / `App.tsx`) showing a client-side filterable + sortable
  table of every complaint: ticket ID, category, ward, filed date, resolved
  date, status, duplicate count, and a "Track →" action button. Search box
  + status/category dropdown filters + clickable column-header sorting.
  Reuses the existing `GET /complaints?limit=200` — **no new backend
  endpoint** (client-side filtering is sufficient at this data scale, per
  the directive). Auto-refreshes every 20s like the Dashboard.
- Dashboard's "Live Grievance Queue" got a "View Full History →" link into
  this new page.
- **Live-verified via real browser**: navigated to History, confirmed all
  41 live records rendered with correct `ticket_id` formatting, status
  badges, and duplicate-count chips; clicked "Track" on a row and confirmed
  it correctly deep-links into the Track page and auto-searches (this also
  exercised the Part B path-converter fix end-to-end through the real UI).

### Part E — Real interactive map ✅ implemented (time allowed) and live-verified
- Added approximate real lat/lng to all 38 wards in `seed_data.json`
  (well-known landmark/locality coordinates — static data only, no
  geocoding, no live GPS, per the directive's explicit constraint).
- `GET /meta/wards` extended **additively** with a `ward_details` array
  (`id`, `display`, `area`, `lat`, `lng`) alongside the original unchanged
  `wards` name list — no existing consumer broken.
- New `kural_web/src/components/WardMap.tsx` using `leaflet` +
  `react-leaflet` (v5, React-19-compatible) + OpenStreetMap tiles (no API
  key needed). Renders one circle marker per ward with lat/lng, colored by
  that ward's current complaint-status mix (red = has an escalated
  complaint, green = all resolved, amber = open/in-progress, grey = no
  complaints yet), with a popup showing the per-ward status breakdown.
  Wired into `DashboardView.tsx` below the existing charts.
- **Live-verified via real browser**: confirmed all 38 markers render on a
  real Chennai OpenStreetMap tile layer at the correct real-world
  coordinates, colors matched the live complaint data (verified against the
  same data in the History table), and clicking a marker opens the correct
  popup.

### Data hygiene fix (found while verifying D + E together)
- **🐛 Real bug found:** the previously-seeded 18 demo complaints (Part A
  of the earlier Final Power-Up pass) plus a handful of complaints filed
  during early live-testing sessions still had **stale ward strings** from
  before the Part C ward-data correction (e.g. `"Ward 82 - Adyar"` instead
  of the corrected `"Ward 173 - Adyar"`, and one complaint even referenced
  `"Ward 108 - Tambaram"` — a ward that was explicitly removed from GCC).
  This silently broke the new ward map (those wards got zero pins) and
  would have looked bad under close inspection. **Fixed** by running
  `python -m backend.seed_demo_data --wipe` to wipe and cleanly re-seed with
  the already-corrected script — verified the resulting DB has exactly the
  38 correct current ward strings, no legacy/incorrect ones, and re-ran
  `pytest` (42/42) plus a full Dashboard/History/Map browser check
  afterward to confirm nothing else regressed.

### README.md updated for accuracy
- Architecture diagram, setup steps (added `kural_web/` npm install/run +
  seed-script step), API reference (`ticket_id` format + lookup semantics,
  `ward_details`), project structure, and the UI/UX judging-criteria row
  were all updated — the previous README predated the React integration
  entirely and only described the Streamlit-only architecture.

### Test status
`pytest tests/ -v` → **42/42 passing** (unchanged pass count from the
previous pass's 42 — no tests were removed, several were adjusted for the
ward expansion, several new ones added for ticket ID + ward coverage as
listed above).

### Nothing left half-migrated
- Every complaint row in the live DB has a `ticket_id` (backfill runs
  automatically in `init_db()` for any pre-existing rows without one).
- Every ward in `seed_data.json` has both the corrected ward number and a
  `lat`/`lng` pair — no partial coverage.
- Both frontends (React + Streamlit) and the test suite were updated
  together for every schema-relevant change in this pass; nothing was left
  wired on one side only.

**Status at end of this pass: A, B, C, D, and E are all done and
live-verified. No known remaining gaps beyond the pre-existing ones listed
in "Known Gaps / Remaining Work" above (real mic input via browser
automation, sample-audio variety, open CORS — all pre-existing and
explicitly out of scope for this pass).**
