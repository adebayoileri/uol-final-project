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

----

## 2026-08-15 — Two-pass lesson generation: a skeleton pass, then lazy per-lesson enrichment

**Context**: Generated lessons were shallow — a two-sentence summary and nothing else. The cause was a single line: `app/routes/courses.py:80` persisted only `lesson_data["description"]`, discarding the `key_concepts`, `worked_example`, `common_pitfalls` and `practice_prompts` that `course_structure.txt` explicitly asks for. Measured on the live database: 19 lessons, mean description length 98 characters, longest 264.

Simply storing the discarded fields would not have been enough. One `POST /courses` call has to emit every lesson in the course — up to 10 modules × 5 lessons for a long-term course — so the model must ration a single output budget across as many as 50 lessons, each supposedly carrying 3–5 concepts, a multi-step worked example, pitfalls and prompts. That is why the prose was thin in the first place.

**Alternatives considered**:
- **Store the discarded fields and widen the generation call** (raise `num_ctx`, `num_predict`) — rejected. Cheapest change, but one call still has to divide its budget across every lesson, so quality stays uneven and long-term courses truncate. It also leaves the 19 existing lessons shallow forever.
- **Enrich every lesson eagerly during course creation** — rejected. Deep content everywhere, but course creation becomes 20–50 sequential LLM calls, several minutes of waiting, with one failure risking the whole course.

**Reason**: Course creation keeps its single fast call and stays deliberately shallow (titles, a prose summary, objectives, duration). A second prompt, `app/prompts/lesson_content.txt`, generates the body for **one** lesson at a time, on first open, cached in `lessons.content_json`. Each lesson therefore gets an entire context window to itself rather than a fiftieth of one — measured effect on a real lesson: **30 characters of description became 2,082 characters of structured content in 17 seconds**.

The lazy trigger has a second benefit that a backfill script would not: the 19 pre-existing shallow lessons enrich themselves as they are opened, so no regeneration and no migration script is needed. Failure leaves `content_json` NULL, which is a retryable state rather than a poison pill.

`_validate_content()` enforces thresholds (≥2 concepts, at least one definition ≥60 characters, a worked example ≥200 characters) and retries once. This is what stops the original defect recurring: output that satisfies the JSON schema but is shallow is rejected rather than stored.

**Status**: Active.

----

## 2026-08-15 — Structured content in a separate `content_json` column, not inside `description`

**Context**: The enrichment has to live somewhere. `content_parser.parse_lesson_body()` and the frontend's `LessonBody` were both written expecting `lesson.description` to be a JSON object string, so overloading that column was the path of least resistance.

**Alternatives considered**:
- **Store JSON in `description`** — rejected, and the two reasons are concrete rather than stylistic. `app/services/question_generator.py:66` passes `lesson.description` into the question prompt as the `lesson_description` template variable; a JSON blob there would make every generated question worse. `app/services/embeddings.py:20` builds the search index text as `f"{lesson.title}: {lesson.description}"`; JSON there would pollute semantic search and put raw braces into the snippet rendered in search results.

**Reason**: A new nullable `lessons.content_json TEXT` column. `description` stays prose and keeps its two existing jobs. `NULL` is an explicit "not yet enriched" state rather than something inferred from whether a string happens to start with `{`. `Lesson.content` is exposed as a property, and because Pydantic reads properties under `from_attributes=True`, `LessonDetailResponse` picks it up with no change to the route.

`tests/test_lesson_context.py::test_question_context_keeps_description_as_prose` pins the regression this decision exists to prevent.

**Status**: Active.

----

## 2026-08-15 — Enrichment behind `POST /lessons/{id}/enrich`, not inside the lesson GET

**Context**: Enrichment needs a trigger. The obvious place is `get_lesson_detail`, which already loads the lesson.

**Reason**: Rejected on three counts. It would turn an instantly-rendering page into a 10–60 second blank screen on every first open, which is the single worst outcome available here. It would mutate the database inside a `GET`, breaking caching, retry and prefetch semantics for any client or proxy that speculatively re-issues the request. And an enrichment failure would then have to either be swallowed — leaving a GET that sometimes takes a minute and returns nothing new — or surfaced as a 503 on the lesson page itself.

A separate endpoint keeps the risk contained: if enrichment breaks entirely, the reader still gets the title, objectives, prose and practice deck exactly as fast as before, and loses only the enriched sections. The frontend fires it after first paint and shows a skeleton in place. Failure renders a quiet inline retry rather than a toast, because the page did render correctly and a red error would misrepresent that.

`tests/test_lesson_enrichment.py::test_enrich_failure_leaves_null_and_lesson_detail_still_works` asserts this invariant directly.

**Status**: Active.

----

## 2026-08-15 — Per-lesson in-process lock with a double-check, over a DB guard

**Context**: Two concurrent opens of the same unenriched lesson would otherwise both trigger a multi-second LLM call. This is routine rather than theoretical: React 18 StrictMode double-invokes effects in development — the mode the demo and dissertation screenshots run in.

**Alternatives considered**:
- **A DB guard alone** (`UPDATE … WHERE content_json IS NULL`) — insufficient. It prevents the duplicate *write* but not the duplicate *call*, and with a single local Ollama instance requests serialise, so a redundant call does not merely waste GPU time — it doubles the wait the user is watching.
- **Accept-and-overwrite** — worst of the three. Same wasted call, plus two different bodies generated for one lesson, so whichever lands second silently replaces content the reader may already be looking at and invalidates the narration hash a second time.
- **Return 202 and have the client poll** — correct for a multi-user service, unnecessary here. Blocking the second caller keeps the client free of a polling loop and a state machine, and costs one threadpool worker in a single-user application.

**Reason**: A `threading.Lock` per lesson id (not `asyncio.Lock` — the route is `def`, so FastAPI runs it in the threadpool), with a double-check inside the lock. The subtle part is `db.expire(lesson, ["content_json"])` immediately after acquiring: the blocked request loaded the lesson into its Session's identity map *before* waiting, so re-reading `content_json` without expiring returns the stale in-memory `NULL`, the double-check passes, and the second call proceeds — the lock would appear to work while doing nothing. This was verified rather than assumed: with the lock and the expire removed, `test_concurrent_enrich_generates_once` fails with `2 != 1`.

**Limitation, accepted**: the lock is per-process, so under `uvicorn --workers N` two processes could still race. The deployment is a single local process, and the `content_json IS NULL` check keeps the worst case a wasted call rather than corruption.

**Status**: Active.

----

## 2026-08-15 — First explicit Ollama `options` block: `num_ctx` on enrichment and chat

**Context**: No Ollama caller in this project had ever sent an `options` block — no `num_ctx`, `num_predict` or `temperature` anywhere. Every call ran at Ollama's server defaults.

**Reason**: That is survivable for short outputs and actively harmful for long ones. `llama3.1:8b` advertises a 131,072-token context, but Ollama's *runtime* `num_ctx` default is far lower (2048 on stock builds) unless set, and it counts prompt and generation in the same window. Lesson enrichment targets 1,000–1,400 output tokens; at the default the model runs out mid-`worked_example`, emits a truncated string, fails `json.loads`, and burns both retry attempts for a 503 with no obvious cause. Enrichment therefore sets `num_ctx: 8192`, `num_predict: 2048` (a ceiling, so a degenerate repetition loop becomes a clean rejection rather than a 180-second timeout) and `temperature: 0.4` (below the 0.8 default — improves JSON structural adherence; going below ~0.3 makes examples generic and repetitive across lessons, which is the exact failure this feature exists to fix).

The tutor chat gets `num_ctx: 8192` for a different and more insidious reason: its system message now carries up to 4,000 characters of lesson content plus ten history turns. On overflow Ollama evicts from the **start** of the prompt — precisely where the lesson grounding sits. The tutor would look grounded in the code and be ungrounded at runtime, which is the hardest class of bug to notice and the worst to discover during a demo.

**Status**: Active.

----

## 2026-08-15 — Search index deliberately left on the prose description

**Context**: With `content_json` populated, the semantic search index could be rebuilt over the enriched content instead of `f"{lesson.title}: {lesson.description}"`.

**Reason**: Deferred, not overlooked. It would require re-embedding on every enrichment, and it would put worked-example code into `content_text` — the string rendered directly in search results, where a fragment of a Python walkthrough is worse than a sentence of prose. Revisit only if search recall proves inadequate in evaluation.

**Status**: Deferred.

----

## 2026-08-16 — Stream accumulation belongs in a ref written synchronously, not in state synced by an effect

**Context**: The AI tutor streamed its reply into the panel correctly, then lost it the instant the stream ended — the text appeared during generation and was never retained in the transcript.

The backend was not at fault: verified directly, `POST /lessons/{id}/chat` emitted 23 SSE lines terminated by `[DONE]` and persisted both the user message and the full assistant reply to `lesson_chat_messages`. The defect was entirely in `AIAssistantPanel`.

`onChunk` appended each token to React state, and a `useEffect` mirrored that state into `streamingContentRef`. `onDone` then read the ref to commit the finished message. But `useSSE` invokes `onChunk` and `onDone` **synchronously** while draining a single network read, and a React effect body does not run until after the current task yields. The measured reply arrived in about 1.3 seconds, so every token and the `[DONE]` sentinel were parsed in one pass with no re-render between them — the ref still held its initial `""` when `onDone` fired. The transcript was therefore committed with empty content while `setStreamingContent("")` simultaneously cleared the visible text.

Reproduced deterministically outside React by modelling those two orderings against the parse loop copied verbatim from `useSSE`: the old strategy yields `""`, the fixed strategy yields the complete reply.

**Reason**: The ref is now the authoritative accumulator and is written synchronously inside `onChunk`; the state exists purely to trigger a re-render. Any design that recovers streamed data from state written earlier in the same synchronous pass is racing the renderer and will fail whenever a response arrives quickly — which is the common case, not the edge case.

Two related corrections landed with it. Finalisation moved out of `onDone` and into the point where `start()` resolves, because `start` resolves for **every** terminal condition, whereas `onDone` fires only on an explicit `[DONE]` — a stream cut short by a server restart, a dropped connection or an abort would previously have left the reply on screen and never retained it. And the empty assistant placeholder is now dropped rather than committed when nothing arrives, instead of leaving a permanently blank bubble that would also be replayed as history context on the next turn.

The bubble's rendered text is also no longer keyed on `isStreaming` (`msg.content || streamingContent` instead), since `isStreaming` flips false a beat before the text is committed and would blank the reply for a frame.

**Status**: Active.

----

## 2026-08-16 — Course classification from goal + category + title, not category alone

**Context**: Two features branched on `Course.category`, which is free text typed into a plain input box. Both were silently wrong against the real database: `_detect_lang` tested `"spanish" in category` while the Spanish course was categorised `"Language"`, so it was narrated by an English voice; `_is_python_lesson` required `category == "python"` while the Python course was categorised `"Programming"`, so it had never received fill-in-the-blank code exercises despite "Python" appearing in both its goal and its title.

**Alternatives considered**:
- **Constrain `category` to an enum at course creation** — rejected. It would invalidate five existing courses, and it pushes a taxonomy decision onto a learner describing a goal in their own words.
- **Store a resolved language column** — rejected. It is a pure function of three columns already present, so a column adds a migration and a staleness risk (edit the goal, the column lies) for nothing.

**Reason**: `app/services/course_profile.py` resolves target language, TTS voice and Python-ness by matching keywords across goal, category and title together — which is where the signal actually lives. Both call sites now delegate.

Two sub-decisions worth recording. `is_python` stays Python-specific rather than a generic `is_code`, because `question_fill_blank.txt` emits Python and a JavaScript course must not receive Python exercises. And `tts_language` degrades to English for any language Piper has no voice for, which is correct rather than merely safe: enrichment writes definitions in English and quotes target-language material inline, so an English voice reading an English definition is right — while Whisper, which *is* multilingual, still receives the true target language for pronunciation checking.

**Status**: Active.

----

## 2026-08-16 — A dedicated `/review/courses`, not `GET /courses`'s progress summary

**Context**: The review hub needs per-course due counts. `GET /courses` already returns `progress_summary.due_now` per course, so reusing it looked free.

**Reason**: `course_progress()` takes no filter arguments, so it cannot answer "how many are due in this course *given these filters*". The moment a date filter is applied, the picker's numbers would disagree with the session it launches — the hub would be lying about what the user is about to get. The new endpoint applies exactly the same `_apply_card_filters` helper as `/review/next` and `/review/queue`, and there is a test asserting hub count == session count under the same filter. It is also one `GROUP BY` over the existing `(course_id, due)` index rather than four COUNT queries per course.

Two query mechanics documented rather than "fixed": `cards.due` is TEXT ISO-8601, so due-range filtering is a lexicographic string comparison — valid only because every value is written as normalised UTC ISO, which is the same assumption `Card.due <= now_iso` has always relied on. And `cards.course_id` is nullable, so grouping excludes NULLs explicitly rather than emitting a blank row.

**Status**: Active.

----

## 2026-08-16 — Drills derived from stored content, with no LLM call at drill time

**Context**: Four new practice drills were needed to cover the VARK modalities that the read-and-type review loop does not reach. The obvious route would be to generate each drill with the LLM on demand.

**Alternatives considered**:
- **Generate drill items per session with Ollama** — rejected. Every drill would inherit a multi-second wait, a failure mode, and non-determinism; a learner retrying a drill would get different questions, and the app would stop working offline.

**Reason**: The enrichment pass already stores key concepts (name, definition, example), a worked example, pitfalls and practice prompts per lesson. All five drills are pure functions of that, seeded deterministically per course and kind. They start instantly, work with Ollama stopped, and produce the same items for the same content — which also makes them testable without stubbing an LLM.

Consequential sub-decisions:
- **Distractor pools are course-wide, not per-lesson.** With one or two lessons enriched, a per-lesson pool routinely cannot field four options. Below the floor (3 concepts for MCQ, 4 for match, 3 steps for order) the drill reports **unavailable with a reason** rather than being padded with filler or borrowing from another course, which would be incoherent.
- **Grading is client-side**; the answer travels in the payload. This is self-directed study, not assessment, and it buys zero-latency feedback. A deliberate trade-off, not an oversight.
- **The listening drill never sends the spoken text.** Audio is synthesised once, cached by content hash, and served by the existing `/audio/{filename}`; sending the definition would let the learner read instead of listen and defeat the drill entirely.
- **Drills record a `DRILL_COMPLETED` event but do not touch FSRS.** Practice is not scheduled review; feeding drill results into the scheduler would corrupt the stability estimates the review system depends on. They still feed streaks and achievements.

**Status**: Active.

----

## 2026-08-16 — Worked-example steps are split on markers, not only newlines

**Context**: The ordering drill splits a lesson's `worked_example` into steps. `lesson_content.txt` explicitly asks the model to separate steps with a newline escape inside the JSON string.

**Reason**: It does not comply. Checking the three enriched lessons in the live database, *all three* returned a single line of `"Step 1: ... Step 2: ... Step 3: ..."`. Splitting on newlines alone therefore produced one step for every real worked example, which silently made the kinesthetic drill permanently unavailable — the availability manifest reported "no worked example with enough steps yet" for content that plainly had four.

`split_steps` now tries newlines, then falls back to splitting before `Step N:` markers, then before `N.` numbering. Tightening the prompt was considered and rejected as the primary fix: the parser has to tolerate what the model actually emits, and a prompt cannot be relied on to hold a format it has already been asked for once.

Worth noting as a general lesson for the report: this defect was invisible to the test suite, because the fixtures used the newline-separated shape the prompt *specifies* rather than the inline shape the model *produces*. It only surfaced by running the generator against real stored content.

**Status**: Active.

----

## 2026-08-17 — HttpOnly session cookie rather than a bearer token

**Context**: The application needed authentication. A JWT in `localStorage` with an `Authorization` header is the more conventional choice and the easier one to write up.

**Reason**: It is not viable here, and the constraint is structural rather than stylistic. `/audio/{filename}` is consumed by `new Audio(...)` in `AudioPlayer.tsx` and `ListenDrill.tsx`, and the certificate is fetched as a blob. A browser-issued media request **cannot carry an `Authorization` header**, so a bearer scheme would have required either signed short-lived URLs or rewriting both media paths to fetch-then-`createObjectURL`. A cookie is sent automatically: `new Audio(url)` issues a no-CORS request that carries it, and `localhost:5173` → `localhost:8000` is same-site (port is not part of "site"), so `SameSite=Lax` permits it. The media paths needed **zero** frontend changes.

Two supporting points: CORS already had `allow_credentials=True` with a single explicit origin, so nothing there changed; and `HttpOnly` means the token is not readable by injected script, which `localStorage` cannot offer.

Sessions are server-side (`auth_sessions`, opaque `secrets.token_urlsafe(32)`) rather than a signed stateless token, so logout genuinely revokes and the table doubles as a login record. `secure=False` is deliberate and commented — a `Secure` cookie is silently dropped over plain HTTP, which `http://localhost` is. A cross-host deployment would need `samesite="none"` with `secure=True` together.

**Status**: Active.

----

## 2026-08-17 — Passwords hashed with stdlib `hashlib.scrypt`

**Context**: Registration needs password hashing. bcrypt and argon2id are the standard answers.

**Alternatives considered**: `passlib[bcrypt]` and `argon2-cffi` — both stronger, both requiring a compiled wheel. Days before a submission deadline, a dependency that can fail to build on a marker's machine is a real risk against a marginal security gain for a single-machine local application.

**Reason**: `scrypt` is memory-hard, is in the standard library, and needs nothing installed. Parameters are `n=2^14, r=8, p=1` — OWASP's stated floor — with a 16-byte per-hash salt and an explicit `maxmem` (the OpenSSL default 32 MB cap would produce an opaque failure if `n` were ever raised). Measured at ~40 ms per hash on the target machine.

The stored format is self-describing — `scrypt$n$r$p$salt$hash` — specifically so a rehash-on-login migration to argon2id stays open without a schema change. `verify_password` returns `False` rather than raising on a malformed value, because a corrupted column must fail the login, not 500 the route.

**Status**: Active. Production would use argon2id; the encoded-parameter format is the migration path.

----

## 2026-08-17 — Single-owner-per-course, not enrolment

**Context**: Deciding how far `user_id` needed to propagate.

**Reason**: `Course` is the root of a strict tree — `Course → Module → Lesson → {Objective, Question → Card → Review}` — with single-valued foreign keys at every level and no join table, fork or share feature. So a `user_id` column is only needed in **four** places: `courses`, and the three genuinely global tables that have no path to a course (`user_events`, `study_sessions`, `user_achievements`). Everything else — chat messages, narration cache, certificate cache, content embeddings, questions, cards — is owned transitively, because a lesson belongs to exactly one course which belongs to exactly one user.

`cards` was deliberately **not** given a denormalised `user_id` despite already carrying a denormalised `course_id`. A join cannot be wrong; a copied column can, and `cards.course_id` already has a drift-repair script. At 175 rows the subquery cost is unmeasurable. `Card.course_id.in_(...)` also fails *closed* on a NULL, which is the direction you want.

**The limitation, stated plainly**: this is single-owner, not enrolment. `lessons.completed_at` living on the shared content row is precisely what makes it single-tenant. Supporting a course shared between learners would require an `enrolments(user_id, course_id)` join table and moving all per-user progress — completion, cards, chat, narration — out of the content tree. That is a restructure, not an addition.

**Status**: Active.

----

## 2026-08-17 — Router-level dependency, not auth middleware

**Context**: The gate had to cover 12 routers while leaving `/`, `/health`, the OpenAPI routes and `/auth/*` public.

**Alternatives considered**: `@app.middleware("http")` or `add_middleware`. Rejected for three concrete reasons, each independently sufficient:
1. **CORS ordering.** Starlette applies middleware in reverse, so an auth middleware added after `CORSMiddleware` becomes the outermost layer — 401 responses would then carry no `Access-Control-Allow-*` headers, the browser would report an opaque network error, and the frontend would never see the status to redirect on.
2. **Streaming.** `POST /lessons/{id}/chat` returns an SSE `StreamingResponse`, and `BaseHTTPMiddleware` has a history of interacting badly with long-lived streams.
3. **Testability.** Middleware cannot be disabled by `dependency_overrides`, which would have meant rewriting all 16 test files instead of adding one autouse fixture.

**Reason**: `dependencies=[Depends(current_user)]` at `include_router` time. The exemptions fall out of the structure rather than a path-matching table: `/`, `/health` and the OpenAPI routes are declared on `app` rather than a router, and `/auth` is the one router included without the list. `test_route_coverage.py` walks `app.routes` and asserts the dependency is present on everything else, so a route added later cannot silently escape the gate.

**Status**: Active.

----

## 2026-08-17 — Ownership violations return 404, not 403

**Context**: When user B requests user A's course, the response could be 403 (exists, forbidden) or 404 (as if absent).

**Reason**: 404, for two reasons. A 403 confirms the id exists, so a leaked URL, screenshot or log line becomes an existence oracle. And every one of these routes *already* raised 404 with the same detail string for an unknown id — reusing it meant the 22 `ErrorState` consumers, the frontend error handling and the existing tests needed no new branch at all. 403 is more debuggable; 404 is more private and cost nothing here.

**Status**: Active.

----

## 2026-08-17 — Rate limiting deliberately out of scope

**Context**: Login is unthrottled, as are the compute-heavy `/transcribe`, `/tts` and LLM endpoints.

**Reason**: Account lockout is a self-inflicted denial of service during a live demonstration or a marking session, and there is no shared deployment for which throttling would be defending anything — the application runs on one machine for one person. The proportionate controls that *are* present: byte-identical responses for wrong-password and unknown-email (verified against a module-level dummy hash so the timing matches), an 8–128 character password bound (the maximum matters — without it a multi-megabyte password is a free 16 MiB-per-attempt hashing DoS), and session revocation on logout.

Recorded rather than omitted because it is the obvious next control, and knowing why it was left out is part of the answer.

**Status**: Deferred, deliberately.

----

## 2026-08-17 — Light theme added as an override, never as an edit to dark

**Context**: The application was dark-only — one `@theme` block, `color-scheme: dark`, hardcoded meta tags, and zero occurrences of `matchMedia` or `dark:` anywhere in `src/`.

**Alternatives considered**: The conventional Tailwind approach is a `dark:` variant on every colour-bearing class. Rejected: it inverts the default — dark becomes the exception written 300+ times — and every one of those call sites is an opportunity to miss one, with no way to prove none were missed.

**Reason**: Dark stays in `@theme` as the bare `:root` default and is **byte-identical** to before the file gained a second theme. Light is applied purely as an override through two selectors: `@media (prefers-color-scheme: light) :root:not([data-theme="dark"])` for following the OS, and `:root[data-theme="light"]` for an explicit choice. Making the change additive means the designed theme cannot regress, which matters concretely because every screenshot already in the report is dark.

Two properties were verified against the compiled CSS *before* committing to this approach, because the whole plan rests on them:
1. **Opacity modifiers resolve at runtime.** `bg-success/12` compiles to `color-mix(in oklab, var(--color-success) 12%, transparent)`, so retuning a hue per theme reaches all ~67 tint sites without touching a single className. (The static hex emitted alongside is the pre-`color-mix` fallback; a browser predating Chrome 111 / Safari 16.2 keeps dark-tuned tints. Accepted.)
2. **Tokens are overridable.** They land on `:root,:host` as plain custom properties, and nothing uses `@theme inline`, so `:root[data-theme="…"]` wins on specificity.

The claim is checked rather than asserted: diffing the compiled custom-property block against a build of the pre-theme commit shows **105 retained dark tokens, 0 changed values**. Three vars disappear only because Tailwind prunes vars with no remaining consumer (`brand-50`, `brand-900`, `white` were renamed to `on-heat-2`, `heat-1`, `on-brand`, each carrying an identical value).

The light palette is tuned, not inverted. The surface ramp inverts in luminance while keeping its *role*: `surface` is white so cards lift off a grey `canvas`, and `surface-raised` goes **darker**, because it means "interactive", not "brighter". Semantic hues are deepened, since the dark palette's mint and amber at 8–15% over white are colourless washes.

**Cost**: the two light blocks are necessarily duplicated — one lives inside a media query — and must be edited together or the toggle and the OS disagree. A comment says so, and the two blocks are diffable.

**Status**: Active.

----

## 2026-08-17 — Elevation and logo tokens deliberately kept out of `@theme`

**Context**: Two tokens broke the assumption that a `@theme` value can be overridden per theme. Both failures were silent.

**Reason**: **Tailwind resolves `@theme` keys at build time.** `--shadow-e1` in `@theme` compiles to `.shadow-e1{--tw-shadow:0 1px 2px var(--tw-shadow-color,#0006);…}` — the value is *inlined* and no `var(--shadow-e1)` survives into the output. The light theme's `--shadow-e1..e4` overrides were therefore dead CSS, and light mode would have painted the dark theme's 40–70% black shadows onto a white canvas. This is a bad failure mode precisely because it degrades gradually: the page still works, it just looks muddy, so it survives casual review.

The six elevation tokens now live in a plain `:root` block with the utilities written out by hand, which keeps the `var()` reference at **runtime**. Cost: they no longer compose with `ring-*` or accept a `shadow-<color>` modifier. Neither is used — the only non-focus ring in the codebase sits on a heatmap cell carrying no shadow, and focus styling is `outline`-based.

The same class of problem, different mechanism, hit the logo. Its gradient ran `brand-400 → brand-600`, but light retunes the upper brand ramp downward so brand-coloured *text* stays legible on white — which moved `brand-400` to `#6a3ce8`, exactly `brand-600`. The tile rendered as a flat fill with no gradient, and stopped matching `public/favicon.svg`. It now reads `--color-logo-from` / `--color-logo-to`, which hold still across all three theme states. These are also declared outside `@theme`, because their only consumer is a `var()` in a `.tsx` file rather than a utility class, and `@theme` prunes tokens no utility references.

**The general lesson**, worth more than either fix: a design token is only themeable if a `var()` reference reaches the browser. "I overrode the token" and "the override has an effect" are different claims, and only the compiled stylesheet can distinguish them.

**Status**: Active.

----

## 2026-08-17 — The theme control lives in an auth-gated user menu

**Context**: `TopNav` rendered the email and Sign out inline, with Sign out duplicated again in the mobile drawer. The appearance control needed a home.

**Alternatives considered**: A bare toggle button in the nav. Rejected because a two-state toggle cannot express "follow the OS" — once a user touches it they are pinned to an explicit choice with no way back, which defeats the chosen default.

**Reason**: A single `UserMenu` replaces both Sign out sites and carries a three-option radiogroup (System / Light / Dark), making System a reachable state rather than merely an implied initial one.

**Accepted consequence, stated rather than hidden**: the menu is auth-gated, so there is **no toggle on the login page**. Someone signing in still gets the correct theme, because the default follows the OS — they simply cannot override it until signed in. The alternative, duplicating the control into an unauthenticated surface, was not worth it for one screen.

Related: the preference persists under a bare `theme` key rather than a user-namespaced one like `LessonView`'s bookmark, precisely because the login page renders before a `user` exists.

**Status**: Active.

----

## 2026-08-17 — Diagrams are generated as semantic specs, never as SVG

**Context**: Lessons were text-only. A chess lesson described the knight's move in prose and an ML lesson described a sigmoid in words. The request was for SVG and light animation rather than images — "where images might be overkill".

**First, a finding**: there was no image-model implementation in the repository to build on. An exhaustive sweep — source, `pyproject.toml`, `uv.lock`, `.env*`, every branch, the full git history, the stash list — found nothing; `pillow` and `torch` are transitive dependencies of `sentence-transformers` and `weasyprint`. `docs/future-work.md` had recorded image and video generation as cut from scope. This turned out not to matter: the feature needs no image model at all.

**Alternatives considered**: the model emitting SVG markup directly, sanitised and injected. Rejected for four independently sufficient reasons.
1. **Reliability.** Asking `llama3.1:8b` for `{"at": "d4"}` is a request it can satisfy; asking it to place 64 `<rect>` elements by hand is one it fails at subtly, because a single wrong coordinate still parses and still renders.
2. **Injection.** `react-markdown` v10 ships without `rehype-raw`, so raw HTML in lesson prose is already discarded, and the repo carries no sanitiser. Model SVG would have introduced both the app's first HTML-injection surface and its first sanitiser dependency.
3. **Theme.** A model writing SVG writes `fill="#f0d9b5"`. Renderers write `var(--color-brand-500)`. The app resolves light and dark from the same markup, so a literal is correct in one theme and wrong in the other.
4. **Motion.** SVG `<animate>`/SMIL is untouched by `MotionConfig reducedMotion="user"` and by the `prefers-reduced-motion` CSS block. Driving animation through motion/react keeps the existing guarantee.

**Reason**: the model returns *meaning* and code computes *geometry*. It names one of four kinds — `board`, `graph`, `plot`, `geometry` — and fills semantic fields; the renderers derive every coordinate. This is the same bargain `drills.py` already makes, where drills are a deterministic function of stored content with no LLM call at render time.

Two constraints inside the schema matter more than they look. A `plot` series is never an expression string: it is explicit points, or a named family (`sigmoid`, `normal`, …) with numeric parameters, so there is no path from generated text to anything evaluated. And a `geometry` shape is positioned from side lengths rather than coordinates, which is what turns "can this triangle exist" into a validator check instead of a drawing that silently comes out wrong.

**Status**: Active.

----

## 2026-08-17 — Reject false claims, repair presentation

**Context**: The validator has to decide what to do with a spec that is imperfect. Rejecting means the lesson gets no diagram; accepting means it may get a wrong one.

**Reason**: The two are not symmetric, and the line between them is whether the flaw is a *claim about the world* or a *choice about presentation*.

**Rejected**, because they are false: an edge to a node that does not exist; a triangle whose sides cannot close; an inverted axis range; a step referencing an element that is not in the diagram (which would play and highlight nothing); and — added after the fact, see below — highlighted squares a piece could not actually reach.

**Repaired**, because they are stylistic: a `tree` layout whose data is not a tree, or a `chain` whose data branches, downgrades to `layered`, which draws both correctly. The nodes and edges have already been checked and they are the content; throwing them away over a layout keyword converts a correct picture into no picture. An over-long node label is clipped rather than rejected, since the renderer truncates far below the cap anyway and length carries no truth value.

**Ignored**: unknown keys. A small model routinely adds a stray `"notes"`, and discarding a sound diagram over one trades a real diagram for none.

**The asymmetry that decides all of these**: a missing diagram is invisible; a wrong one teaches something false. So the validator errs strict on truth and forgiving on form.

**Status**: Active.

----

## 2026-08-17 — Piece movement is validated in code, not trusted to the model

**Context**: Generating against the live Chess Fundamentals course produced a bishop on e2 highlighting a1, h8, a8, h1, c4 and f5. Only c4 is on a diagonal from e2.

**Reason**: Every one of those is a legal square on an 8×8 board, so no structural check could reject it. It was drawable, plausible, and a completely false picture of how a bishop moves — the exact failure the whole semantic-spec design exists to prevent, arriving through the one door the design had left open.

The principle was already stated: the model returns meaning, code computes geometry. Which squares a piece can reach *is* geometry. Trusting it to the model was simply an incomplete application of the project's own rule.

Board specs are now checked against real movement for knight, bishop, rook, queen and king, accepting either letter or Unicode glyphs. Three deliberate exemptions keep it from over-firing: highlights may be a **subset** of the legal moves, since illustrating two of a knight's eight is legitimate; a piece's **own square** may be highlighted; and **pawns and non-chess glyphs skip the check entirely**, so a board used as a coordinate grid or a matrix is unconstrained.

**The known limit, stated rather than implied**: this validates *geometry*, not *chess*. A castling diagram passed because the king's destination happened to lie on the rook's rank, and a caption claiming the king moves three squares cannot be checked at all. Reachability catches the class of error that was actually observed; it is not a rules engine.

**Status**: Active.
