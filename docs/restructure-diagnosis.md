# Restructure Diagnosis

Created: 2026-07-18  
Baseline tag: `pre-restructure`

---

## 1. Does `GET /review/next` filter by due date and by course/user scope?

**Due-date filter: yes.**  
`backend/app/routes/review.py` line ~35:

```python
card = (
    db.query(Card)
    .filter(Card.due <= now_iso)
    .order_by(Card.due)
    .first()
)
```

`Card.due` is a `TEXT` column containing an ISO 8601 UTC string (e.g. `2026-07-18T14:30:00+00:00`).
`now_iso = datetime.now(timezone.utc).isoformat()` produces a string in the same format, so
lexicographic comparison is correct as long as all stored values use a consistent UTC offset format.

**Course filter: absent.**  
**User filter: absent.**

The query is completely global — it returns the earliest-due card across every course in the
database. There is no `user_id` column on `Card` and no `course_id` column to filter on.

**Verdict**: due-date filtering works; course/user scoping is a data-model bug (the FK does not
exist on `Card`, so no filter is possible).

---

## 2. Do questions have a foreign key back to a course, or only to a lesson?

**Only to a lesson.**

`backend/app/models.py` — `Question` model:

```python
class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = ...
    lesson_id: Mapped[str] = mapped_column(Text, ForeignKey("lessons.id"), nullable=False)
    # ... text, reference_answer, reference_embedding, question_type, code_snippet, created_at
    # NO course_id column
```

Path to a course: `question.lesson → lesson.module → module.course_id` (3 hops, requires two
JOIN operations or three lazy-load hits). Same applies to `Card` — it links to `Question` which
links to `Lesson`, with no direct `course_id`.

**Verdict**: data-model gap. Both `questions` and `cards` lack a `course_id` column.

---

## 3. Does the course view fetch the entire course tree at once?

**Yes — one eager-loaded GET.**

`frontend/src/pages/CourseViewPage.tsx` calls `getCourse(courseId)` on mount, which hits
`GET /courses/:courseId`. The backend eager-loads the full tree:

```
Course → modules[] → lessons[] → objectives[]
```

(via `selectinload` chains in `backend/app/routes/courses.py`).

**Questions are not in this payload.** They are loaded lazily per-lesson when the user clicks
"Generate questions" or "Show questions" — each triggers a separate API call. This is correct
behaviour; no change needed here.

**Verdict**: course tree fetching is correct. No issue here.

---

## 4. Do cards actually carry course scope in the data?

**No.** As established in question 2:

- `cards` table: columns are `id`, `question_id`, `state`, `step`, `stability`, `difficulty`,
  `due`, `last_review`, `created_at`. No `course_id`.
- Deriving course from a card requires: `card → question → lesson → module → course` (4 hops).
- `GET /review/next` cannot scope to a course without either a direct `course_id` on cards or
  an expensive JOIN through three intermediate tables on every request.

**Additional gap found**: the "Go to review session" link in `CourseViewPage.tsx` is:

```tsx
<Link to="/review" className="...">Go to review session</Link>
```

There is no `courseId` query param or route param. Even if the review endpoint grew a
`course_id` filter, the frontend has no mechanism to pass the current course's ID to it.

**Verdict**: data-model bug (no `course_id` on cards) + UI routing gap (link loses course context).

---

## Summary table

| Problem | Root cause | Layer |
|---|---|---|
| Review shows cards from all courses | No `course_id` on `Card`; no scope filter in `GET /review/next` | Data model + query |
| Course-scoped queries require 4-hop join | No `course_id` FK on `Question` or `Card` | Data model |
| "Go to review" loses course context | `<Link to="/review">` — no param forwarding | UI routing |
| No index on review query pattern | No composite index on `(course_id, due)` | Query performance |

## Fix order

- **R1** (this session): add `course_id` to `questions` + `cards` tables; backfill; add index.
- **R2** (next): change `GET /review/next` to accept optional `course_id` param; update
  `<Link to="/review">` to forward `?courseId=<id>` from `CourseViewPage`.
