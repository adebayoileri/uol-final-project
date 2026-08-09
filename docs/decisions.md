# Decisions Log

## 2026-08-09 — Prompts as `.txt` files, not inline Python strings

**Context**: Phase A required enriching the course and question generation prompts. Inline strings embedded in `course_agent.py` and `question_generator.py` were 40–60-line blocks that became hard to read, hard to test independently, and required a Python redeploy to change.

**Alternatives considered**:
- Keep inline — rejected. Unreadable in diff. Mixing template content with Python logic makes both harder to change.
- Jinja2 templates — rejected. Jinja2 is the right tool if templates have conditional blocks or loops inside the template itself. These templates are flat (no logic — just `{variable}` substitution), so `str.format(**kwargs)` is sufficient and introduces no new dependency.
- `.json` or `.yaml` config — rejected. A prompt is prose, not structured data. `.txt` is the right file type for prose.

**Reason**: Flat `.txt` files in `backend/app/prompts/` loaded once at module level with `pathlib.Path.read_text()` and substituted with `.format(**kwargs)`. This makes prompt changes reviewable as standalone diffs, keeps Python files focused on logic, and enables A/B testing a prompt by swapping a file without touching Python. The directory path is resolved relative to `__file__` so it works regardless of working directory.

**Status**: Active.

---

## 2026-08-09 — `content_parser` as a separate module (never raises)

**Context**: LLM lesson output in Phase A now contains optional structured fields (`key_concepts`, `worked_example`, etc.). Two callers need to extract these: `question_generator` (to build richer prompts) and potentially the frontend renderer. Inline JSON parsing in each caller leads to duplicated try/except boilerplate.

**Alternatives considered**:
- Pydantic model for lesson content — considered. Cleaner types, auto-validation. Rejected for now: Pydantic raises `ValidationError` on bad data, which means every caller has to handle the exception. The invariant we want is "extraction never crashes the request"; `parse_lesson_body` expresses that explicitly and is easier to test with bad/partial fixtures.
- Validate at course-generation time (before write to DB) — rejected. The course agent already has its own `_validate_structure` check on the top-level shape. Adding deep field validation there would couple the parser to the generation path and make retries more aggressive. Better to validate lazily at read time.

**Reason**: `parse_lesson_body(raw: str) -> dict` always returns a dict with known keys (empty defaults for missing fields). Callers get type-safe access without try/except. `is_structured: bool` lets callers branch on whether the description was rich JSON or legacy plain text without re-parsing. Nine unit tests cover: full input, missing fields, malformed JSON, plain text, empty string, non-list `key_concepts`, empty concept names, wrong-type pitfalls, and whitespace stripping.

**Status**: Active.

---

## 2026-07-19 — Frontend: no shared data-fetching library; local state only

**Context**: R5 adds 5 pages. Choosing whether to introduce TanStack Query, SWR, or
a global store (Zustand etc.) vs. keeping the current pattern of per-component `useEffect` + `useState`.

**Reason**: The app is single-user with no concurrent mutations and no cross-page cache
invalidation requirements. Each page fetches its own data on mount. Adding a query library
would introduce a new dependency for negligible gain at this scale (5 pages, 3–4 distinct
fetch sites). The `request<T>()` helper in `api.ts` is already a thin, consistent wrapper.
If a future session adds optimistic mutations or shared cart/session state, TanStack Query
would be the right upgrade — defer until then.

**Status**: Active.

---

## 2026-07-19 — ReviewSession shares one component for scoped and global review

**Context**: The IA has two review routes: `/courses/:courseId/review` (course-scoped) and
`/review` (global). These could be two separate components or one parameterised component.

**Reason**: The only difference between the two flows is whether `courseId` is passed to
`getNextCard` and `getReviewQueue`. A single `ReviewSession` component reads `courseId` from
`useParams()` (undefined on the global route) and conditionally appends the query param.
One component, one test surface, no duplication. The back-link adjusts accordingly
(`/courses/:courseId` when scoped, `/courses` when global).

**Status**: Active.

---

## 2026-07-19 — Lesson-completion semantics: explicit mark, not automatic

**Context**: `POST /lessons/{id}/complete` needs a definition of what "complete" means.
Two approaches were on the table: (1) automatic — trigger completion when all FSRS cards for
the lesson reach `State.Review`; (2) explicit — user presses a "Mark complete" button.

**Alternatives considered**:
- Automatic on FSRS card graduation — rejected. A lesson can have 3 questions, all of which
  reach `State.Review` after a week of daily reviews. But the user might have completed the
  lesson content on day 1. Tying completion to the scheduler conflates two cognitively
  different activities: reading/studying a lesson (one-time) and recalling via spaced
  repetition (ongoing).
- Automatic on question generation — rejected. Generating questions is not the same as
  having studied them; it's a tool action, not a learning signal.

**Reason**: An explicit "Mark as complete" action models the user's intent accurately. The
lesson is "done" when the user says so. `completed_at` is set once, never overwritten (idempotent
POST). Progress summary (`completed_lessons / total_lessons`) counts lessons with
`completed_at IS NOT NULL`. The FSRS review queue is separate and ongoing regardless of lesson
completion status.

**Status**: Active.

---

## 2026-07-19 — Course list returns `progress_summary` as a denormalised aggregate

**Context**: `GET /courses` needs to return progress counts without fetching full course trees.

**Reason**: Four `COUNT(*)` queries per course (total_lessons, completed_lessons, total_cards,
due_now) run in <1ms each on indexed columns (`Module.course_id` via FK, `Card.course_id` via
`ix_cards_course_due`). For 5 courses, 20 total queries ≈ <5ms. No full tree serialisation,
no N+1 on objectives. The counts are computed in `app/services/progress.py` and are correct
at request time — no caching, no stale data.

**Status**: Active.

---

## 2026-07-18 — Review endpoint: 204 for "no cards due" and optional `course_id` scope

**Context**: `GET /review/next` needed two contract decisions — what to return when no card is
due, and whether to scope results by course.

**Alternatives considered**:
- 404 for "no cards due" — rejected. 404 means "resource not found", which is wrong: the queue
  exists, it's just empty right now. Misleading to the frontend.
- 200 with null body — rejected. Forces the client to null-check before reading any field.
  204 is the semantically correct signal for "operation succeeded, nothing to return."
- Required `course_id` (no global mode) — rejected. A global "all courses" review mode is a
  valid use case (the spec's acceptance criteria explicitly say omitting course_id should
  work). Optional param avoids breaking the current frontend while enabling scoped review.

**Reason**: `GET /review/next?course_id=<id>` scopes to that course's cards. Omitting
`course_id` returns the globally next due card across all courses. Implemented as a conditional
`.filter(Card.course_id == course_id)` in SQLAlchemy — clean, no raw SQL. `GET /review/queue`
adds the same scope parameter and returns `{total, due_now, due_today, due_this_week}` for the
review-hub UI. No `user_id` filter: single-user app, no auth.

**Status**: Active.

---

## 2026-07-18 — Denormalised `course_id` on `questions` and `cards`

**Context**: The review query pattern is `cards WHERE course_id = ? AND due <= ?`. Without a
`course_id` column on `Card`, scoping review to one course requires a 4-hop join
(card → question → lesson → module → course) on every `GET /review/next` call — a full table
scan that grows with total card count across all courses.

**Alternatives considered**:
- Join-based scoping — rejected. SQLite can't use an index to efficiently scope a query whose
  filter column lives 3 tables away; any index on an intermediate table still requires scanning
  all cards.
- Store `course_id` only on `Card`, not `Question` — rejected. `Question` is also queried
  directly (e.g. answer evaluation, search indexing) and benefits from the same denormalisation.

**Reason**: Adding `course_id` directly to both `questions` and `cards` lets SQLite use the
`(course_id, due)` composite index on cards, cutting the review query from O(N) to O(log N + k)
where k is cards due in that course. The redundancy is safe: `course_id` is write-once (set at
question-generation time and never updated). Backfill via the `lesson → module` join chain runs
at startup in `_run_migrations()`, same pattern as the existing `question_type`/`code_snippet`
migrations — `WHERE course_id IS NULL` and `IF NOT EXISTS` make it fully idempotent.

**Status**: Active.

---

## 2026-07-18 — Semantic search: SQLite + numpy over FAISS / vector DB

**Context**: Sub-phase 3C required a search index over lesson and question content. Options were a dedicated vector database (FAISS, Chroma, Qdrant) or a simpler SQLite + numpy approach.

**Alternatives considered**:
- FAISS — rejected. Adds a C++ native dependency; overkill for a corpus that will realistically reach ~500 items at most. Latency difference vs numpy at 500 × 384 floats is negligible (<5ms either way).
- Chroma / Qdrant — rejected. Both run as external server processes, adding operational complexity for a single-user local prototype.
- SQLite FTS5 (full-text search) — rejected. FTS5 is keyword-based; it would miss paraphrases (e.g. "iterate" not found by a query for "loop"), defeating the semantic matching goal.

**Reason**: Numpy cosine similarity over `N × 384` float32 vectors loaded from SQLite is measured at <5ms for N=500. Vectors are stored as BLOB (1536 bytes = 384 × float32), which is 2.5× smaller than JSON and requires no parsing. The `content_embeddings` table scopes results by `course_id` so the search panel shows only the open course's content. No new runtime dependency added — numpy is already a transitive dependency of sentence-transformers.

**Indexed content**: Lessons (title + description) and questions (question stem). Modules and courses are excluded — they are too coarse to be useful retrieval targets; the lesson is the atomic learning unit.

**Status**: Active.

---

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
----

## 2026-08-09 — Design tokens in a Tailwind v4 `@theme` block, not a config file or CSS-in-JS

**Context**: The frontend had no design system at all. `src/index.css` was seven lines; five surface colours (`#0a0a0f`, `#111118`, `#1a1a24`, `#2a2a3a`, `#0d0d14`) were hand-repeated as arbitrary-value classes in every file, so `border-[#2a2a3a]` alone appeared in nearly every component. Nothing could be changed centrally.

**Alternatives considered**:
- A `tailwind.config.js` with a `theme.extend` block — rejected. Tailwind v4 (which this project already uses via `@tailwindcss/vite`) has no config file by design; adding one back would fight the toolchain.
- A TypeScript token module consumed by CSS-in-JS — rejected. Introduces a runtime styling dependency and a second source of truth alongside Tailwind's utilities, for a single-developer dissertation project where the utilities already work.

**Reason**: `@theme` is v4's native mechanism and generates both the CSS custom properties and the matching utility classes from one declaration, so `--color-border` yields `border-border`, `text-border`, etc. automatically. Type steps are declared as *sets* — `--text-display-2xl` binds size, `--text-display-2xl--line-height`, `--text-display-2xl--letter-spacing` and `--text-display-2xl--font-weight` together — which enforces the WWDC 2020 typography rule that tracking and leading are size-specific and must never be applied as one fixed value across a scale. A useful confirmation that the tokens are wired correctly: the editor's Tailwind plugin immediately began flagging every legacy `border-[#2a2a3a]` as "can be written as `border-border`", which doubles as a migration checklist for the later phases.

**Status**: Active.

----

## 2026-08-09 — Absolute `API_URL` for narration and chat, not a Vite dev-server proxy

**Context**: `AudioPlayer` and `AIAssistantPanel` fetched relative paths (`/api/lessons/...`) while every other caller used `const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'`. No proxy was ever configured in `vite.config.ts`, so both requests hit the Vite dev server and 404'd. The Phase D audio narration and Phase E streaming chat features had therefore never worked in a browser despite both being implemented and committed.

**Alternatives considered**:
- Add a `server.proxy` entry mapping `/api` to `http://localhost:8000` — rejected. It would work under `vite dev` and silently break under `vite build` / `vite preview` and any static deployment, since a dev-server proxy does not exist in a production bundle. It would also leave two competing conventions in one codebase.

**Reason**: The backend's CORS middleware already sets `allow_origins=["http://localhost:5173"]`, so cross-origin requests from the dev server are permitted with no additional configuration, and `.env` already carries `VITE_API_URL`. Switching both components to the absolute base makes them consistent with `api.ts` and survives a production build. The constant was extracted to a single `src/config.ts` in the same change, removing four duplicate declarations.

**Status**: Active.

----

## 2026-08-09 — Self-hosted Inter Variable rather than the platform system font

**Context**: The app had no `font-family` declaration at all, inheriting Tailwind Preflight's `system-ui` stack. The redesign introduces a type scale with per-step tracking values tuned to a specific typeface.

**Alternatives considered**:
- Keep the system stack (`system-ui`) — this is what Apple's own guidance recommends, since the platform font ships optical sizing, tracking tables and legibility tuning already. On macOS it resolves to SF Pro, which is excellent.

**Reason**: Rejected specifically because of what this artefact is. Screenshots go into the dissertation and a second marker may open the app on Windows or Linux, where the same stack resolves to Segoe UI or DejaVu Sans — different metrics, so the tuned tracking values would be wrong and the display headings would not match the figures in the report. Inter Variable is self-hosted via `@fontsource-variable/inter` (no CDN request, consistent with the project's local-first framing), exposes a real `opsz` axis so `font-optical-sizing: auto` does something, and has a continuous weight axis so intermediate weights such as 620 are genuine instances rather than synthesised. Monospace deliberately stays on the system stack — code blocks need no brand identity and it avoids a second font download.

**Status**: Active.

----

## 2026-08-09 — Callout marker stripping walks the React tree instead of flattening to a string

**Context**: `LessonRenderer` detects GitHub-style `> [!NOTE]` / `> [!WARNING]` blockquotes and renders them as `Callout` components. It did so by calling `extractText(children)` to flatten the subtree to a plain string, stripping the marker with a regex, and passing the resulting string as the callout body.

**Reason**: Flattening discards the element tree, so any inline markdown inside a callout — bold, links, inline code — was silently rendered as literal text. Since lesson bodies are LLM-generated and the prompt encourages emphasis, this was actively lossy on real content. `extractText` is now used for *detection only*; rendering goes through `stripLeadingMarker(children)`, which walks the tree, replaces the marker on the first non-empty string leaf it reaches, and returns every other node untouched via `cloneElement`. A `done` flag stops the walk after the first substitution so a later occurrence of the literal text is never altered.

**Status**: Active.

----

## 2026-08-09 — Spring parameters expressed as damping ratio and response, not mass/stiffness/damping

**Context**: The redesign needed a motion vocabulary that could be applied consistently across ~20 components without each one inventing its own timing.

**Alternatives considered**:
- CSS transitions and `@keyframes` throughout — rejected for anything a user can interrupt. A CSS transition animates from wherever it was declared to start, cannot be grabbed and redirected mid-flight, and produces a visible jump when a new transition replaces a running one.
- Raw physics parameters (mass/stiffness/damping) — rejected as unusable for design intent. Nothing about `stiffness: 210` communicates how the motion will feel, so values get copied around and drift.

**Reason**: Apple replaced the physics triplet with two designer-facing parameters — damping ratio (how much it overshoots) and response (how quickly it reaches the target) — and Motion's `bounce` + `duration` API maps onto those closely, with `bounce ≈ 1 − damping`. `src/motion/springs.ts` defines four named springs and the codebase uses nothing else. The rule that carries the most weight is that `bounce > 0` is only permitted where a gesture genuinely carried momentum or where the moment is a celebration: overshoot on a panel that merely faded in reads as noise, while overshoot on a review card thrown out by a rating reads as physical. Reduced motion is handled once at the root via `MotionConfig reducedMotion="user"` rather than per-component, so the behaviour cannot drift.

**Status**: Active.

----

## 2026-08-09 — Per-route container widths instead of one shared column

**Context**: Every page — the lesson reader, the review card, and all the dashboards — rendered inside a single `max-w-3xl` (768px) column defined once in `App.tsx`. Only one responsive class existed in the entire codebase.

**Reason**: These surfaces have opposite requirements. Long-form reading wants a measure of roughly 60–75 characters, so the lesson body is capped at 46rem; dashboards want to use the width for two columns and stat grids, so they go to 72rem; the review card wants to be narrow and focused. A `Container` component takes a `width` token and each route picks one. This is what makes the two-column dashboards from the target design possible at all — they cannot exist inside a 768px column.

**Status**: Active.

----

## 2026-08-09 — `GET /review/forecast` folds overdue cards into today and returns empty days explicitly

**Context**: The review calendar needed per-day due counts. The existing `/review/queue` returns only three cumulative buckets (`due_now`, `due_today`, `due_this_week`).

**Alternatives considered**:
- Derive the calendar client-side from the three buckets — rejected outright. The buckets are cumulative and carry no per-day information, so any daily breakdown drawn from them would be invented. In a dissertation artefact that is fabricated data, not a rendering shortcut.

**Reason**: The endpoint groups cards by due date over a bounded horizon. Two decisions inside it are worth recording. Overdue cards are attributed to today rather than to the past date they were scheduled for, because today is where the learner will actually encounter them and a backlog rendered in the past would be unreachable. Days with no cards are returned explicitly with `count: 0` rather than omitted, so the client renders exactly what it is given and never has to distinguish "no cards" from "no data". The frontend widget degrades to the three queue buckets if the endpoint returns 404, so an older backend loses the calendar but not the page.

**Status**: Active.

----

## 2026-08-09 — Kept the mockups' visual density, rejected their navigation

**Context**: The redesign was driven by a set of v0-generated mockups. Those mockups included a floating bottom pill navigation labelled Home / Timeline / Content / Review / Completion, and a sidebar panel listing the models in use (Llama 3.1, Whisper, Piper TTS, Sentence-T) with fixed role labels.

**Reason**: The wide two-column layouts, icon-badge stat tiles, gradient display headings and calendar widget were adopted, because they are genuine improvements over a 768px single column. The bottom pill nav was not, because those five labels describe a linear walkthrough of the product rather than its actual information architecture — they are a presentation narrative, and shipping them would have made the navigation misrepresent the structure beneath it. The "Models in Use" panel was reinterpreted rather than copied: the panel *shape* (titled rows, tinted icon badges, right-aligned values) was reused for the learning-insights sidebar, but every row is bound to a real value from `/courses/{id}/insights`. Displaying a static list of model names dressed as live status would have been decorative fiction in a document that is meant to be evidence.

**Status**: Active.
