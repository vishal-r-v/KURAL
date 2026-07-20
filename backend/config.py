"""
config.py — Environment variable loading for KURAL backend.

Loads all required configuration from .env file at startup.
Fails loudly if required variables are missing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from backend/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


# ---------------------------------------------------------------------------
# Anthropic / Claude  (fallback LLM)
# ---------------------------------------------------------------------------

def get_anthropic_api_key() -> str:
    """Return the Anthropic API key, raising clearly if missing."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and fill in your key."
        )
    return key


def get_claude_model() -> str:
    """Return the Claude model to use (fallback only)."""
    return os.getenv("CLAUDE_MODEL", "claude-sonnet-5")


# ---------------------------------------------------------------------------
# NVIDIA NIM  (primary LLM)
# ---------------------------------------------------------------------------

def get_nim_api_key() -> str:
    """Return the NVIDIA NIM API key. Empty string if not configured."""
    return os.getenv("NVIDIA_NIM_API_KEY", "")


def get_nim_model() -> str:
    """Return the NVIDIA NIM model name."""
    return os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.3-70b-instruct")


def get_nim_base_url() -> str:
    """Return the NVIDIA NIM API base URL."""
    return os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")


def nim_is_configured() -> bool:
    """Return True if NVIDIA NIM credentials are present."""
    return bool(get_nim_api_key())


# ---------------------------------------------------------------------------
# Whisper / DB / Scheduler
# ---------------------------------------------------------------------------

def get_whisper_model() -> str:
    """Return the Whisper model size to use (default: base)."""
    return os.getenv("WHISPER_MODEL", "base")


def get_db_path() -> str:
    """Return the SQLite database path."""
    return os.getenv("DB_PATH", str(Path(__file__).parent / "kural.db"))


def get_sla_poll_interval_seconds() -> int:
    """Return how often (in seconds) the SLA scheduler polls the DB."""
    return int(os.getenv("SLA_POLL_INTERVAL_SECONDS", "60"))
