"""J4 — FSRS simulation.

Simulates 100 synthetic cards reviewed daily for 30 days.
Tracks: intervals, state distribution, retention rate at each simulated day.

Usage:
    cd backend
    uv run python -m eval.j4_fsrs_simulation
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fsrs import Card, Rating, Scheduler

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

N_CARDS = 100
DAYS = 30


def run() -> dict:
    scheduler = Scheduler(enable_fuzzing=False)
    cards = [Card() for _ in range(N_CARDS)]
    start = datetime.now(timezone.utc)

    daily_stats = []
    all_intervals: list[float] = []

    for day in range(DAYS):
        current_time = start + timedelta(days=day)
        reviewed_today = 0
        due_today = 0

        updated_cards = []
        for card in cards:
            due = card.due
            if due <= current_time:
                due_today += 1
                updated, _log = scheduler.review_card(card, Rating.Good, review_datetime=current_time)
                updated_cards.append(updated)
                reviewed_today += 1
                if updated.stability:
                    all_intervals.append(updated.stability)
            else:
                updated_cards.append(card)

        cards = updated_cards

        state_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for card in cards:
            state_counts[int(card.state)] = state_counts.get(int(card.state), 0) + 1

        avg_stability = (
            sum(c.stability for c in cards if c.stability)
            / max(sum(1 for c in cards if c.stability), 1)
        )

        # Estimate retention using R = e^(-t/S) for cards in Review state
        # Use stability and time since last review
        retained = 0
        total_reviewable = 0
        for card in cards:
            if card.stability and card.last_review:
                elapsed = (current_time - card.last_review).days
                # Retention formula from FSRS
                retention = 0.9 ** (elapsed / card.stability) if card.stability > 0 else 0.0
                retained += retention
                total_reviewable += 1

        retention_rate = retained / total_reviewable if total_reviewable > 0 else 1.0

        daily_stats.append({
            "day": day,
            "due_today": due_today,
            "reviewed_today": reviewed_today,
            "avg_stability": round(avg_stability, 2),
            "state_distribution": state_counts,
            "estimated_retention": round(retention_rate, 3),
        })

        if day % 5 == 0:
            print(f"Day {day:2d}: due={due_today:3d}, avg_stability={avg_stability:.1f}d, retention={retention_rate:.1%}")

    final_stabilities = sorted([c.stability for c in cards if c.stability])
    summary = {
        "timestamp": datetime.now().isoformat(),
        "config": {"n_cards": N_CARDS, "days": DAYS, "rating": "Good (3) always"},
        "daily_stats": daily_stats,
        "final_summary": {
            "mean_stability": round(sum(final_stabilities) / len(final_stabilities), 2) if final_stabilities else 0,
            "median_stability": final_stabilities[len(final_stabilities) // 2] if final_stabilities else 0,
            "state_distribution": {
                str(k): sum(1 for c in cards if int(c.state) == k) for k in [0, 1, 2, 3]
            },
            "all_review_intervals_sample": [round(x, 2) for x in sorted(all_intervals)[:30]],
        },
    }

    out_path = RESULTS_DIR / f"j4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSimulation complete. Results written to {out_path}")
    return summary


if __name__ == "__main__":
    run()
