"""What a listening clue is allowed to say.

A clue is the spoken half of the aural drill: the description the learner hears
before choosing which concept it describes. Its one hard invariant is negative —
**it must never contain the concept it describes, in any form** — and this
module is where that invariant lives.

The rule is not stylistic. `build_listen` originally spoke the concept's stored
`definition` verbatim, and definitions routinely open by naming their own term
("Overfitting is when a model…"), so the audio simply announced the answer. A
prompt asking the model to avoid the term is a request, not a guarantee: the
same model that wrote the definition will occasionally write the term back in.
Prompt and checker are therefore both required, and this is the checker.

Because the cost of a leak is a drill that tests nothing — the exact defect
`docs/decisions.md` already records for the ordering drill — the comparison is
deliberately loose about *form* and strict about *identity*: case, punctuation,
hyphenation, plurals and simple inflections all still count as naming the term.
The cost of a false positive is one dropped clue, surfaced to the learner as an
unavailable drill with a reason, which is the cheaper mistake by a wide margin.
"""

import logging
import re
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Bounds. The floor rejects a "clue" that is really just a fragment the learner
# cannot reason from; the ceiling rejects a paragraph, which costs TTS latency
# and attention without adding discriminative power. Both are prompt guidance
# the model can miss, so they are enforced here too.
MIN_CLUE_CHARS = 40
MAX_CLUE_CHARS = 400
# The concept count is 3–5 per lesson by prompt, so this is only a guard against
# a runaway response, not a real budget.
MAX_CLUES_PER_LESSON = 8

# Shortest common prefix before two tokens are treated as the same word. Six
# admits "threshold"/"thresholds" and "overfit"/"overfitting" while leaving
# unrelated short words alone ("rate" vs "ratings" shares only three).
MIN_SHARED_PREFIX = 6
# …and the prefix must also be most of the shorter token, so that a long word
# is not matched by a coincidental start ("classification" vs "class" shares
# four characters, well under this; "classification" vs "classify" shares seven
# of eight and does match).
MIN_PREFIX_RATIO = 0.6
# Tokens shorter than this are too generic to police individually; the full-name
# check still covers them when they are part of a multi-word term.
MIN_POLICED_TOKEN = 4
# Initialisms are only derived from terms of this many words or more, so that
# "Confusion Matrix" does not put "cm" out of bounds in unrelated prose.
MIN_WORDS_FOR_INITIALISM = 3

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    """Lowercased alphanumeric tokens, so hyphen and space spellings agree."""
    return _WORD_RE.findall(text.casefold())


def _same_word(a: str, b: str) -> bool:
    """Whether two tokens are the same word wearing different endings.

    Prefix comparison rather than a stemmer: the inflections that matter here
    are exactly the ones a stemmer is meant to collapse ("-s", "-es", "-ing",
    "-ed"), a prefix rule collapses those without a dependency, and it errs
    towards matching rather than missing — the correct direction for this check.
    """
    if a == b:
        return True
    if min(len(a), len(b)) < MIN_SHARED_PREFIX:
        return False
    shared = 0
    for left, right in zip(a, b):
        if left != right:
            break
        shared += 1
    return shared >= MIN_SHARED_PREFIX and shared >= MIN_PREFIX_RATIO * min(len(a), len(b))


def _contains_phrase(clue_tokens: list[str], name_tokens: list[str]) -> bool:
    """True when the term appears, however its words were separated.

    Two passes, because separators are not meaningful in the term but are in the
    clue. The first compares word-to-word, which keeps inflection matching tight
    for a multi-word term. The second joins a run of clue words and compares the
    result against the term joined, which is what catches a separator placed
    *inside* a one-word term — "over-fitting" tokenises to two words and would
    otherwise sail past the first pass while reading, to any learner, as
    "overfitting".
    """
    if not name_tokens or not clue_tokens:
        return False

    if len(name_tokens) <= len(clue_tokens):
        span = len(name_tokens)
        if any(
            all(
                _same_word(clue_tokens[i + offset], token)
                for offset, token in enumerate(name_tokens)
            )
            for i in range(len(clue_tokens) - span + 1)
        ):
            return True

    # One word longer than the term allows the extra token to be part of the
    # same word rather than a separate one.
    collapsed = "".join(name_tokens)
    for size in range(1, min(len(name_tokens) + 2, len(clue_tokens) + 1)):
        for i in range(len(clue_tokens) - size + 1):
            if _same_word("".join(clue_tokens[i : i + size]), collapsed):
                return True

    return False


def _initialism(normalised: str) -> str | None:
    words = [word for word in normalised.split() if len(word) >= 3]
    if len(words) < MIN_WORDS_FOR_INITIALISM:
        return None
    return "".join(word[0] for word in words)


def mentioned_name(clue: str, name: str) -> str | None:
    """The reason `clue` gives away `name`, or None if it does not.

    Returns a short human-readable reason so the caller can log why a clue was
    dropped, which is the only way to tell a strict-but-working checker from one
    that is silently rejecting everything.
    """
    normalised = " ".join(_tokens(name))
    if not normalised:
        return None

    clue_tokens = _tokens(clue)
    name_tokens = normalised.split()

    if _contains_phrase(clue_tokens, name_tokens):
        return f"says the term itself ({name!r})"

    # The head noun carries the term's identity: a clue for "Classification
    # Threshold" that mentions "threshold" has named half the answer, and the
    # other half is usually in the options as well.
    head = name_tokens[-1]
    if len(head) >= MIN_POLICED_TOKEN and any(_same_word(token, head) for token in clue_tokens):
        return f"says the term's key word ({head!r})"

    initialism = _initialism(normalised)
    if initialism and initialism in clue_tokens:
        return f"uses the acronym ({initialism.upper()!r})"

    return None


def validate_clues(
    payload: dict[str, Any],
    concept_names: Iterable[str],
) -> dict[str, str]:
    """Validate a raw model response into the storable clue map.

    Each clue is checked **independently** and a failure discards only that
    clue, following `validate_diagrams`: one bad item must not throw away a good
    one. Two further rules are treated as form rather than truth — a clue for a
    concept this lesson does not have is dropped, and the stored key is the
    lesson's own spelling of the concept, so lookups cannot miss on casing. Both
    are the model's noise, not a reason to discard usable content.

    Unlike diagrams, an empty result is **not** a legitimate answer. Every key
    concept is describable without its name, so "the model declined" here means
    the aural drill cannot run at all. That raises, which costs a retry and, at
    worst, leaves `clues_json` NULL so the drill reports itself unavailable with
    a reason instead of speaking its answer.

    Raises ValueError (so the caller's existing retry branch catches it the same
    way it catches a JSON parse failure).
    """
    raw = payload.get("clues") if isinstance(payload, dict) else None
    if raw is None:
        raise ValueError("response has no `clues` key")

    # Accept both the mapping form and the list form the prompt may return.
    entries: list[tuple[Any, Any]] = []
    if isinstance(raw, dict):
        entries = list(raw.items())
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                entries.append((item.get("name"), item.get("clue")))
    else:
        raise ValueError("`clues` must be an object or a list")

    if not entries:
        raise ValueError("no clues returned")

    # Canonical spelling per casefolded name, so the drill's lookup cannot miss.
    canonical = {name.strip().casefold(): name.strip() for name in concept_names if name and name.strip()}

    kept: dict[str, str] = {}
    failures: list[str] = []

    for raw_name, raw_clue in entries:
        if len(kept) >= MAX_CLUES_PER_LESSON:
            break
        name = str(raw_name or "").strip()
        clue = str(raw_clue or "").strip()
        if not name or not clue:
            failures.append("an entry was missing its name or clue")
            continue

        proper = canonical.get(name.casefold())
        if proper is None:
            failures.append(f"{name!r} is not a concept in this lesson")
            continue
        if proper in kept:
            continue

        if len(clue) < MIN_CLUE_CHARS:
            failures.append(f"{proper!r} clue is too short ({len(clue)} chars)")
            continue
        if len(clue) > MAX_CLUE_CHARS:
            failures.append(f"{proper!r} clue is too long ({len(clue)} chars)")
            continue

        leak = mentioned_name(clue, proper)
        if leak is not None:
            failures.append(f"{proper!r} clue {leak}")
            continue

        kept[proper] = clue

    if not kept:
        raise ValueError("; ".join(failures) or "no usable clue in response")

    if failures:
        # Logged rather than raised: the survivors are usable, and the reason a
        # particular concept has no clue is exactly what the drill's
        # availability message reports.
        logger.info("clue validation dropped entries: %s", "; ".join(failures))

    return kept
