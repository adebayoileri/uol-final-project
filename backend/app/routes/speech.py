import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.schemas import PronunciationCheckResponse, TranscriptionResponse, TTSRequest, WordDiffItem
from app.services.transcriber import transcribe_audio
from app.services.tts import synthesize_speech
from app.services.word_diff import compute_word_diff

logger = logging.getLogger(__name__)
router = APIRouter(tags=["speech"])


def _save_upload(upload: UploadFile, tmp_dir: str) -> str:
    suffix = Path(upload.filename or "audio.wav").suffix or ".wav"
    dest = Path(tmp_dir) / f"upload{suffix}"
    dest.write_bytes(upload.file.read())
    return str(dest)


@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe an uploaded audio file via whisper-cli."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = _save_upload(audio, tmp_dir)
        try:
            result = transcribe_audio(file_path)
        except RuntimeError as exc:
            logger.error("Transcription failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Transcription is temporarily unavailable. Please try again.",
            ) from exc

    return TranscriptionResponse(text=result["text"], duration_seconds=result["duration_seconds"])


@router.post("/pronunciation-check", response_model=PronunciationCheckResponse)
def pronunciation_check(
    audio: UploadFile = File(...),
    expected_text: str = Form(...),
) -> PronunciationCheckResponse:
    """Transcribe an uploaded audio file and diff it against the expected text."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = _save_upload(audio, tmp_dir)
        try:
            result = transcribe_audio(file_path)
        except RuntimeError as exc:
            logger.error("Transcription failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Transcription is temporarily unavailable. Please try again.",
            ) from exc

    transcribed_text = result["text"]
    diff = compute_word_diff(expected_text, transcribed_text)

    expected_word_count = len(expected_text.split())
    matched = sum(1 for d in diff if d["op"] == "match")
    accuracy = matched / expected_word_count if expected_word_count else 0.0

    return PronunciationCheckResponse(
        expected_text=expected_text,
        transcribed_text=transcribed_text,
        diff=[WordDiffItem(**d) for d in diff],
        accuracy=accuracy,
    )


@router.post("/tts")
def tts(body: TTSRequest) -> Response:
    """Synthesize speech for the given text via piper."""
    try:
        wav_bytes = synthesize_speech(body.text, body.lang)
    except RuntimeError as exc:
        logger.error("Speech synthesis failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Speech synthesis is temporarily unavailable. Please try again.",
        ) from exc

    return Response(content=wav_bytes, media_type="audio/wav")
