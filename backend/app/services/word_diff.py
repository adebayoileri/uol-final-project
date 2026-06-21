"""Word-level diff between an expected phrase and a transcribed phrase.

Used by /pronunciation-check to highlight which words were matched, missing
(expected but not heard), extra (heard but not expected), or substituted.
"""

import difflib
import string
from typing import Any

_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)


def _tokenize(text: str) -> list[str]:
    return [w.translate(_PUNCTUATION_TABLE) for w in text.lower().split()]


def compute_word_diff(expected: str, actual: str) -> list[dict[str, Any]]:
    expected_words = _tokenize(expected)
    actual_words = _tokenize(actual)
    matcher = difflib.SequenceMatcher(a=expected_words, b=actual_words, autojunk=False)

    diff: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                diff.append({"op": "match", "expected": expected_words[i1 + k], "actual": actual_words[j1 + k]})
        elif tag == "delete":
            for k in range(i1, i2):
                diff.append({"op": "missing", "expected": expected_words[k], "actual": None})
        elif tag == "insert":
            for k in range(j1, j2):
                diff.append({"op": "extra", "expected": None, "actual": actual_words[k]})
        elif tag == "replace":
            n = max(i2 - i1, j2 - j1)
            for k in range(n):
                exp_word = expected_words[i1 + k] if i1 + k < i2 else None
                act_word = actual_words[j1 + k] if j1 + k < j2 else None
                if exp_word is not None and act_word is not None:
                    diff.append({"op": "substituted", "expected": exp_word, "actual": act_word})
                elif exp_word is not None:
                    diff.append({"op": "missing", "expected": exp_word, "actual": None})
                else:
                    diff.append({"op": "extra", "expected": None, "actual": act_word})
    return diff
