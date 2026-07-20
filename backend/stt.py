"""
stt.py — Whisper speech-to-text transcription for KURAL.

Handles Tamil, Tanglish, and English code-mixed audio.
Uses OpenAI Whisper locally (no API call) with Tamil language hint.
Runs in a thread pool to avoid blocking the FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from backend.config import get_whisper_model

logger = logging.getLogger(__name__)

# Lazy-loaded Whisper model (loaded once on first use)
_whisper_model = None
_model_lock = asyncio.Lock()


def _load_model():
    """Load Whisper model synchronously. Called in thread pool."""
    import whisper

    model_name = get_whisper_model()
    logger.info(f"Loading Whisper model: {model_name}")
    return whisper.load_model(model_name)


def _transcribe_sync(audio_path: str) -> dict:
    """
    Run Whisper transcription synchronously.

    Language hint decision (live-verified 2026-07-19): forcing Tamil (`ta`)
    was the original design intent for Tamil/Tanglish/English code-mixed
    speech, but live testing against the actual sample audio showed the
    opposite of what was expected — with `language="ta"`, Whisper renders
    *everything* phonetically into Tamil script, including the English
    words/structure that dominate typical Tanglish complaints ("garbage
    collect pannala", "please urgent action"), destroying the semantic
    content those English words carried and causing the downstream LLM to
    misclassify the complaint category. Forcing `language="en"` instead let
    Whisper transcribe the English-structured backbone faithfully while
    still picking up Tamil loanwords by ear, which produced correct
    category/ward extraction on the same audio where `ta` did not.
    """
    global _whisper_model

    import whisper

    if _whisper_model is None:
        _whisper_model = _load_model()

    logger.info(f"Transcribing: {audio_path}")
    result = _whisper_model.transcribe(
        audio_path,
        language="en",           # see docstring — verified more accurate than "ta" for Tanglish
        task="transcribe",       # transcribe (not translate)
        fp16=False,              # CPU-safe default
        verbose=False,
    )
    return result


async def transcribe(audio_path: str) -> str:
    """
    Async wrapper for Whisper transcription.

    Runs in a thread pool to avoid blocking the FastAPI event loop.
    Returns the raw transcript text.

    Args:
        audio_path: Absolute path to the audio file (wav, mp3, m4a, etc.)

    Returns:
        Transcribed text string.

    Raises:
        FileNotFoundError: If audio_path does not exist.
        RuntimeError: If Whisper transcription fails.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _transcribe_sync, audio_path)
        transcript = result.get("text", "").strip()

        if not transcript:
            logger.error(f"STT produced empty transcript for {audio_path}")
            raise RuntimeError("Whisper returned empty transcript. Check audio quality — try speaking closer to the mic or in a quieter environment.")

        logger.info(f"Transcript: {transcript[:100]}...")
        return transcript

    except RuntimeError:
        raise  # already a clean, user-facing message — don't double-wrap
    except Exception as exc:
        logger.error(f"STT failed for {audio_path}: {exc}")
        raise RuntimeError(f"Transcription failed: {exc}") from exc


async def transcribe_upload(audio_bytes: bytes, suffix: str = ".wav") -> str:
    """
    Transcribe audio from raw bytes (e.g., from FastAPI UploadFile).

    Writes to a temp file, transcribes, then cleans up.

    Args:
        audio_bytes: Raw audio bytes.
        suffix: File extension hint for format detection.

    Returns:
        Transcribed text string.
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return await transcribe(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
