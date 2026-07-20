# Backend image for KURAL FastAPI (Whisper + Claude + SQLite + APScheduler).
# Build from repo root:
#   docker build -f backend/Dockerfile -t kural-backend .

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Persist SQLite outside the image layers (overridden in compose).
    DB_PATH=/data/kural.db

WORKDIR /app

# System deps for openai-whisper (ffmpeg) and any native wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Package layout: uvicorn backend.main:app expects /app/backend/...
COPY backend/ ./backend/

RUN mkdir -p /data

EXPOSE 8000

# Named volume in compose should mount at /data so DB_PATH persists.
VOLUME ["/data"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
