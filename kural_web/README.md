# KURAL Web — Citizen Frontend

This is the citizen-facing React frontend for KURAL. It talks directly to the
KURAL FastAPI backend (`../backend`) for filing complaints (text + voice),
tracking complaint status, viewing the escalation timeline, and the public
dashboard. The Streamlit app (`../frontend`) remains a separate internal
admin/demo dashboard and is untouched by this project.

## Run Locally

**Prerequisites:** Node.js, and the KURAL backend running (see the repo root
`README.md` — typically `uvicorn backend.main:app --reload` from the project
root, on `http://localhost:8000`).

1. Install dependencies:
   `npm install`
2. Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` to wherever the
   FastAPI backend is running (defaults to `http://localhost:8000`).
3. Run the app:
   `npm run dev`
4. Open `http://localhost:3000`.

## Architecture

```
Citizen -> React (this app) -> FastAPI backend -> SQLite -> Claude -> Whisper -> APScheduler
```

All backend calls live in `src/lib/api.ts` (fetch/XHR abstraction with typed
errors) and `src/lib/adapters.ts` (maps backend JSON onto the existing
frontend `Complaint`/`TimelineEvent` types in `src/types.ts`). No API base
URLs are hardcoded elsewhere in the app — everything reads from
`src/lib/config.ts`, which is driven by `VITE_API_BASE_URL`.

## Build

`npm run build` produces a static production bundle in `dist/` plus a
minimal Express static host (`dist/server.cjs`) — start it with `npm start`.
