"""Pulling JSON back out of a model response.

Even with Ollama's `format: "json"` set, responses arrive wrapped in code
fences or trailed by an apology often enough that every caller needs this.
Lifted out of lesson_enricher when a second generator needed the same scanner —
question_generator already carries a near-identical one for top-level arrays,
and a third copy was the wrong direction.
"""

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*")


def extract_json_object(raw: str) -> dict[str, Any]:
    """Pull the first balanced JSON object out of a model response.

    Scans for the matching brace rather than taking the last `}` in the string,
    so trailing commentary after the object does not break the parse.
    """
    cleaned = _FENCE_RE.sub("", raw).strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")

    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    break
    return json.loads(cleaned)
