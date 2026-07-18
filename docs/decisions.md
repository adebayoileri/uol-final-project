# Decisions Log

## 2026-07-18 — LLM judge instead of embeddings for Python fill-blank answer evaluation

**Context**: `POST /questions/{id}/answer` needs to evaluate Python code fill-in-the-blank answers. The existing answer evaluation path uses cosine similarity on sentence-transformer embeddings (all-MiniLM-L6-v2, 384-dim) with an LLM fallback for borderline scores. This works well for prose answers but is unreliable for short code.

**Problem with embeddings on code**: Short code fragments produce misleading similarity scores. `print(i)` and `print(x)` have nearly identical embeddings (same structure, common tokens) but are semantically very different in context. Conversely, `x += 1` and `x = x + 1` are semantically identical but score around 0.55 cosine similarity — placing them in the grey zone and triggering an LLM call anyway, just with the wrong framing.

**Alternatives considered**:
- Cosine similarity (embedding path) — rejected. Structure dominates over semantics for 1–3 token code fragments; false-positive rate is too high.
- String normalisation (strip whitespace, lower) — rejected. `x += 1` vs `x = x + 1` are not string-equivalent; would incorrectly mark correct answers as wrong.
- AST comparison (parse both answers and compare AST nodes) — rejected. Requires sandboxed Python execution or a safe eval environment; out of scope per Phase 1 decisions.

**Reason**: A direct LLM judge with a code-specific prompt handles semantic equivalence naturally and produces an `explanation` field visible to the student. The judge prompt includes the full code snippet context (with `# BLANK` marker) so the model can evaluate the answer in situ. `signal_used: "llm"` is returned to the client so the frontend can suppress the embedding-similarity percentage (meaningless for code).

**Status**: Active.

---

## 2026-07-18 — No code execution for fill-blank exercises

**Context**: Fill-blank exercises ask students to write one line of Python. The obvious enhancement is to execute the snippet and check the output, not just judge the line in isolation.

**Decision**: No code execution. Explicitly out of scope.

**Reason**: Sandboxed execution adds significant infrastructure complexity (subprocess isolation, resource limits, timeout handling, security audit). For a single-user local prototype, the LLM judge provides sufficient correctness signal without that complexity. This decision was made in Phase 1 and is reaffirmed here.

**Status**: Active.

---

## 2026-07-18 — Word-level diff instead of phoneme-level scoring for pronunciation feedback

**Context**: `/pronunciation-check` needed feedback beyond a binary pass/fail — the user should see exactly which words they got right, missed, or mispronounced. Two approaches were on the table: (1) phoneme-level alignment (Levenshtein on IPA strings via espeak-ng or a G2P model), (2) word-level diff on Whisper's existing transcript.

**Alternatives considered**:
- Phoneme-level alignment — rejected. Requires a G2P model (espeak-ng or CMU Pronouncing Dict), adds a hard OS-level dependency, and produces sparse/noisy results for Spanish where English-trained dicts have incomplete coverage. Computationally heavier for marginal user benefit at this stage.
- Edit-distance on raw characters — rejected. Conflates spelling artefacts of the ASR output with pronunciation errors; not meaningful for evaluating spoken production.

**Reason**: Whisper already transcribes the spoken words. `difflib.SequenceMatcher` on tokenised word lists is zero-dependency, deterministic, and maps directly to 4 user-visible categories: `match` (green), `missing` (red), `substituted` (yellow), `extra` (grey). Word-level accuracy (`matched_words / expected_words`) is immediately interpretable without phoneme notation. Validated against the acceptance-criteria case: "hola me llamo juan" → 4/4 match → 100% accuracy; one missing word → correctly flagged as `missing`.

**Status**: Active.

---

Every non-trivial choice made on this project, with date, alternatives considered, and reason. This file is gold for the report's Design chapter.

**Format**: newest entry on top. Each entry has Date, Decision, Context, Alternatives, Reason, and Status (Active / Superseded by [link]).

---

## 2026-06-15 — FSRS-6 via py-fsrs for spaced repetition scheduling

**Context**: Need a principled scheduling algorithm for question reviews. The brief requires active recall, so questions must resurface at optimal intervals rather than on a fixed schedule.

**Decision**: FSRS-6 algorithm via the `fsrs` library (PyPI: `fsrs`, v6.3.1), pinned as `>=6.3,<7` in `pyproject.toml`.

**FSRS-6 vs FSRS-5**:
- FSRS-6 introduces improved stability/difficulty update equations based on larger training datasets.
- No code-level branching required — the version pin in `pyproject.toml` selects FSRS-6 at install time.

**FSRS-6 vs SM-2 (Anki default)**:
- SM-2 uses a fixed ease factor that decays identically for all users; FSRS-6 is item-level and user-adaptive.
- Published benchmarks show FSRS achieves higher predicted recall at equivalent review load.
- SM-2 rejected: no published superiority evidence over FSRS, and harder to extend.

**py-fsrs API surface used**:
- `Scheduler()` — default parameters: `desired_retention=0.9`, `enable_fuzzing=True`
- `scheduler.review_card(card, Rating(n), review_datetime=None)` → `(Card, ReviewLog)` tuple
- `Card()` constructs a new card; `Card.from_dict(d)` reconstructs from a serialised dict
- `Rating.Again=1, Hard=2, Good=3, Easy=4` (IntEnum)
- `State.Learning=1, Review=2, Relearning=3` (IntEnum)

**Scheduling behaviour**:
- New cards enter `State.Learning` with default steps (1 min, 10 min).
- `Rating.Good` advances through learning steps, then enters `State.Review` with growing intervals.
- `Rating.Again` in Review → `State.Relearning` (short step), then back to Review with reduced stability.
- `due` stored as TEXT ISO 8601 UTC in SQLite to avoid timezone-stripping issues with `DateTime(timezone=True)`.
- `enable_fuzzing=True` (default) randomises review-phase intervals to prevent review bunching; disabled in simulation tests via `Scheduler(enable_fuzzing=False)`.

**Validated**: 50-review simulation in `tests/test_fsrs_simulation.py` — intervals strictly increase on consecutive Good ratings and drop after Again.

**Status**: Active.

---

## 2026-06-14 — Cosine similarity thresholds for answer evaluation

**Context**: `POST /questions/{id}/answer` needs an automated verdict without human grading. Two signals are available: embedding cosine similarity (fast, deterministic) and LLM verification (slow, ~2–5 s per call). The goal is to use the LLM only when the score is genuinely ambiguous.

**Thresholds chosen**:
- ≥ 0.65 → verdict "correct", `signal_used` "embedding"
- ≤ 0.35 → verdict "incorrect", `signal_used` "embedding"
- 0.35 < score < 0.65 → LLM verification → `signal_used` "embedding+llm"

**Alternatives considered**:
- Single threshold (e.g. 0.5) — rejected: too many borderline paraphrases fall near 0.5 with all-MiniLM-L6-v2, creating a high false-negative rate on valid answers.
- Pure LLM grading — rejected: adds 2–5 s latency and Ollama dependency to every answer submission; embedding alone suffices for clear cases.
- Higher correct threshold (0.75) — rejected: legitimate paraphrases (e.g. "Python uses indentation" vs "Python's block structure relies on indentation") score ~0.68 and would fall into the grey zone unnecessarily.

**Reason**: all-MiniLM-L6-v2 (384-dim) produces scores ≥ 0.7 for paraphrases and < 0.3 for semantically unrelated text in most Q&A domains. The 0.35/0.65 band gives a 10-point buffer on each side of the ambiguity zone. Validated against 16 manually-labelled (answer, reference, expected) pairs in `tests/test_questions.py::EVAL_FIXTURE` with ≥ 80% precision on "correct" verdicts.

**Status**: Active.

---

## 2026-05-04 — Initial stack: React + Vite + FastAPI + SQLite

**Context**: Need a web-based UI per project requirements; backend must run local models on Apple Silicon.

**Alternatives considered**:
- Next.js full-stack — rejected: heavier than needed, Python ecosystem better for ML model integration.
- Streamlit — rejected: too constrained for the UX we want (voice input, review session flow).
- Electron desktop — rejected: web is simpler to demo and screenshot for the report.
- Postgres — rejected: SQLite is sufficient for single-user local app and zero-config.

**Reason**: Vite gives fastest iteration for a small frontend. FastAPI is the Python standard for ML-backed APIs. SQLite is zero-ops and ships with Python.

**Status**: Active.

---

## 2026-05-04 — Package managers: pnpm and uv

**Context**: Choosing JS and Python package managers for the project.

**Alternatives considered**:
- npm + pip — rejected: slower, larger node_modules, no lockfile reproducibility for Python.
- yarn + poetry — rejected: poetry is slower than uv; yarn is fine but pnpm is faster.

**Reason**: pnpm uses content-addressable storage (faster installs, less disk). uv is significantly faster than pip and handles virtualenv automatically.

**Status**: Active.

---

## 2026-05-04 — Four models on different data types (planned)

**Context**: Brief requires ≥3 pre-trained models on different data types. Chose 4 to exceed and to add genuine functionality.

**Planned models**:
1. Llama 3.1 8B (Ollama) — text → text
2. Whisper (mlx-whisper) — audio → text
3. sentence-transformers all-MiniLM-L6-v2 — text → vector
4. Piper TTS — text → audio

**Alternatives considered**: see Week 2–3 bake-off (to be filled in).

**Reason**: Each model earns its place via a distinct user-visible feature; no model is added "for the count."

**Status**: Pending validation in Week 1 spike and Week 3 bake-off.

---

## TEMPLATE — copy this for new entries

```
## YYYY-MM-DD — [Decision in one line]

**Context**: Why this decision came up.

**Alternatives considered**:
- Option A — why rejected.
- Option B — why rejected.

**Reason**: Why the chosen option won.

**Status**: Active / Superseded by [link to later entry].
```

----

## 2026-05-04 - Model installation and test
Tested models used in the project (llama 3.1 8b) works decently, smoke testing it to generate a quick spanish learning guide in 4 weeks and it did in less than 10secs. So I'll qualify the performance as fast.

Llama 3.1 8b would be a good text to text model for the project.

Tried to install mlx whisper via uv but had issues installing dependencies
```
uv pip install mlx-whisper                  
  × No solution found when resolving dependencies:
  ╰─▶ Because mlx==0.31.2 has no wheels with a matching platform tag (e.g., `macosx_26_0_x86_64`) and
      mlx>=0.11.1,<=0.31.1 has no wheels with a matching platform tag (e.g., `macosx_26_0_x86_64`), we can
      conclude that mlx>=0.11.1,<=0.31.1 cannot be used.
      And because only the following versions of mlx are available:
```

Decided to go with an easier option i.e whisper.cpp (also open source) - Tested this with an example .wav file to confirm tts capabilities and got good result in <6s

```bash
system_info: n_threads = 4 / 10 | WHISPER : COREML = 0 | OPENVINO = 0 | MTL : EMBED_LIBRARY = 1 | CPU : NEON = 1 | ARM_FMA = 1 | DOTPROD = 1 | ACCELERATE = 1 | OPENMP = 1 | REPACK = 1 | 

main: processing 'samples/jfk.wav' (176000 samples, 11.0 sec), 4 threads, 1 processors, 5 beams + best of 5, lang = en, task = transcribe, timestamps = 1 ...


[00:00:00.000 --> 00:00:11.000]   And so my fellow Americans, ask not what your country can do for you, ask what you can do for your country.

```

----

## 2026-05-31 — [Decision in one line]

**Context**: Why this decision came up.

**Alternatives considered**:
- Option A — why rejected.
- Option B — why rejected.

**Reason**: Why the chosen option won.

**Status**: Active / Superseded by [link to later entry].

----

## 2026-06-19 — Whisper integration via `whisper-cli` subprocess

**Context**: Needed speech-to-text for `/transcribe` and `/pronunciation-check`. whisper.cpp was already chosen over mlx-whisper (see 2026-05-04 entry above) for platform-compatibility reasons. The remaining question was how to call it from FastAPI, and which model file to ship the default path for.

**Alternatives considered**:
- Parse the transcript from `whisper-cli`'s stdout — rejected. whisper.cpp interleaves diagnostic logging (`system_info: ...`, `main: processing ...`) with the transcript on stdout/stderr unpredictably across builds, making it fragile to scrape.
- Use the Homebrew-bundled `for-tests-ggml-tiny.bin` as the default model — rejected. It's a build-test stub; running it against the project's `jfk.wav` reference sample produced zero transcript output (silent failure, exit code 0).
- Embed whisper.cpp via a Python binding (e.g. `pywhispercpp`) — rejected, for the same reason Ollama is called over HTTP rather than embedded: keeps the model runtime as an external, independently-upgradable process rather than a Python dependency tied to this venv's ABI.

**Reason**: `whisper-cli` is invoked with `-otxt -of <tmp_basename>` and the transcript is read back from the written `.txt` file — sidesteps stdout-parsing fragility entirely. Default `WHISPER_MODEL_PATH` points at `ggml-base.en.bin` (downloaded separately, gitignored), which is a real usable model, not the bundled stub. Measured latency on the 5-second `samples/test_5s.wav` fixture (JFK clip, 16kHz mono): **~0.63s wall-clock for the subprocess call**, logged via `logger.info` in `transcriber.py` and returned to the client as `duration_seconds`. Well within the latency budget for a synchronous request/response endpoint.

**Status**: Active.

----

## 2026-06-19 — Piper integration via `piper-tts` pip package

**Context**: Needed text-to-speech for `/tts`. The original brief assumed a `piper` binary installed system-wide; on inspection, nothing called `piper` existed anywhere on the machine (checked PATH, Homebrew, pip, pipx). User installed the `piper-tts` pip package (v1.4.2, the `OHF-voice/piper1-gpl` rewrite) into the existing uv-managed venv instead.

**Alternatives considered**:
- Invoke a bare `piper` binary on PATH, per the original task framing — rejected, since no such binary exists on this machine or in the `piper-tts` pip distribution (it ships no console-script entry point).
- Auto-download voices at synthesis time — rejected. The `piper-tts` package has no auto-download path at synthesis; voices must be fetched once via `python -m piper.download_voices <voice> --data-dir <dir>`. Acceptable for a local-first, single-user app — this is a one-time setup step, not a runtime concern.

**Reason**: `synthesize_speech()` shells out to `<venv-python> -m piper -m <voice> --data-dir backend/voices -f <tmp.wav> -- "<text>"`, matching the same subprocess-boundary pattern used for `whisper-cli` and for Ollama. Voice names were confirmed against the `rhasspy/piper-voices` HuggingFace repo (the `voices.json` index was truncated mid-fetch, so the Spanish entry was confirmed via the HF API directory-listing endpoint instead): `en_US-lessac-medium` (English default) and `es_ES-davefx-medium` (Spanish default, only `medium`-quality variant available for the `davefx` speaker). Verified manually: both English and Spanish requests produced valid RIFF/WAVE PCM 16-bit mono 22050Hz files, confirmed audible via `afplay` and frame-count-checked via Python's `wave` module.

**Status**: Active.

----

## 2026-06-21 — Closed two API gaps before building the frontend: `GET /courses/{id}` and auto-created FSRS cards

**Context**: Starting the first real frontend flow (goal input → course view → review session) surfaced two gaps that weren't deliberate design choices, just things nobody had needed yet: `POST /courses` was write-only (no way to re-fetch a course), and FSRS `Card` rows were only ever created by manually running `backend/scripts/backfill_cards.py` — so newly generated questions were invisible to the review session until someone remembered to re-run that script.

**Alternatives considered**:
- Leave course-fetching to the frontend (pass the just-created `CourseResponse` through router state, fall back to `sessionStorage`) — rejected. Works for the happy path but breaks on a fresh page load/shared link, and is strictly worse than just adding the missing `GET` endpoint that every other resource already has.
- Leave card-creation manual and have the frontend show a "run this script" hint — rejected. Pushes a real backend gap onto the user as a manual step in the demo flow; not acceptable for something that should just work end-to-end.

**Reason**: `GET /courses/{course_id}` was added to `app/routes/courses.py`, reusing `CourseResponse` and the same `selectinload` eager-loading pattern already used in `app/routes/lessons.py`. `generate_lesson_questions` (`app/routes/lessons.py`) now creates one `Card` per generated `Question` inline — same construction `backfill_cards.py` already used (`FSRSCard()` default-constructed, fields copied across) — so a question is reviewable the moment it's generated. `Card.question_id`'s existing `UniqueConstraint` makes this safe against double-creation. `backfill_cards.py` is kept as-is for any pre-existing questions from before this change.

**Status**: Active.