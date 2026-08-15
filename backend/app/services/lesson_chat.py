"""Streaming chat grounded in lesson content.

Uses Ollama's streaming API (stream: true) via httpx, yielding each token
as an SSE-compatible string. The caller (FastAPI route) wraps this in a
StreamingResponse — no async/await anywhere; the route stays sync.
"""

import json
import logging
import os
from typing import Iterator

import httpx

from app.services.content_parser import parse_lesson_body

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = 30.0

_CHAT_SYSTEM = (
    "You are a helpful tutor. Answer questions about the lesson content concisely and clearly. "
    "Stay grounded in the material provided. If the question is unrelated to the lesson, "
    "gently redirect the student back to the topic."
)


def _build_context(
    lesson_description: str,
    lesson_title: str,
    content_json: str | None = None,
) -> str:
    """Build the grounding block from lesson content (max ~4000 chars).

    Prose and structured content are both included — both are real grounding,
    so there is no reason to withhold one in favour of the other.
    """
    parts = [f"Lesson: {lesson_title}"]

    prose = (lesson_description or "").strip()
    if prose:
        parts.append(prose[:600])

    parsed = parse_lesson_body(content_json or "")
    if parsed["key_concepts"]:
        parts.append("Key concepts: " + "; ".join(
            f"{c['name']} — {c['definition']}"
            for c in parsed["key_concepts"][:5]
        ))
    if parsed["worked_example"]:
        # 400 chars cut a real 4-step example off after step one.
        parts.append("Worked example: " + parsed["worked_example"][:1200])
    if parsed["common_pitfalls"]:
        parts.append("Common pitfalls: " + "; ".join(parsed["common_pitfalls"][:3]))

    return "\n".join(parts)[:4000]


def stream_chat(
    lesson_title: str,
    lesson_description: str,
    history: list[dict],
    message: str,
    content_json: str | None = None,
) -> Iterator[str]:
    """Yield streaming tokens as plain text chunks (SSE data payloads)."""
    context = _build_context(lesson_description, lesson_title, content_json)
    system = f"{_CHAT_SYSTEM}\n\n---\nLesson content:\n{context}\n---"

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:  # keep last 10 turns to stay within context
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        # Load-bearing: a 4000-char system context plus ten history turns
        # exceeds Ollama's default runtime window, and overflow evicts from the
        # START of the prompt — exactly where the lesson content sits. Without
        # this the tutor looks grounded in code and is ungrounded at runtime.
        "options": {"num_ctx": 8192},
    }

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        break
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP error: %s", exc)
        yield f"data: {json.dumps({'error': f'Ollama error {exc.response.status_code}'})}\n\n"
    except httpx.RequestError as exc:
        logger.error("Ollama unreachable: %s", exc)
        yield f"data: {json.dumps({'error': 'Cannot reach Ollama'})}\n\n"

    yield "data: [DONE]\n\n"
