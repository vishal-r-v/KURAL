# Streamlit admin / demo dashboard for KURAL.
# Build from repo root:
#   docker build -f frontend/Dockerfile -t kural-admin .
#
# Only needs Streamlit + requests (calls the backend over HTTP).
# Avoids reinstalling Whisper/torch just for the admin UI.

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Server-side calls use the compose service name (set in docker-compose.yml).
    KURAL_BACKEND_URL=http://backend:8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Pin versions to match requirements.txt Streamlit section.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir \
        streamlit==1.38.0 \
        requests==2.32.3 \
        python-dotenv==1.0.1

COPY frontend/ ./frontend/

EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true"]
