"""
MedRelay — Local Audio Storage
Saves raw audio recordings to disk before sending for transcription.
Supports WAV conversion, metadata tracking, and audio replay.
"""

import asyncio
import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_RECORDINGS_DIR = Path(__file__).parent.parent / "recordings"
_METADATA_DIR = _RECORDINGS_DIR / "metadata"
_TRANSCRIPTS_DIR = _RECORDINGS_DIR / "transcripts"
_DRAFTS_DIR = _RECORDINGS_DIR / "drafts"

_executor = ThreadPoolExecutor(max_workers=2)


def _ensure_dirs():
    """Create storage directories if they don't exist."""
    for d in [_RECORDINGS_DIR, _METADATA_DIR, _TRANSCRIPTS_DIR, _DRAFTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


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
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/flac": ".flac",
    "audio/wav": ".wav",
}


def _convert_to_wav_sync(audio_bytes: bytes, source_ext: str) -> bytes:
    """Convert audio to 16-bit mono WAV using ffmpeg subprocess.
    Uses the ffmpeg binary from imageio-ffmpeg (configured in backend/__init__.py).
    No pydub or ffprobe dependency.
    """
    from backend import convert_audio_to_wav
    return convert_audio_to_wav(audio_bytes, source_ext)


def _save_sync(recording_id: str, raw_audio: bytes, metadata: dict) -> dict:
    """Synchronous save — called via executor to not block the event loop."""
    _ensure_dirs()

    mime = _detect_mime(raw_audio)
    source_ext = _MIME_TO_EXT.get(mime, ".webm")

    # 1. Save the raw original audio
    raw_path = _RECORDINGS_DIR / f"{recording_id}{source_ext}"
    raw_path.write_bytes(raw_audio)

    # 2. Convert to WAV for Python processing
    wav_path = _RECORDINGS_DIR / f"{recording_id}.wav"
    try:
        wav_bytes = _convert_to_wav_sync(raw_audio, source_ext)
        wav_path.write_bytes(wav_bytes)
        wav_size = len(wav_bytes)
    except Exception as e:
        print(f"[AudioStorage] WAV conversion failed: {e}")
        wav_size = 0

    # 3. Save metadata JSON
    meta = {
        "recording_id": recording_id,
        "original_format": mime,
        "original_ext": source_ext,
        "original_size_bytes": len(raw_audio),
        "wav_size_bytes": wav_size,
        "duration_estimate_sec": round(wav_size / (16000 * 2) if wav_size else len(raw_audio) / 16000, 1),
        "saved_at": datetime.now().isoformat(),
        "raw_path": str(raw_path),
        "wav_path": str(wav_path) if wav_size else None,
        **metadata,
    }
    meta_path = _METADATA_DIR / f"{recording_id}.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"[AudioStorage] Saved recording {recording_id}: "
          f"{len(raw_audio)} bytes ({source_ext}) → WAV {wav_size} bytes")
    return meta


async def save_recording(
    audio_chunks: list[bytes],
    outgoing_nurse: str = "",
    incoming_nurse: str = "",
    session_id: str | None = None,
) -> dict:
    """
    Save audio chunks to disk as both raw format and converted WAV.
    Returns metadata dict with paths and recording_id.
    """
    raw_audio = b"".join(audio_chunks)
    if len(raw_audio) < 256:
        return {"error": "Audio too small to save", "recording_id": None}

    recording_id = session_id or str(uuid.uuid4())
    metadata = {
        "outgoing_nurse": outgoing_nurse,
        "incoming_nurse": incoming_nurse,
        "session_id": session_id,
        "chunk_count": len(audio_chunks),
    }

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _save_sync, recording_id, raw_audio, metadata)
    return result


async def save_transcript(recording_id: str, transcript: str) -> str:
    """Save the transcript text for a recording."""
    _ensure_dirs()
    path = _TRANSCRIPTS_DIR / f"{recording_id}.txt"
    path.write_text(transcript, encoding="utf-8")
    return str(path)


async def save_draft_transcript(recording_id: str, partial_transcript: str) -> str:
    """Save a draft/partial transcript during recording (auto-save)."""
    _ensure_dirs()
    path = _DRAFTS_DIR / f"{recording_id}_draft.txt"
    path.write_text(partial_transcript, encoding="utf-8")
    return str(path)


async def get_recording_wav(recording_id: str) -> bytes | None:
    """Return WAV bytes for a recording (for replay/re-processing)."""
    wav_path = _RECORDINGS_DIR / f"{recording_id}.wav"
    if wav_path.exists():
        return wav_path.read_bytes()
    return None


async def get_recording_metadata(recording_id: str) -> dict | None:
    """Return metadata for a recording."""
    meta_path = _METADATA_DIR / f"{recording_id}.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return None


async def get_transcript(recording_id: str) -> str | None:
    """Return saved transcript text, falling back to draft if available."""
    final_path = _TRANSCRIPTS_DIR / f"{recording_id}.txt"
    if final_path.exists():
        return final_path.read_text(encoding="utf-8")
    draft_path = _DRAFTS_DIR / f"{recording_id}_draft.txt"
    if draft_path.exists():
        return draft_path.read_text(encoding="utf-8")
    return None


async def list_recordings(limit: int = 50) -> list[dict]:
    """List recent recordings with metadata."""
    _ensure_dirs()
    files = sorted(_METADATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    results = []
    for f in files[:limit]:
        try:
            meta = json.loads(f.read_text())
            # Check if transcript exists
            rec_id = meta.get("recording_id", "")
            meta["has_transcript"] = (_TRANSCRIPTS_DIR / f"{rec_id}.txt").exists()
            meta["has_draft"] = (_DRAFTS_DIR / f"{rec_id}_draft.txt").exists()
            results.append(meta)
        except Exception:
            continue
    return results


async def delete_recording(recording_id: str) -> bool:
    """Delete all files for a recording."""
    deleted = False
    for pattern in [
        _RECORDINGS_DIR / f"{recording_id}.*",
        _METADATA_DIR / f"{recording_id}.json",
        _TRANSCRIPTS_DIR / f"{recording_id}.txt",
        _DRAFTS_DIR / f"{recording_id}_draft.txt",
    ]:
        if isinstance(pattern, Path) and "*" not in str(pattern):
            if pattern.exists():
                pattern.unlink()
                deleted = True
        else:
            parent = pattern.parent
            name = pattern.name
            for f in parent.glob(name):
                f.unlink()
                deleted = True
    return deleted


def get_recordings_dir() -> Path:
    """Return the recordings directory path."""
    return _RECORDINGS_DIR
