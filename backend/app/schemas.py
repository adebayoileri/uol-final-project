from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CourseRequest(BaseModel):
    goal: str = Field(..., min_length=10, max_length=1000)
    duration: Literal["short_term", "long_term"]
    #: A value from `GET /courses/categories`, the sentinel "auto" to have one
    #: chosen from the goal, or anything else the learner typed under "Other".
    category: str = Field(..., min_length=2, max_length=100)


class CategoryOption(BaseModel):
    """One entry in the category vocabulary, as the form needs to render it."""

    value: str
    label: str
    group: str
    note: str = ""


class CategorySuggestionRequest(BaseModel):
    #: Lower than `CourseRequest.goal`'s 10 because this endpoint is called while
    #: the learner is still typing; it is a preview, not a submission.
    goal: str = Field(..., min_length=3, max_length=1000)


class CategorySuggestionResponse(BaseModel):
    value: str
    label: str
    group: str
    note: str = ""
    #: "model" when the LLM chose, "keyword" when it was unavailable or invented
    #: an answer and the deterministic matcher took over, "default" when nothing
    #: matched. The form uses this to decide how loudly to present the result.
    source: Literal["model", "keyword", "default"]


class ObjectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    description: str


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    title: str
    description: str
    duration_minutes: int
    completed_at: datetime | None
    objectives: list[ObjectiveResponse]


class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    title: str
    description: str
    lessons: list[LessonResponse]


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    duration: str
    category: str
    title: str
    description: str
    created_at: datetime
    modules: list[ModuleResponse]


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    text: str
    reference_answer: str
    question_type: str
    code_snippet: str | None
    created_at: datetime


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=2000)


class AnswerResponse(BaseModel):
    verdict: Literal["correct", "incorrect"]
    score: float
    signal_used: Literal["embedding", "embedding+llm", "llm"]
    explanation: str | None = None


class CardResponse(BaseModel):
    id: str
    question_id: str
    question_text: str
    question_reference_answer: str
    question_type: str
    code_snippet: str | None
    state: int
    stability: float | None
    difficulty: float | None
    due: str  # ISO 8601 UTC
    # Provenance, so a cross-course session can say where a card came from.
    course_id: str | None = None
    course_title: str | None = None


class GradeRequest(BaseModel):
    card_id: str
    rating: int = Field(..., ge=1, le=4)  # 1=Again 2=Hard 3=Good 4=Easy


class GradeResponse(BaseModel):
    card_id: str
    rating: int
    stability: float | None
    difficulty: float | None
    due: str
    state: int


class TranscriptionResponse(BaseModel):
    text: str
    duration_seconds: float


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    lang: Literal["en", "es"] = "en"


class WordDiffItem(BaseModel):
    op: Literal["match", "missing", "extra", "substituted"]
    expected: str | None
    actual: str | None


class PronunciationCheckResponse(BaseModel):
    expected_text: str
    transcribed_text: str
    diff: list[WordDiffItem]
    accuracy: float


class SearchResultItem(BaseModel):
    content_type: str
    content_id: str
    content_text: str
    course_id: str
    lesson_id: str | None
    score: float


class ReviewQueueResponse(BaseModel):
    total: int
    due_now: int
    due_today: int
    due_this_week: int


class ReviewCourseGroup(BaseModel):
    """One row of the review hub's course picker."""

    course_id: str
    title: str
    category: str
    total_cards: int
    due_now: int
    oldest_created_at: datetime | None = None
    newest_created_at: datetime | None = None


class ProgressSummary(BaseModel):
    total_lessons: int
    completed_lessons: int
    total_cards: int
    due_now: int


class CourseSummaryResponse(BaseModel):
    id: str
    title: str
    category: str
    created_at: datetime
    progress_summary: ProgressSummary


class KeyConceptResponse(BaseModel):
    name: str
    definition: str
    example: str = ""


class LessonContent(BaseModel):
    """Deep teaching content, generated lazily per lesson."""

    key_concepts: list[KeyConceptResponse] = []
    worked_example: str | None = None
    common_pitfalls: list[str] = []
    practice_prompts: list[str] = []


class LessonEnrichResponse(BaseModel):
    status: Literal["cached", "generated"]
    content: LessonContent | None


class LessonDiagramResponse(BaseModel):
    status: Literal["cached", "generated"]
    # Validated on the way in by app.diagram_spec; passed through as plain
    # dicts on the way out so a new diagram kind needs no change here.
    diagrams: list[dict]


class LessonClueResponse(BaseModel):
    """Response for the listening-clue generation endpoint.

    Deliberately carries no clue text. The clue is the audio question, so a
    client that could read it would not have to listen — the same reason
    `build_listen` never sends the spoken string. The only caller that needs the
    text is the drill endpoint, which synthesises it server-side.
    """

    status: Literal["cached", "generated"]


class LessonDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    title: str
    description: str
    duration_minutes: int
    completed_at: datetime | None
    objectives: list[ObjectiveResponse]
    questions: list["QuestionResponse"]
    # Populated from the Lesson.content property; None until enriched.
    content: LessonContent | None = None
    # From Lesson.diagrams. None until generation has been attempted; an empty
    # list means the model was asked and correctly said no diagram helps.
    diagrams: list[dict] | None = None
