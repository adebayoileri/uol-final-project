"""Answer evaluation service.

Embeds the user's answer and compares it to the stored reference embedding via
cosine similarity. When the score falls in an ambiguous grey zone, an LLM call
is made to produce a final verdict.

Thresholds (see docs/decisions.md for full rationale):
  score >= 0.65  → correct  (embedding only)
  score <= 0.35  → incorrect (embedding only)
  otherwise      → LLM fallback (embedding+llm)
"""

import json
import logging
import os
from typing import Any

import httpx
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

CORRECT_THRESHOLD = 0.65
INCORRECT_THRESHOLD = 0.35

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30"))

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> list[float]:
    return _get_model().encode(text).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def _llm_verify(question_text: str, user_answer: str, reference_answer: str) -> bool:
    """Ask the LLM if the student's answer is essentially correct.

    Returns True on any parse failure so borderline answers lean generous.
    """
    prompt = (
        "You are evaluating a student answer. Reply with ONLY JSON: "
        '{"correct": true} or {"correct": false}. No other text.\n\n'
        f"Question: {question_text}\n"
        f"Reference answer: {reference_answer}\n"
        f"Student answer: {user_answer}\n\n"
        "Is the student's answer essentially correct, even if worded differently?"
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
        result = json.loads(response.json()["response"])
        return bool(result.get("correct", True))
    except Exception as exc:
        logger.warning("LLM verify failed, defaulting to True: %s", exc)
        return True


def evaluate_answer(
    question_text: str,
    user_answer: str,
    reference_answer: str,
    reference_embedding: list[float],
) -> dict[str, Any]:
    """Evaluate a free-text answer and return verdict, score, and signal used."""
    user_embedding = embed(user_answer)
    score = cosine_similarity(user_embedding, reference_embedding)

    if score >= CORRECT_THRESHOLD:
        return {"verdict": "correct", "score": score, "signal_used": "embedding"}
    if score <= INCORRECT_THRESHOLD:
        return {"verdict": "incorrect", "score": score, "signal_used": "embedding"}

    is_correct = _llm_verify(question_text, user_answer, reference_answer)
    return {
        "verdict": "correct" if is_correct else "incorrect",
        "score": score,
        "signal_used": "embedding+llm",
    }
