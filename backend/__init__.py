"""
MedRelay backend package.

On import, configures ffmpeg path from imageio-ffmpeg so that audio conversion
works on Windows without a system-wide ffmpeg install.

Provides `get_ffmpeg_path()` for any module that needs to call ffmpeg directly.
"""

import os
import subprocess
import tempfile

_FFMPEG_EXE = None

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

    if not os.path.isfile(_FFMPEG_EXE):
        print(f"[Backend] WARNING: ffmpeg binary not found at {_FFMPEG_EXE}")
        _FFMPEG_EXE = None
    else:
        print(f"[Backend] ffmpeg binary: {_FFMPEG_EXE}")

        # Add directory to PATH so any subprocess can find ffmpeg by name
        _ffmpeg_dir = os.path.dirname(_FFMPEG_EXE)
        if _ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        # Also configure pydub just in case anything still uses it
        try:
            import pydub.utils
            from pydub import AudioSegment
            pydub.utils.get_encoder_name = lambda: _FFMPEG_EXE
            pydub.utils.get_prober_name = lambda: _FFMPEG_EXE
            AudioSegment.converter = _FFMPEG_EXE
            AudioSegment.ffmpeg = _FFMPEG_EXE
            AudioSegment.ffprobe = _FFMPEG_EXE
        except Exception:
            pass

        print("[Backend] ffmpeg configured successfully")

except Exception as e:
    print(f"[Backend] Failed to configure ffmpeg: {e}")
    import traceback
    traceback.print_exc()


def get_ffmpeg_path() -> str | None:
    """Return the absolute path to ffmpeg, or None if unavailable."""
    return _FFMPEG_EXE


def convert_audio_to_wav(audio_bytes: bytes, source_ext: str = ".webm") -> bytes:
    """Convert audio bytes to 16-bit mono 16kHz WAV using ffmpeg subprocess.

    This bypasses pydub entirely — no ffprobe dependency.
    Returns WAV bytes, or raises on failure.
    """
    if not _FFMPEG_EXE:
        raise RuntimeError("ffmpeg binary not available")

    in_tmp = None
    out_tmp = None
    try:
        # Write input to temp file
        with tempfile.NamedTemporaryFile(suffix=source_ext, delete=False) as f:
            f.write(audio_bytes)
            in_tmp = f.name

        # Prepare output path
        out_tmp = in_tmp.rsplit(".", 1)[0] + ".wav"

        cmd = [
            _FFMPEG_EXE,
            "-y",              # overwrite
            "-i", in_tmp,      # input
            "-ar", "16000",    # 16 kHz sample rate
            "-ac", "1",        # mono
            "-sample_fmt", "s16",  # 16-bit signed
            "-f", "wav",       # force WAV output
            out_tmp,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"ffmpeg exited {result.returncode}: {stderr}")

        with open(out_tmp, "rb") as f:
            wav_bytes = f.read()

        if len(wav_bytes) < 44:  # WAV header is 44 bytes minimum
            raise RuntimeError(f"ffmpeg produced empty WAV ({len(wav_bytes)} bytes)")

        return wav_bytes

    finally:
        for p in (in_tmp, out_tmp):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass
