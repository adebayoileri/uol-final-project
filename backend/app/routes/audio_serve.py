"""Static serving for generated narration files.

GET /audio/{filename} — serves WAV files from data/narration/.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/audio", tags=["audio"])

_NARRATION_DIR = Path(__file__).parent.parent.parent / "data" / "narration"


@router.get("/{filename}")
def serve_audio(filename: str):
    # Reject path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = _NARRATION_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(file_path), media_type="audio/wav")
