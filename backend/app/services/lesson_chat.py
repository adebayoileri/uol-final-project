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


def _build_context(lesson_description: str, lesson_title: str) -> str:
    """Build a compact context block from lesson content (max ~2000 chars)."""
    parts = [f"Lesson: {lesson_title}"]
    parsed = parse_lesson_body(lesson_description)
    if parsed["is_structured"]:
        if parsed["key_concepts"]:
            parts.append("Key concepts: " + "; ".join(
                f"{c['name']} — {c['definition']}"
                for c in parsed["key_concepts"][:5]
            ))
        if parsed["worked_example"]:
            parts.append("Worked example: " + parsed["worked_example"][:400])
        if parsed["common_pitfalls"]:
            parts.append("Common pitfalls: " + "; ".join(parsed["common_pitfalls"][:3]))
    else:
        parts.append(lesson_description[:600])
    return "\n".join(parts)[:2000]


def stream_chat(
    lesson_title: str,
    lesson_description: str,
    history: list[dict],
    message: str,
) -> Iterator[str]:
    """Yield streaming tokens as plain text chunks (SSE data payloads)."""
    context = _build_context(lesson_description, lesson_title)
    system = f"{_CHAT_SYSTEM}\n\n---\nLesson content:\n{context}\n---"

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:  # keep last 10 turns to stay within context
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
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
