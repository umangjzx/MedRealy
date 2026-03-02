"""
Agent 1 — Relay Agent
Handles audio accumulation and transcription via SpeechRecognition.
Uses Google's free Speech Recognition API (no API key required).
Never falls back to demo transcript during real capture.

Audio format handling:
  - WAV/FLAC/AIFF are natively supported by SpeechRecognition.
  - WebM/OGG/MP3 are converted to WAV via pydub (requires ffmpeg on PATH).
  - Live partials use a single-pass fast path (no retries).
  - Final transcription uses a retry strategy: detected format → WAV conversion → fallback.
"""

import asyncio
import io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import speech_recognition as sr

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
    """Convert non-native audio formats to WAV using pydub.
    Requires ffmpeg on system PATH for webm/ogg/mp3 decoding.
    """
    from pydub import AudioSegment

    ext_to_format = {
        ".webm": "webm",
        ".ogg":  "ogg",
        ".mp3":  "mp3",
        ".flac": "flac",
        ".wav":  "wav",
    }
    fmt = ext_to_format.get(ext, "webm")
    audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
    # Export as 16-bit mono WAV (optimal for speech recognition)
    audio_segment = audio_segment.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    wav_buffer = io.BytesIO()
    audio_segment.export(wav_buffer, format="wav")
    return wav_buffer.getvalue()


def _do_transcribe(audio_bytes: bytes, ext: str) -> str:
    """Write audio to a temp file, run SpeechRecognition, return transcript text.
    This is synchronous and must be called from a thread executor.
    Non-native formats are converted to WAV via pydub before recognition.
    """
    tmp_path = None
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

        # Use Google's free speech recognition (no API key needed)
        text = _recognizer.recognize_google(audio_data)
        text = text.strip() if text else ""
        if text:
            print(f"[Relay] Transcribed ({ext}): {len(text)} chars")
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


def _transcribe_fast(audio_bytes: bytes, preferred_ext: str) -> str:
    """Fast single-pass transcription for live partials.
    No retries — keeps latency minimal."""
    try:
        return _do_transcribe(audio_bytes, preferred_ext)
    except Exception as e:
        print(f"[Relay] Fast transcription failed ({preferred_ext}): {e}")
        return ""


def _transcribe_with_retries(audio_bytes: bytes, preferred_ext: str) -> str:
    """Retry strategy for final transcription (max 2 passes):
       1. Detected extension (converted to WAV if needed)
       2. Direct WAV re-encoding with different parameters
    """
    # Pass 1: detected container format
    try:
        text = _do_transcribe(audio_bytes, preferred_ext)
        if text:
            return text
    except Exception as e:
        print(f"[Relay] Pass 1 failed ({preferred_ext}): {e}")

    # Pass 2: force WAV re-conversion with pydub regardless of original ext
    if preferred_ext != ".wav":
        try:
            wav_bytes = _convert_to_wav(audio_bytes, preferred_ext)
            text = _do_transcribe(wav_bytes, ".wav")
            if text:
                print(f"[Relay] Transcription succeeded with WAV re-encoding fallback")
                return text
        except Exception as e:
            print(f"[Relay] Pass 2 (WAV re-encoding fallback) failed: {e}")

    return ""


async def transcribe_buffer(audio_data: bytes) -> str | None:
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
        text = await loop.run_in_executor(_executor_partial, _transcribe_fast, audio_data, ext)
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

    async def transcribe_full(self) -> str:
        """
        Transcribe the full accumulated audio via SpeechRecognition.
        Returns plain-text transcript.
        Returns empty string if audio is too small or transcription fails.
        Buffer is cleared after transcription.
        """
        buf = bytes(self.audio_buffer)
        self.audio_buffer.clear()

        if len(buf) < _MIN_AUDIO_BYTES:
            print(f"[RelayAgent] Audio too small ({len(buf)} bytes); no transcript captured")
            return ""

        mime = _detect_mime(buf)
        ext = _MIME_TO_EXT.get(mime, ".webm")
        print(f"[RelayAgent] Transcribing {len(buf)} bytes | detected={mime} ext={ext} | header={buf[:8].hex()}")

        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(_executor_final, _transcribe_with_retries, buf, ext)
            if text:
                print(f"[RelayAgent] Transcribed {len(buf)} bytes → {len(text)} chars of real audio")
                return text
            else:
                print(f"[RelayAgent] SpeechRecognition returned empty text for {len(buf)} bytes")
                return ""
        except Exception as e:
            print(f"[RelayAgent] SpeechRecognition transcription failed: {e}")
            return ""
