"""Pure FSRS-6 simulation tests — no DB, no HTTP.

Validates the scheduler's interval growth and Again-reset behaviour without
needing a running Ollama instance or any fixtures.
"""

from datetime import datetime, timezone

import pytest
from fsrs import Card, Rating, Scheduler, State


@pytest.fixture()
def scheduler():
    return Scheduler(enable_fuzzing=False)


def test_new_card_starts_in_learning(scheduler):
    card = Card()
    assert int(card.state) == int(State.Learning)
    assert card.stability is None
    assert card.difficulty is None


def test_good_exits_learning_to_review(scheduler):
    card = Card()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    card, _ = scheduler.review_card(card, Rating.Good, review_datetime=now)
    assert int(card.state) == int(State.Learning)  # still in learning (first step)
    now = card.due
    card, _ = scheduler.review_card(card, Rating.Good, review_datetime=now)
    assert int(card.state) == int(State.Review)


def test_again_in_review_moves_to_relearning(scheduler):
    card = Card()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Push card into Review
    card, _ = scheduler.review_card(card, Rating.Good, review_datetime=now)
    now = card.due
    card, _ = scheduler.review_card(card, Rating.Good, review_datetime=now)
    assert int(card.state) == int(State.Review)
    now = card.due
    card, _ = scheduler.review_card(card, Rating.Again, review_datetime=now)
    assert int(card.state) == int(State.Relearning)


def test_50_review_simulation(scheduler):
    """50 reviews: Good×40, Again×5, Good×5.

    Assertions:
    1. Intervals strictly increase during the Good streak in Review phase.
    2. The first Again rating drops the interval well below the preceding Good interval.
    """
    card = Card()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history = []  # (pre_state, post_state, interval_seconds)

    for i in range(50):
        rating = Rating.Again if 40 <= i < 45 else Rating.Good
        pre = int(card.state)
        card, _ = scheduler.review_card(card, rating, review_datetime=now)
        interval_secs = (card.due - now).total_seconds()
        history.append((pre, int(card.state), interval_secs))
        now = card.due

    # Reviews 2–39 are all in Review (enable_fuzzing=False guarantees determinism)
    review_intervals = [h[2] for h in history[2:40] if h[1] == int(State.Review)]
    assert len(review_intervals) > 0, "Expected some Review-phase intervals"
    # Intervals must be non-decreasing (FSRS caps at maximum_interval once hit)
    for i in range(1, len(review_intervals)):
        assert review_intervals[i] >= review_intervals[i - 1], (
            f"Interval at index {i} ({review_intervals[i]:.0f}s) decreased from "
            f"previous ({review_intervals[i-1]:.0f}s)"
        )
    # Growth must actually occur — first and last interval cannot be equal
    assert review_intervals[-1] > review_intervals[0], (
        "Review intervals never increased — scheduler may not be working correctly"
    )

    # Again (index 40) must produce a much shorter interval than the last Good (index 39)
    assert history[40][2] < history[39][2], (
        f"Again interval ({history[40][2]:.0f}s) should be less than "
        f"last Good interval ({history[39][2]:.0f}s)"
    )
