"""J6 — End-to-end latency measurement.

Times: question generation per lesson, answer evaluation, review grading.
(Course generation and TTS latency are measured separately as they can take
minutes — the script prints timing for stages it can reach without a
full-app server.)

Usage:
    cd backend
    uv run python -m eval.j6_latency
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

N_TRIALS = 3


def measure(label: str, fn, *args, **kwargs) -> dict:
    times = []
    error = None
    for _ in range(N_TRIALS):
        t0 = time.perf_counter()
        try:
            fn(*args, **kwargs)
            times.append(time.perf_counter() - t0)
        except Exception as exc:
            error = str(exc)
            break
    if times:
        mean = sum(times) / len(times)
        std = (sum((t - mean) ** 2 for t in times) / len(times)) ** 0.5
        print(f"  {label}: mean={mean:.2f}s std={std:.2f}s (n={len(times)})")
        return {"label": label, "mean_s": round(mean, 3), "std_s": round(std, 3), "n": len(times)}
    else:
        print(f"  {label}: FAILED — {error}")
        return {"label": label, "error": error}


def run() -> dict:
    from app.services.answer_evaluator import embed, evaluate_answer

    results = []
    print("J6 — Latency benchmark")
    print(f"Trials per stage: {N_TRIALS}\n")

    print("1. Embedding (reference answer):")
    ref_text = "A list is an ordered, mutable collection of items in Python."
    results.append(measure("embed_reference", embed, ref_text))

    print("\n2. Answer evaluation (embedding path):")
    ref_emb = embed(ref_text)
    user_ans_correct = "An ordered, changeable sequence of items"
    user_ans_wrong = "A database schema"
    results.append(measure(
        "evaluate_answer_correct",
        evaluate_answer,
        question_text="What is a Python list?",
        user_answer=user_ans_correct,
        reference_answer=ref_text,
        reference_embedding=ref_emb,
    ))
    results.append(measure(
        "evaluate_answer_wrong",
        evaluate_answer,
        question_text="What is a Python list?",
        user_answer=user_ans_wrong,
        reference_answer=ref_text,
        reference_embedding=ref_emb,
    ))

    print("\n3. Content parser:")
    from app.services.content_parser import parse_lesson_body
    import json as _json
    sample = _json.dumps({
        "key_concepts": [{"name": "int", "definition": "Whole number", "example": "x = 1"}],
        "worked_example": "Step 1: x = 10\nStep 2: print(x)",
        "common_pitfalls": ["Off-by-one errors"],
        "practice_prompts": ["Write a loop"],
    })
    results.append(measure("content_parser", parse_lesson_body, sample))

    summary = {
        "timestamp": datetime.now().isoformat(),
        "n_trials": N_TRIALS,
        "stages": results,
    }

    out_path = RESULTS_DIR / f"j6_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nResults written to {out_path}")
    return summary


if __name__ == "__main__":
    run()
