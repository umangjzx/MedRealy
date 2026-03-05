"""
Agent 1 — Relay Agent
Handles audio accumulation and transcription.
Primary: OpenAI Whisper API (cloud, high accuracy, medical vocabulary).
Fallback: Google Speech Recognition (free, no API key required).

Audio format handling:
  - WAV/FLAC/AIFF are natively supported by SpeechRecognition.
  - WebM/OGG/MP3 are converted to WAV via pydub (requires ffmpeg on PATH).
  - Whisper API accepts all formats directly (no conversion needed).
  - Live partials use a single-pass fast path (no retries).
  - Final transcription uses a retry strategy with format fallbacks.
"""

import asyncio
import io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import speech_recognition as sr

# pydub is configured globally in backend/__init__.py (imageio-ffmpeg)

# WebM header is typically ~200-500 bytes; keep threshold low to avoid false negatives
_MIN_AUDIO_BYTES = 256

# Separate executors: partials should never starve the final transcription
_executor_final = ThreadPoolExecutor(max_workers=1)
_executor_partial = ThreadPoolExecutor(max_workers=1)

# Shared recognizer instance (thread-safe for recognize_* calls)
_recognizer = sr.Recognizer()
# Adjust for ambient noise tolerance
_recognizer.energy_threshold = 300
_recognizer.dynamic_energy_threshold = True

# Lazy-loaded OpenAI client (used for Whisper API)
_openai_client = None

def _get_openai_client():
    """Return a cached OpenAI client if OPENAI_API_KEY is configured."""
    global _openai_client
    if _openai_client is None:
        try:
            from backend.config import OPENAI_API_KEY
            if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"):
                import openai
                _openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
                print("[Relay] OpenAI Whisper API client initialised")
            else:
                # Sentinel: key missing/invalid — don't retry on every call
                _openai_client = False
        except Exception as e:
            print(f"[Relay] Could not initialise OpenAI client: {e}")
            _openai_client = False
    return _openai_client if _openai_client else None


def _detect_mime(buf: bytes) -> str:
    """Detect audio MIME type from buffer header bytes."""
    if buf[:4] == b"\x1aE\xdf\xa3":
        return "audio/webm"
    if buf[:4] == b"OggS":
        return "audio/ogg"
    if buf[:3] == b"ID3" or (buf[:2] == b"\xff\xfb"):
        return "audio/mpeg"
    if buf[:4] == b"fLaC":
        return "audio/flac"
    if buf[:4] == b"RIFF":
        return "audio/wav"
    return "audio/webm"


_MIME_TO_EXT = {
    "audio/webm": ".webm",
    "audio/ogg":  ".ogg",
    "audio/mpeg": ".mp3",
    "audio/flac": ".flac",
    "audio/wav":  ".wav",
}

# Formats natively supported by SpeechRecognition's AudioFile
_NATIVE_FORMATS = {".wav", ".flac", ".aiff"}


def _convert_to_wav(audio_bytes: bytes, ext: str) -> bytes:
    """Convert non-native audio formats to WAV using ffmpeg subprocess.
    Uses the ffmpeg binary from imageio-ffmpeg (configured in backend/__init__.py).
    No pydub or ffprobe dependency.
    """
    from backend import convert_audio_to_wav
    return convert_audio_to_wav(audio_bytes, ext)


# Language codes for Google Speech Recognition
LANGUAGE_CODES = {
    "en": "en-US",
    "hi": "hi-IN",
    "ta": "ta-IN",
}


def _do_transcribe_whisper(audio_bytes: bytes, ext: str, language: str = "en") -> str:
    """Transcribe using the OpenAI Whisper cloud API.
    Supports all common audio formats directly — no conversion needed.
    Language codes match Whisper's ISO 639-1 format (en, hi, ta, etc.).
    """
    client = _get_openai_client()
    if not client:
        raise RuntimeError("OpenAI client not available")
    filename = f"audio{ext}"
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language=language,
    )
    text = (transcript.text or "").strip()
    if text:
        print(f"[Relay] Whisper API transcribed ({ext}, lang={language}): {len(text)} chars")
    return text


def _do_transcribe_google(audio_bytes: bytes, ext: str, language: str = "en") -> str:
    """Transcribe with Google's free Speech Recognition API (fallback).
    Requires wav/flac/aiff; other formats are converted first.
    """
    tmp_path = None
    lang_code = LANGUAGE_CODES.get(language, "en-US")
    try:
        # Convert to WAV if not a natively supported format
        if ext not in _NATIVE_FORMATS:
            audio_bytes = _convert_to_wav(audio_bytes, ext)
            ext = ".wav"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with sr.AudioFile(tmp_path) as source:
            audio_data = _recognizer.record(source)

        # Use Google's free speech recognition with language support
        text = _recognizer.recognize_google(audio_data, language=lang_code)
        text = text.strip() if text else ""
        if text:
            print(f"[Relay] Transcribed ({ext}, lang={lang_code}): {len(text)} chars")
        return text

    except sr.UnknownValueError:
        print(f"[Relay] Speech not understood ({ext}) — audio may be unclear or silent")
        return ""
    except sr.RequestError as e:
        print(f"[Relay] Google Speech Recognition service error: {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _do_transcribe(audio_bytes: bytes, ext: str, language: str = "en") -> str:
    """Primary dispatcher: try OpenAI Whisper API first, fall back to Google STT."""
    client = _get_openai_client()
    if client:
        try:
            return _do_transcribe_whisper(audio_bytes, ext, language)
        except Exception as e:
            print(f"[Relay] Whisper API error, switching to Google STT: {e}")
    return _do_transcribe_google(audio_bytes, ext, language)


def _transcribe_fast(audio_bytes: bytes, preferred_ext: str, language: str = "en") -> str:
    """Fast single-pass transcription for live partials.
    No retries — keeps latency minimal."""
    try:
        return _do_transcribe(audio_bytes, preferred_ext, language)
    except Exception as e:
        print(f"[Relay] Fast transcription failed ({preferred_ext}): {e}")
        return ""


def _transcribe_with_retries(audio_bytes: bytes, preferred_ext: str, language: str = "en") -> str:
    """Retry strategy for final transcription (max 2 passes):
       1. Detected extension (converted to WAV if needed)
       2. Direct WAV re-encoding with different parameters
    """
    # Pass 1: detected container format
    try:
        text = _do_transcribe(audio_bytes, preferred_ext, language)
        if text:
            return text
    except Exception as e:
        print(f"[Relay] Pass 1 failed ({preferred_ext}): {e}")

    # Pass 2: force WAV re-conversion with pydub regardless of original ext
    if preferred_ext != ".wav":
        try:
            wav_bytes = _convert_to_wav(audio_bytes, preferred_ext)
            text = _do_transcribe(wav_bytes, ".wav", language)
            if text:
                print(f"[Relay] Transcription succeeded with WAV re-encoding fallback")
                return text
        except Exception as e:
            print(f"[Relay] Pass 2 (WAV re-encoding fallback) failed: {e}")

    return ""


async def transcribe_buffer(audio_data: bytes, language: str = "en") -> str | None:
    """Transcribe raw audio bytes for live partial display.
    Uses single-pass fast path (no retries) on a dedicated executor
    so it never blocks the final transcription.
    """
    if len(audio_data) < _MIN_AUDIO_BYTES:
        return None
    mime = _detect_mime(audio_data)
    ext = _MIME_TO_EXT.get(mime, ".webm")
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(_executor_partial, _transcribe_fast, audio_data, ext, language)
        return text or None
    except Exception as e:
        print(f"[Relay] Partial transcription failed: {e}")
        return None


class RelayAgent:
    def __init__(self):
        self.audio_buffer = bytearray()

    async def process_audio_chunk(self, chunk: bytes) -> None:
        """Accumulate raw binary audio chunks from the browser."""
        self.audio_buffer.extend(chunk)

    async def transcribe_full(self, language: str = "en") -> str:
        """
        Transcribe the full accumulated audio via SpeechRecognition.
        Returns plain-text transcript.
        Returns empty string if audio is too small or transcription fails.
        Buffer is cleared after transcription.
        Supports language parameter: 'en', 'hi' (Hindi), 'ta' (Tamil).
        """
        buf = bytes(self.audio_buffer)
        self.audio_buffer.clear()

        if len(buf) < _MIN_AUDIO_BYTES:
            print(f"[RelayAgent] Audio too small ({len(buf)} bytes); no transcript captured")
            return ""

        mime = _detect_mime(buf)
        ext = _MIME_TO_EXT.get(mime, ".webm")
        lang_code = LANGUAGE_CODES.get(language, "en-US")
        print(f"[RelayAgent] Transcribing {len(buf)} bytes | detected={mime} ext={ext} | lang={lang_code} | header={buf[:8].hex()}")

        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(_executor_final, _transcribe_with_retries, buf, ext, language)
            if text:
                print(f"[RelayAgent] Transcribed {len(buf)} bytes → {len(text)} chars of real audio")
                return text
            else:
                print(f"[RelayAgent] SpeechRecognition returned empty text for {len(buf)} bytes")
                return ""
        except Exception as e:
            print(f"[RelayAgent] SpeechRecognition transcription failed: {e}")
            return ""
