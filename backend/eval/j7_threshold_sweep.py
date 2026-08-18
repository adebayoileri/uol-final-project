"""J7 — Are the chosen answer-grading thresholds the right ones?

The preliminary report justified the 0.35 / 0.65 cosine band by argument. This
measures it. Every pair in the J3 fixture already carries the embedding score
the live evaluator produced, so alternative decision rules can be replayed over
the same 50 labelled answers without re-running the model.

Three questions:
  1. What is the best a single threshold can do?           (embedding only)
  2. What does the two-threshold band buy over that?       (hybrid)
  3. Are 0.35 / 0.65 the right band, or did I guess well?  (grid search)

Usage:  cd backend && uv run python -m eval.j7_threshold_sweep
"""

import glob
import json
from datetime import datetime
from pathlib import Path

RESULTS = Path(__file__).parent / "results"


def prf(pred, exp):
    tp = sum(1 for p, e in zip(pred, exp) if p == e == "correct")
    fp = sum(1 for p, e in zip(pred, exp) if p == "correct" and e != "correct")
    fn = sum(1 for p, e in zip(pred, exp) if p != "correct" and e == "correct")
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return round(prec, 3), round(rec, 3), round(f1, 3)


def run():
    latest = sorted(glob.glob(str(RESULTS / "j3_*.json")))[-1]
    details = json.load(open(latest))["details"]
    scores = [d["score"] for d in details]
    exp = [d["expected"] for d in details]
    # What the live hybrid evaluator actually decided, LLM escalations included.
    hybrid = [d["predicted"] for d in details]

    out = {"timestamp": datetime.now().isoformat(), "n": len(details), "source": latest}

    # 1 — single threshold, embedding only
    single = []
    t = 0.20
    while t <= 0.80001:
        pred = ["correct" if s >= t else "incorrect" for s in scores]
        p, r, f = prf(pred, exp)
        single.append({"threshold": round(t, 2), "precision": p, "recall": r, "f1": f})
        t += 0.05
    best_single = max(single, key=lambda r: r["f1"])
    out["single_threshold"] = single
    out["best_single_threshold"] = best_single

    # 2 — the live hybrid result over the same pairs
    p, r, f = prf(hybrid, exp)
    out["hybrid_live"] = {"precision": p, "recall": r, "f1": f}
    out["escalation_rate"] = round(
        sum(1 for d in details if d["signal"] != "embedding") / len(details), 3
    )

    # 3 — grid search over the band, treating the escalated middle as an oracle
    #     (the live LLM verdict for those pairs, which is what actually happens)
    llm = {round(d["score"], 6): d["predicted"] for d in details}
    grid = []
    lo = 0.20
    while lo <= 0.50001:
        hi = lo + 0.05
        while hi <= 0.85001:
            pred = []
            for s, d in zip(scores, details):
                if s <= lo:
                    pred.append("incorrect")
                elif s >= hi:
                    pred.append("correct")
                else:
                    pred.append(d["predicted"])          # escalated
            band = sum(1 for s in scores if lo < s < hi)
            p2, r2, f2 = prf(pred, exp)
            grid.append({"low": round(lo, 2), "high": round(hi, 2), "f1": f2,
                         "precision": p2, "recall": r2, "escalated": band})
            hi += 0.05
        lo += 0.05
    best = max(grid, key=lambda r: (r["f1"], -r["escalated"]))
    chosen = next(r for r in grid if r["low"] == 0.35 and r["high"] == 0.65)
    out["grid"] = grid
    out["best_band"] = best
    out["chosen_band"] = chosen

    print(f"J7 — threshold sweep over {len(details)} labelled pairs\n")
    print("1. Best single threshold (embedding only, no LLM):")
    print(f"   t={best_single['threshold']}  P={best_single['precision']} "
          f"R={best_single['recall']}  F1={best_single['f1']}")
    print("\n2. Live hybrid evaluator (0.35 / 0.65 + LLM judge):")
    print(f"   P={out['hybrid_live']['precision']} R={out['hybrid_live']['recall']} "
          f"F1={out['hybrid_live']['f1']}   escalated {out['escalation_rate']*100:.0f}% of answers")
    print("\n3. Grid search over the escalation band:")
    print(f"   best   low={best['low']} high={best['high']}  F1={best['f1']}  "
          f"escalated {best['escalated']}/{len(details)}")
    print(f"   chosen low={chosen['low']} high={chosen['high']}  F1={chosen['f1']}  "
          f"escalated {chosen['escalated']}/{len(details)}")
    print("\n   top bands by F1 then fewest escalations:")
    for r in sorted(grid, key=lambda r: (-r["f1"], r["escalated"]))[:6]:
        print(f"     {r['low']:.2f}-{r['high']:.2f}  F1={r['f1']:.3f}  esc={r['escalated']}")

    path = RESULTS / f"j7_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"\nResults written to {path}")
    return out


if __name__ == "__main__":
    run()
