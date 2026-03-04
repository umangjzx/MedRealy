import os
import secrets
import warnings
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # no longer used for transcription
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Validate Anthropic API Key format (simple check)
if ANTHROPIC_API_KEY and (ANTHROPIC_API_KEY.startswith("http") or "your-openai-api-key" in ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith("sk-")):
    warnings.warn(f"Invalid ANTHROPIC_API_KEY detected. Disabling API usage.", stacklevel=2)
    ANTHROPIC_API_KEY = None

# Warn (don't crash) if API keys are missing — demo mode still works
if not ANTHROPIC_API_KEY:
    warnings.warn("ANTHROPIC_API_KEY not set — Claude extraction/report will fall back to demo data")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    warnings.warn("GEMINI_API_KEY not set — Gemini model will fall back to demo data")

# ── AI Model Configuration ────────────────────────────────────────────────────
# Transcription is now handled locally via faster-whisper (no API key needed)
WHISPER_MODEL = "base"  # faster-whisper model size used in relay_agent.py

# Claude model for SBAR extraction and report generation
CLAUDE_MODEL = "claude-sonnet-4-6"

# HuggingFace local model for SBAR extraction (fallback when Claude is unavailable)
HF_SBAR_MODEL = "google/flan-t5-base"

# ── JWT / Authentication ──────────────────────────────────────────────────────
# IMPORTANT: In production, set MEDRELAY_JWT_SECRET as an environment variable!
JWT_SECRET = os.getenv("MEDRELAY_JWT_SECRET", "runbackend")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("MEDRELAY_ACCESS_TOKEN_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("MEDRELAY_REFRESH_TOKEN_DAYS", "7"))

# Account lockout
MAX_LOGIN_ATTEMPTS = int(os.getenv("MEDRELAY_MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("MEDRELAY_LOCKOUT_MINUTES", "15"))

# ── CORS / Allowed Origins ────────────────────────────────────────────────────
# Comma-separated list; "*" = allow all (dev only)
_raw_origins = os.getenv("MEDRELAY_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# ── Vitals Thresholds ─────────────────────────────────────────────────────────
VITALS_THRESHOLDS = {
    "hr": {"low": 50, "high": 120},
    "sbp": {"low": 90, "high": 180},
    "spo2": {"low": 92},
    "rr": {"low": 10, "high": 30},
    "temp": {"low": 36.0, "high": 38.5},
}

# ── External APIs ─────────────────────────────────────────────────────────────
OPENFDA_BASE_URL = "https://api.fda.gov/drug/event.json"