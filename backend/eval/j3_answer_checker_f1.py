"""J3 — Answer checker F1 evaluation.

Runs the semantic answer evaluator on 50 labelled (question, answer, expected_verdict) triples.
Computes precision, recall, F1 for the 'correct' class overall and per category.

Usage:
    cd backend
    uv run python -m eval.j3_answer_checker_f1
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.answer_evaluator import evaluate_answer, embed

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "answer_pairs.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def run() -> dict:
    pairs = []
    for line in FIXTURES_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            pairs.append(json.loads(line))

    print(f"Loaded {len(pairs)} pairs")

    per_category: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    overall = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    details = []

    for i, pair in enumerate(pairs):
        q = pair["question"]
        user_answer = pair["user_answer"]
        reference = pair["reference_answer"]
        expected = pair["expected_verdict"]
        category = pair.get("category", "unknown")

        print(f"  [{i+1}/{len(pairs)}] {q[:40]}…", end=" ", flush=True)

        try:
            ref_emb = embed(reference)
            result = evaluate_answer(
                question_text=q,
                user_answer=user_answer,
                reference_answer=reference,
                reference_embedding=ref_emb,
            )
            predicted = result["verdict"]
        except Exception as exc:
            print(f"ERROR: {exc}")
            details.append({"question": q, "error": str(exc)})
            continue

        print(f"predicted={predicted}, expected={expected}")
        details.append({
            "question": q,
            "category": category,
            "predicted": predicted,
            "expected": expected,
            "score": result.get("score"),
            "signal": result.get("signal_used"),
        })

        tp = int(predicted == "correct" and expected == "correct")
        fp = int(predicted == "correct" and expected == "incorrect")
        fn = int(predicted == "incorrect" and expected == "correct")
        tn = int(predicted == "incorrect" and expected == "incorrect")

        for counter in [overall, per_category[category]]:
            counter["tp"] += tp
            counter["fp"] += fp
            counter["fn"] += fn
            counter["tn"] += tn

    def f1(counts: dict) -> dict:
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1_score, 3),
            **counts,
        }

    summary = {
        "timestamp": datetime.now().isoformat(),
        "overall": f1(overall),
        "per_category": {cat: f1(counts) for cat, counts in per_category.items()},
        "details": details,
    }

    out_path = RESULTS_DIR / f"j3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))

    print(f"\nOverall F1: {summary['overall']['f1']}")
    print(f"Results written to {out_path}")
    return summary


if __name__ == "__main__":
    run()
