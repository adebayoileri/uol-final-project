# Report Notes

Continuous notes feeding the final 7000-word report. **Add to this file at the end of every working session — 5 minutes, every time.**

The 6 chapters are fixed by the marking scheme. Drop bullet points under the relevant heading. Don't write prose yet — that comes in Phase 4 (Week 18 draft) and Phase 5 (Weeks 20–21 polish).

When you add an entry, prefix it with the date so you can reconstruct your thinking timeline later.

---

## 1. Introduction

_What problem does this project solve? Why does it matter? What's the scope?_

- 2026-05-04: Project framing — combining multiple pre-trained models to generate personalised courses with spaced repetition. Distinguishes from existing tools (Duolingo, Anki, Khan Academy) by being goal-driven rather than content-driven.
- 

## 2. Literature Review

_What's been done before? What models exist? What's the state of the art in spaced repetition, automated assessment, LLM-generated education?_

- 2026-05-04: Reading list to cover in Week 2 — FSRS paper (Ye et al.), SM-2 original paper, supermemo.guru incremental learning articles, 2-3 papers on LLM-generated educational content, 1-2 papers on automated assessment.

- 2026-05-10: Reading FSRS paper (Ye et al.) ahead of the proposal video. The paper introduces the FSRS model, which predicts recall probability for spaced repetition. It outperforms SM-2 and other baselines on multiple datasets. Key features include modeling item difficulty, learning decay factors, and incorporating user/item features. This informs our choice to implement FSRS for scheduling in the project, as it represents the state of the art in spaced repetition algorithms. 

- 2026-05-26: Reading AI engineering book written by Chip Huyen, the book shares insights on working with foundation models and difference between the concepts AI and ML engineering. It also provides with useful information on techniques on how to get desirable behaviors from foundation models. 

- 2026-06-13: Added a new /courses endpoint with the database model `courses` to generate a course using Llama3.1:8b model
- 2026-06-14: Implemented tests for the courses endpoint



## 3. Design

_System architecture, model choices with justification, data flow, schema design._

- 2026-05-04: Initial stack chosen — see decisions.md for full rationale.
- 2026-05-04: Architecture sketch — frontend (React) → API (FastAPI) → [Ollama + Whisper + embeddings + Piper] → SQLite. All local.

- 2026-07-19 IA rationale (R3). The five-destination IA (Home / Course library / Course home / Lesson view / Review session) separates two cognitively distinct activities: encoding (reading a lesson, generating questions) and retrieval (FSRS review). The old single-page course view conflated both, making it impossible to scope the review queue to a single course. The key IA decisions were: (1) one lesson per page — prevents cognitive overload and enables per-lesson completion tracking; (2) course home as navigation hub, not content — all learning happens in dedicated sub-pages; (3) review as a named destination with a dedicated route, not a popup — signals that review is a first-class activity, not a footnote; (4) course_id on cards and questions (denormalised) — the data model follows the IA rather than forcing the IA to work around the data model.

- 2026-07-19 Restructure decision: denormalised course_id vs. join-time derivation. Adding course_id as a column on questions and cards (R1) rather than deriving it at query time (3-hop join: card → question → lesson → module → course) was a deliberate trade-off. The join approach is pure but slow for the review query pattern where we need to filter by course_id in `ORDER BY due LIMIT 1`. The column + composite index `(course_id, due)` gives O(log N + k) for the common case. Backfilling existing rows via UPDATE … SELECT ensures no data migration downtime.

## 4. Implementation

_What did you actually build? Key technical challenges and how you solved them._

- 2026-07-19 R6 — Validation walkthrough. Deleted dev database (fresh start). API-level walkthrough confirmed: 3 courses (Python, Spanish, ML) each with 4 lessons and 8 due cards; course list returns correct progress_summary; lesson detail returns objectives + questions; POST /lessons/:id/complete is idempotent and increments completed_lessons; review/next?course_id= returns only cards from that course (verified card question text matches the seeded course content); review/next without param returns global queue; wrong course+lesson pair → 404; unknown course_id → queue={due_now:0} + next=204. UX friction review (approximating one-person test): top-2 issues found and fixed — (1) "Continue" button showed no context about which lesson it led to; fixed by adding "Next: {lesson.title}" subtitle; (2) when all lessons are complete the Continue button disappeared with no explanation; fixed by replacing it with "✓ All lessons complete — keep reviewing to reinforce your knowledge." 122 backend tests still passing.

- 2026-07-19 R5 — Frontend rebuild (five-destination IA). Deleted GoalInputPage, CourseViewPage, ReviewSessionPage. Replaced with: Home (goal form + "Continue learning" CTA for returning users), CourseLibrary (course list with progress bar + due-now badge), CourseHome (parallel fetch of course tree + review queue; two CTAs; module accordion with completion checkmarks; no inline question rendering), LessonView (objectives → description → one-at-a-time question study with localStorage index persistence → Mark complete → back to CourseHome), ReviewSession (scoped via route param or global; sessionTotal from queue count; answering→feedback state machine; 1–4 keyboard shortcuts for FSRS rating; done/empty states). Updated api.ts: added completed_at to LessonResponse, added ProgressSummary/CourseSummaryResponse/ReviewQueueResponse/LessonDetailResponse types, added getCourses/getReviewQueue/getLessonDetail/completeLesson functions, updated getNextCard to accept optional courseId. TypeScript clean (0 errors).

- 2026-07-19 R3+R4 — Information architecture and backend. Recorded 5-destination IA in `docs/information-architecture.md` (Home, Course library, Course home, Lesson view, Review session). R4 added: `GET /courses` list with per-course `progress_summary` (`{total_lessons, completed_lessons, total_cards, due_now}`) via 4 indexed COUNT queries per course; `GET /courses/:id/lessons/:id` returning full lesson + questions for the lesson view; `POST /lessons/:id/complete` (idempotent, sets `completed_at` once) to track lesson-reading progress separately from FSRS card state. `Lesson.completed_at` column added via migration. New `backend/app/services/progress.py`. 10 new tests (list, lesson detail, completion idempotency, progress increment).

- 2026-07-18 R2 — Review scoping. `GET /review/next` now accepts an optional `?course_id=` query param; without it the endpoint returns the globally next due card (all-courses mode); with it, only cards from that course are returned. Added `GET /review/queue` returning `{total, due_now, due_today, due_this_week}` with the same optional scope, for the review-hub UI. 4 new tests cover: in-scope card returned, out-of-scope card excluded even when due, future card in scope → 204, queue counts with mixed due dates.

- 2026-07-18 Sub-phase 3C — Semantic search over course content. Added a `content_embeddings` table (content_type, content_id, content_text, course_id, lesson_id, vector BLOB). `index_lesson()` and `index_question()` are called automatically after course creation and question generation respectively, embedding the text with all-MiniLM-L6-v2 and storing as a 1536-byte float32 BLOB. `GET /search?q=<query>&k=5&course_id=<id>` loads candidate vectors, computes cosine similarity in numpy (no FAISS/Chroma needed at this scale), and returns top-K results. Logged latency: <5ms for 500 items. Frontend: search box on course view with 300ms debounce; results show Lesson/Question type pills, content text, and relevance %; clicking links to the course. 20 backend tests pass (5 semantic relevance pairs with real embeddings).

- 2026-07-18 Sub-phase 3B — Python fill-blank exercises and code highlighting. Added `question_type` (`"open"` | `"fill_blank"`) and `code_snippet` columns to the `questions` table via a startup migration (ALTER TABLE with try/except, no Alembic needed for single-user SQLite). `question_generator.py` detects Python courses via `lesson.module.course.category` and switches to a 2-open + 2-fill-blank prompt. Fill-blank answers bypass the embedding path entirely and go straight to an LLM judge (`evaluate_code_answer` in `answer_evaluator.py`), which returns a verdict, score, and a student-facing `explanation`. Added `CodeBlock.tsx` using Prism.js (Python grammar, ~8KB) — renders `# BLANK` lines in the code context; CourseViewPage shows code blocks and a "Fill blank" pill badge; ReviewSessionPage shows the code context above a monospace single-line input (Enter to submit) and displays the LLM explanation in the verdict banner. Prism over Shiki chosen for size (8KB vs ~350KB). 25 backend tests pass, TypeScript clean.

- 2026-07-18 Sub-phase 3A — Spanish pronunciation loop. Built the end-to-end pronunciation drill: browser MediaRecorder API captures audio (with `audio/webm` → `audio/mp4` fallback for Safari), uploads to `/pronunciation-check` via FormData, Whisper transcribes, `difflib.SequenceMatcher` produces word-level diff (match/missing/extra/substituted), and the frontend renders colour-coded per-word feedback (green/red/yellow/grey) with an accuracy badge. Key discovery: the entire backend was already implemented (`word_diff.py`, `speech.py`, schemas) — Sub-phase 3A only required writing the frontend page ([PronunciationDrill.tsx](../frontend/src/pages/PronunciationDrill.tsx)), wiring the `checkPronunciation` API call in `api.ts`, adding the route/nav link, and extending the test suite with Spanish-specific fixtures. Permission denial (mic blocked on Safari or Chrome) is caught and shown as a descriptive error message rather than crashing. 18 tests pass.



## 5. Evaluation

_How did you test it? Quantitative (latency, accuracy, F1) and qualitative (user testing, SUS scores). What were the results?_

- 2026-05-04: Plan to evaluate — semantic answer-checker on 50 hand-labelled pairs (precision/recall/F1); course quality rubric on 5 generated courses; FSRS simulation of 100 cards × 30 days; user testing with 5–8 participants in Weeks 15–16.


## 6. Conclusion

_What worked, what didn't, what would you do differently, future work._

- 

---

## Stray thoughts / observations / quotes

_Catch-all for things that don't fit a chapter yet. Triage these into chapters periodically._

- 


- Idea to depict the forgetting curve for an information or course content. - check the paper to see how it's calculated and how to visualize it. - 2026-05-04  