"""Static serving for generated audio.

GET /audio/{filename} — serves WAV files from data/narration/.

The router carries the auth gate, so every request here is authenticated. That
is not the same as authorised: filenames encode which lesson or course the audio
belongs to, and this checks that the caller owns it.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.ownership import get_owned_course, get_owned_lesson
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/audio", tags=["audio"])

_NARRATION_DIR = Path(__file__).parent.parent.parent / "data" / "narration"

_DRILL_PREFIX = "drill_"


def _check_ownership(filename: str, db: Session, user_id: str) -> None:
    """Two filename shapes, both self-describing. Anything else is rejected.

    Narration is `{lesson_id}_{content_hash}.wav` and drills are
    `drill_{course_id}_{digest}.wav`. UUIDs contain '-' and never '_', so
    splitting on '_' is unambiguous.
    """
    stem = filename[: -len(".wav")] if filename.endswith(".wav") else filename

    if stem.startswith(_DRILL_PREFIX):
        parts = stem.split("_")
        # drill_<course-uuid>_<digest>
        if len(parts) != 3:
            raise HTTPException(status_code=404, detail="Audio file not found")
        get_owned_course(db, parts[1], user_id)
        return

    lesson_id, sep, _digest = stem.rpartition("_")
    if not sep or not lesson_id:
        raise HTTPException(status_code=404, detail="Audio file not found")
    get_owned_lesson(db, lesson_id, user_id)


@router.get("/{filename}")
def serve_audio(
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    # Path(...).name collapses traversal, absolute paths and separators in one
    # check that cannot be reasoned wrong.
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    _check_ownership(filename, db, user.id)

    file_path = _NARRATION_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(file_path), media_type="audio/wav")
