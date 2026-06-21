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

WHISPER_MODEL_PATH = os.environ.get(
    "WHISPER_MODEL_PATH",
    str(Path(__file__).parent.parent.parent / "models" / "ggml-base.en.bin"),
)
WHISPER_BIN = "whisper-cli"
WHISPER_TIMEOUT = 60


def transcribe_audio(file_path: str, language: str = "en") -> dict[str, Any]:
    """Transcribe an audio file and return {"text": str, "duration_seconds": float}."""
    if not Path(WHISPER_MODEL_PATH).is_file():
        raise RuntimeError(f"Whisper model not found at {WHISPER_MODEL_PATH}.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_basename = str(Path(tmp_dir) / uuid.uuid4().hex)
        cmd = [
            WHISPER_BIN,
            "-m", WHISPER_MODEL_PATH,
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
