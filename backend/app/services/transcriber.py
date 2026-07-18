"""Speech-to-text via whisper.cpp's `whisper-cli` binary.

Invoked as a subprocess rather than a Python binding — mirrors how the
project shells out to Ollama over HTTP rather than embedding an LLM runtime.
Transcript is read from the `-otxt` output file rather than parsed from
stdout/stderr, since whisper.cpp interleaves diagnostic logging with the
transcript unpredictably across builds (see docs/decisions.md).
"""

import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent.parent.parent / "models"
WHISPER_MODEL_PATH = os.environ.get(
    "WHISPER_MODEL_PATH",
    str(_MODELS_DIR / "ggml-base.en.bin"),
)
WHISPER_MULTILINGUAL_MODEL_PATH = os.environ.get(
    "WHISPER_MULTILINGUAL_MODEL_PATH",
    str(_MODELS_DIR / "ggml-base.bin"),
)
WHISPER_BIN = "whisper-cli"
FFMPEG_BIN = "ffmpeg"
WHISPER_TIMEOUT = 60
# Formats whisper-cli accepts natively without conversion
_WHISPER_NATIVE = {".flac", ".mp3", ".ogg", ".wav"}


def _to_wav(src: str, tmp_dir: str) -> str:
    """Convert src to 16 kHz mono WAV using ffmpeg. Returns the WAV path."""
    wav_path = str(Path(tmp_dir) / "converted.wav")
    cmd = [FFMPEG_BIN, "-y", "-i", src, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        logger.error("ffmpeg conversion failed: %s", stderr)
        raise RuntimeError("Transcription failed: audio conversion error.") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("Transcription failed: ffmpeg is not installed.") from exc
    return wav_path


def transcribe_audio(file_path: str, language: str = "en") -> dict[str, Any]:
    """Transcribe an audio file and return {"text": str, "duration_seconds": float}.

    Uses the multilingual model for non-English languages and falls back to it
    even for English when the English-only model is absent.
    """
    if language != "en" or not Path(WHISPER_MODEL_PATH).is_file():
        model_path = WHISPER_MULTILINGUAL_MODEL_PATH
    else:
        model_path = WHISPER_MODEL_PATH

    if not Path(model_path).is_file():
        raise RuntimeError(f"Whisper model not found at {model_path}.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # whisper-cli only accepts flac/mp3/ogg/wav; convert anything else via ffmpeg
        if Path(file_path).suffix.lower() not in _WHISPER_NATIVE:
            file_path = _to_wav(file_path, tmp_dir)

        out_basename = str(Path(tmp_dir) / uuid.uuid4().hex)
        cmd = [
            WHISPER_BIN,
            "-m", model_path,
            "-f", file_path,
            "-l", language,
            "-nt",
            "-otxt",
            "-of", out_basename,
        ]
        start = time.monotonic()
        try:
            subprocess.run(cmd, capture_output=True, timeout=WHISPER_TIMEOUT, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
            logger.error("whisper-cli failed: %s", stderr)
            raise RuntimeError("Transcription failed: whisper-cli returned an error.") from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("whisper-cli timed out after %ds", WHISPER_TIMEOUT)
            raise RuntimeError("Transcription failed: whisper-cli timed out.") from exc
        except FileNotFoundError as exc:
            logger.error("whisper-cli binary not found on PATH")
            raise RuntimeError("Transcription failed: whisper-cli is not installed.") from exc
        elapsed = time.monotonic() - start

        out_path = Path(f"{out_basename}.txt")
        if not out_path.is_file():
            raise RuntimeError("Transcription failed: whisper-cli produced no output file.")
        text = out_path.read_text(encoding="utf-8").strip()

    logger.info("whisper-cli transcribed %s in %.2fs", file_path, elapsed)
    return {"text": text, "duration_seconds": elapsed}
