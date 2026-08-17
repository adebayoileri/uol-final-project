"""AI assistant chat for lessons.

POST /lessons/{id}/chat      — streaming SSE chat response
GET  /lessons/{id}/chat/history — persisted message history
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.ownership import get_owned_lesson
from app.database import get_db
from app.models import Lesson, User
from app.services.lesson_chat import stream_chat

router = APIRouter(prefix="/lessons", tags=["chat"])


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []


@router.post("/{lesson_id}/chat")
def chat(
    lesson_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    lesson = get_owned_lesson(db, lesson_id, user.id)

    history = [{"role": m.role, "content": m.content} for m in body.history]

    # Buffer the full response to persist after streaming
    full_response: list[str] = []

    def _generate():
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO lesson_chat_messages (id, lesson_id, role, content, created_at)
                VALUES (:id, :lesson_id, :role, :content, :now)
            """),
            {"id": msg_id, "lesson_id": lesson_id, "role": "user", "content": body.message, "now": now},
        )
        db.commit()

        for chunk in stream_chat(
            lesson.title,
            lesson.description,
            history,
            body.message,
            content_json=lesson.content_json,
        ):
            yield chunk
            # Accumulate non-control chunks
            if chunk.startswith("data: {"):
                try:
                    import json
                    data = json.loads(chunk[6:])
                    if "token" in data:
                        full_response.append(data["token"])
                except Exception:
                    pass

        # Persist assistant response after stream ends
        assistant_text = "".join(full_response)
        if assistant_text:
            asst_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO lesson_chat_messages (id, lesson_id, role, content, created_at)
                    VALUES (:id, :lesson_id, :role, :content, :now)
                """),
                {
                    "id": asst_id,
                    "lesson_id": lesson_id,
                    "role": "assistant",
                    "content": assistant_text,
                    "now": datetime.now(timezone.utc),
                },
            )
            db.commit()

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/{lesson_id}/chat/history")
def chat_history(
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    get_owned_lesson(db, lesson_id, user.id)

    rows = db.execute(
        text("""
            SELECT role, content, created_at
            FROM lesson_chat_messages
            WHERE lesson_id = :id
            ORDER BY created_at ASC
        """),
        {"id": lesson_id},
    ).fetchall()

    return [
        {"role": r.role, "content": r.content, "created_at": r.created_at}
        for r in rows
    ]
