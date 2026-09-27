"""Runner: executes J4, J6 and J8 automatically (J1 needs Ollama, J3 needs Ollama,
J2/J5 need manual scoring or a running server — those print instructions).

Usage:
    cd backend
    uv run python scripts/run_all_evals.py [--all]

With --all: also runs J1 (Ollama) and J3 (Ollama + embeddings). Without it,
only J4 (FSRS sim), J6 (latency) and J8 (clue leak rate) run, which work offline.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path(__file__).parent.parent / "eval" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_phase(name: str, fn) -> dict | None:
    print(f"\n{'='*60}")
    print(f"Running {name}…")
    print("=" * 60)
    try:
        result = fn()
        print(f"✓ {name} complete")
        return result
    except Exception as exc:
        print(f"✗ {name} FAILED: {exc}")
        return {"error": str(exc)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Also run J1 and J3 (requires Ollama)")
    args = parser.parse_args()

    results: dict = {"timestamp": datetime.now().isoformat(), "phases": {}}

    from eval.j4_fsrs_simulation import run as j4
    from eval.j6_latency import run as j6

    results["phases"]["J4_fsrs"] = run_phase("J4 — FSRS simulation", j4)
    results["phases"]["J6_latency"] = run_phase("J6 — Latency", j6)

    # Reads the database only, so it belongs with the offline phases rather
    # than behind --all.
    from eval.j8_clue_leak_rate import run as j8

    results["phases"]["J8_clue_leak_rate"] = run_phase("J8 — Clue leak rate", j8)

    if args.all:
        from eval.j1_content_quality import run as j1
        from eval.j3_answer_checker_f1 import run as j3
        results["phases"]["J1_content"] = run_phase("J1 — Content quality", j1)
        results["phases"]["J3_f1"] = run_phase("J3 — Answer checker F1", j3)
    else:
        print("\nSkipping J1 (needs Ollama) and J3 (needs Ollama). Run with --all to include.")
        print("J2 (RAG ablation) skipped — RAG not implemented.")
        print("J5 (chat relevance) requires a running server — run separately: uv run python -m eval.j5_chat_relevance")

    summary_path = RESULTS_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    lines = [
        f"# Evaluation Summary\n\nGenerated: {results['timestamp']}\n",
    ]
    for phase_name, phase_result in results["phases"].items():
        lines.append(f"## {phase_name}\n")
        if isinstance(phase_result, dict) and "error" not in phase_result:
            lines.append("```json")
            lines.append(json.dumps(phase_result.get("aggregate") or phase_result.get("overall") or phase_result.get("final_summary") or {}, indent=2))
            lines.append("```\n")
        else:
            lines.append(f"Failed: {phase_result}\n")

    summary_path.write_text("\n".join(lines))
    print(f"\n\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
