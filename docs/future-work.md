# Future Work

Anything cut from scope, or any feature idea that surfaces during development. Lives here, not in the build. Promoted into the report's Conclusion as "future work" — examiners like seeing this.

## Cut from initial scope

- Video generation for course content (out of scope: too expensive in time, weak local models)
- Slide/presentation generation (out of scope: nice-to-have, not load-bearing)
- Sentiment/difficulty classifier for adaptive difficulty (deferred: FSRS already covers difficulty)
- Music goal category — piano, theory (out of scope: needs audio analysis pipeline of its own)
- Visual skills — Blender, drawing (out of scope: image-quality assessment is unreliable)
- Physical skills — dance, yoga (out of scope: needs pose estimation, separate problem)
- Multi-user accounts and authentication (single-user local app is sufficient)
- Cloud deployment (local-only is the design; runs offline is a feature)
- Mobile app (web-only this version)

## Ideas that surfaced during development

_(Add here as they come up. Don't act on them.)_

- **Listening clues in the target language for language courses.** The clue pass writes English prose even when the course is Spanish, and the drill then synthesises it with a Spanish voice — so the aural drill is a Spanish speaker reading an English description. It is comprehensible and arguably still a listening exercise, but it does not test target-language comprehension, which is what an aural drill in a language course ought to be doing. A per-course decision is already available (`course_profile.is_language_course`) and the drill's availability is already gated on the profile, so this is a prompt branch rather than new plumbing. Worth doing only once the course has enough target-language material to describe concepts in it — the definitions are written in English and quote the target language inline, so the grounding for a Spanish clue is thinner than it looks.

- **Masking as a second line of defence.** The clue validator rejects a description that names its own term, but a sufficiently novel inflection could still slip past a form-based comparison. Deterministically replacing any surviving occurrence with a neutral phrase before synthesis would close that gap at the cost of slightly stilted audio. Not worth it while the measured leak rate is zero; revisit if the eval ever reports a non-zero value.
