# Information Architecture

Recorded: 2026-07-19

---

## Five destinations

| Route | Purpose | Primary action |
|---|---|---|
| `/` | Home / entry point | "Start a new goal" or "Continue a course" |
| `/courses` | Course library | Pick a course to open |
| `/courses/:id` | Course home | Continue a lesson, or start review |
| `/courses/:id/lessons/:id` | Lesson view | Study the questions for this lesson |
| `/courses/:id/review` | Review session (course-scoped) | Rate cards |

Plus `/review` for a global cross-course review session (all courses, ordered by due date).

---

## Transitions

Every transition is deliberate — no destination is entered accidentally.

```
/
├── "Start new goal" form → POST /courses → /courses/:id (new course home)
└── "Continue" card       → /courses/:id (existing course home)

/courses
└── Click course card → /courses/:id

/courses/:id
├── Click lesson title  → /courses/:id/lessons/:id
└── "Start review"     → /courses/:id/review

/courses/:id/lessons/:id
├── "Mark complete"    → stays on page, shows completion badge
└── "Back to course"   → /courses/:id

/courses/:id/review
├── Answer + rate card → next card (same page, loop)
└── "Done" (204)       → /courses/:id

/review (global)
├── Answer + rate card → next card (same page, loop)
└── "Done" (204)       → /
```

---

## Empty states

| Destination | Empty condition | What the user sees |
|---|---|---|
| `/` | No courses yet | Prompt: "What do you want to learn?" with goal input |
| `/courses` | No courses | Same as `/` — redirect or inline goal input |
| `/courses/:id` | Course has no modules | Shouldn't happen (course always has structure); show error |
| `/courses/:id/lessons/:id` | Lesson has no questions yet | "Generate questions" button prominent |
| `/courses/:id/review` | No cards due | "Nothing due right now. Check back later." + link back to course |

---

## Key IA decisions

**1. One lesson per page, not all lessons on the course page.**
The course home is a navigation hub. Showing full lesson content inline creates an
ever-growing scroll that users abandon. Each lesson is its own destination with its own
focus and back-navigation.

**2. Course home is a navigation hub, not a content dump.**
It shows: course title/description, module + lesson tree (titles, durations, completion
badges), progress summary (completed/total lessons, cards due), and two primary actions
(Continue lesson / Start review). It does not show objectives, question text, or code snippets.

**3. Review is a separate destination, entered deliberately.**
Studying new content (reading objectives, generating questions) and actively recalling via
spaced repetition are cognitively distinct tasks. They happen at different times in a
learning session and should look and feel different. The course home links to both; neither
auto-starts the other.

**4. Questions live under lessons in navigation; cards are course-scoped for the query.**
`GET /courses/:id/lessons/:id` returns questions for that lesson (so the lesson view can show
them). `GET /review/next?course_id=:id` queries cards by `course_id` (not `lesson_id`) because
the FSRS scheduler interleaves cards across all lessons in a course — restricting review to one
lesson at a time would break the scheduling algorithm's assumptions.

---

## Mapping of current pages to new destinations

| Current page | Maps to | Notes |
|---|---|---|
| `GoalInputPage` (`/`) | `/` (Home) | Keep as-is; add course list if courses exist |
| `CourseViewPage` (`/courses/:id`) | `/courses/:id` (Course home) | Strip inline lesson content; show nav tree + progress |
| `ReviewSessionPage` (`/review`) | `/courses/:id/review` + `/review` (global) | Needs `courseId` forwarded from course home |
| `PronunciationDrill` (`/pronunciation`) | Stays at `/pronunciation` | Not part of course IA; standalone tool |
| *(missing)* | `/courses` (Course library) | New page |
| *(missing)* | `/courses/:id/lessons/:id` (Lesson view) | New page |
