"""J5 — Chat relevance evaluation (manual scoring).

Calls POST /lessons/{id}/chat for 10 fixed (lesson_id, question) pairs and
prints side-by-side for manual hand-scoring.

Usage:
    cd backend
    # With the server running:
    uv run python -m eval.j5_chat_relevance --base-url http://localhost:8000

NOTE: This script requires a running server and populated database.
      Results are printed for manual annotation; not automated.
"""

import argparse
import json
import sys
from pathlib import Path

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "chat_questions.jsonl"

# Inline defaults if fixture file not present
DEFAULT_QUESTIONS = [
    {"question": "What is the main topic of this lesson?"},
    {"question": "Explain the first key concept in simple terms."},
    {"question": "What common mistakes should I avoid?"},
    {"question": "Give me an example of the worked example but with different numbers."},
    {"question": "Why is this topic important?"},
    {"question": "How does this relate to what I learned in previous lessons?"},
    {"question": "What would happen if I skipped this lesson?"},
    {"question": "Can you test me on the key concepts?"},
    {"question": "What's the most difficult part of this topic?"},
    {"question": "Summarise this lesson in three bullet points."},
]


def run(base_url: str, lesson_id: str | None = None):
    import httpx

    # Try to get the first available lesson if none specified
    if not lesson_id:
        try:
            courses = httpx.get(f"{base_url}/courses", timeout=10).json()
            if not courses:
                print("No courses found. Generate a course first.")
                return
            course_id = courses[0]["id"]
            course = httpx.get(f"{base_url}/courses/{course_id}", timeout=10).json()
            lesson_id = course["modules"][0]["lessons"][0]["id"]
            print(f"Using lesson: {lesson_id}")
        except Exception as exc:
            print(f"Could not auto-select lesson: {exc}")
            return

    questions = DEFAULT_QUESTIONS
    if FIXTURES_PATH.is_file():
        questions = [json.loads(l) for l in FIXTURES_PATH.read_text().splitlines() if l.strip()]

    print("\n" + "=" * 60)
    print("CHAT RELEVANCE EVALUATION — Manual scoring (1=irrelevant, 5=perfect)")
    print("=" * 60 + "\n")

    for i, item in enumerate(questions[:10], 1):
        q = item["question"]
        print(f"[{i}/10] Q: {q}")

        try:
            with httpx.Client(timeout=60) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/lessons/{lesson_id}/chat",
                    json={"message": q, "history": []},
                    headers={"Accept": "text/event-stream"},
                ) as resp:
                    tokens = []
                    for line in resp.iter_lines():
                        if line.startswith("data: ") and not line.endswith("[DONE]"):
                            try:
                                data = json.loads(line[6:])
                                if "token" in data:
                                    tokens.append(data["token"])
                            except Exception:
                                pass
                    answer = "".join(tokens).strip()
        except Exception as exc:
            answer = f"ERROR: {exc}"

        print(f"    A: {answer[:300]}{'…' if len(answer) > 300 else ''}")
        print(f"    Score (1-5): ___")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--lesson-id", default=None)
    args = parser.parse_args()
    run(args.base_url, args.lesson_id)
