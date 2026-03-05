import os
import secrets
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Always resolve .env from the project root (one level above this file)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # used for Whisper API transcription (Agent 1)

# Validate OpenAI API key
if OPENAI_API_KEY and (not OPENAI_API_KEY.startswith("sk-") or "your-openai-api-key" in OPENAI_API_KEY):
    warnings.warn("Invalid OPENAI_API_KEY detected. Whisper API will fall back to Google STT.", stacklevel=2)
    OPENAI_API_KEY = None

if not OPENAI_API_KEY:
    warnings.warn("OPENAI_API_KEY not set — Whisper transcription will fall back to Google STT")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    warnings.warn("GEMINI_API_KEY not set — CMIO briefing will fall back to deterministic summary")

# ── AI Model Configuration ────────────────────────────────────────────────────
# OpenAI Whisper API model (cloud) — used as primary transcription engine
WHISPER_API_MODEL = "whisper-1"
# Local faster-whisper model size (kept for reference; cloud API is preferred when key is set)
WHISPER_MODEL = "base"

# HuggingFace local model for SBAR extraction (primary extraction engine)
HF_SBAR_MODEL = "google/flan-t5-base"

# HuggingFace sentence-embedding model used by billing and literature agents
HF_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

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