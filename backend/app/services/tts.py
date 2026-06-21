"""Text-to-speech via the `piper-tts` pip package.

Invoked as `<venv-python> -m piper` rather than imported directly — piper-tts
ships no console-script entry point, and shelling out keeps the same
subprocess-boundary pattern used for whisper-cli (see docs/decisions.md).
Voices are pre-downloaded once via `python -m piper.download_voices` and read
from PIPER_VOICES_DIR; there is no auto-download at synthesis time.
"""

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

PIPER_VOICE_EN = os.environ.get("PIPER_VOICE_EN", "en_US-lessac-medium")
PIPER_VOICE_ES = os.environ.get("PIPER_VOICE_ES", "es_ES-davefx-medium")
PIPER_VOICES_DIR = str(Path(__file__).parent.parent.parent / "voices")
PIPER_TIMEOUT = 30


def synthesize_speech(text: str, lang: Literal["en", "es"] = "en") -> bytes:
    """Synthesize speech for `text` and return WAV bytes."""
    voice = PIPER_VOICE_EN if lang == "en" else PIPER_VOICE_ES
    voice_path = Path(PIPER_VOICES_DIR) / f"{voice}.onnx"
    if not voice_path.is_file():
        raise RuntimeError(
            f"Piper voice '{voice}' not found in {PIPER_VOICES_DIR}. "
            f"Run: python -m piper.download_voices {voice} --data-dir {PIPER_VOICES_DIR}"
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / f"{uuid.uuid4().hex}.wav"
        cmd = [
            sys.executable, "-m", "piper",
            "-m", voice,
            "--data-dir", PIPER_VOICES_DIR,
            "-f", str(out_path),
            "--", text,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=PIPER_TIMEOUT, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
            logger.error("piper failed: %s", stderr)
            raise RuntimeError("Speech synthesis failed: piper returned an error.") from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("piper timed out after %ds", PIPER_TIMEOUT)
            raise RuntimeError("Speech synthesis failed: piper timed out.") from exc

        if not out_path.is_file():
            raise RuntimeError("Speech synthesis failed: piper produced no output file.")
        return out_path.read_bytes()
