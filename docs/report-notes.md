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
- 

## 4. Implementation

_What did you actually build? Key technical challenges and how you solved them._

- 

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
