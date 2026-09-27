import { API_URL } from "./config";

export interface CourseRequest {
  goal: string;
  duration: "short_term" | "long_term";
  category: string;
}

/**
 * One entry in the category vocabulary. Fetched rather than hardcoded so the
 * dropdown, the "Auto" classifier and the value the server stores all come from
 * one list — two copies of a taxonomy drift silently.
 */
export interface CategoryOption {
  value: string;
  label: string;
  group: string;
  note: string;
}

export interface CategorySuggestion {
  value: string;
  label: string;
  group: string;
  note: string;
  /** "model" is the LLM's answer; "keyword"/"default" mean it fell back. */
  source: "model" | "keyword" | "default";
}

export interface ObjectiveResponse {
  id: string;
  order_index: number;
  description: string;
}

export interface LessonResponse {
  id: string;
  order_index: number;
  title: string;
  description: string;
  duration_minutes: number;
  completed_at: string | null;
  objectives: ObjectiveResponse[];
}

export interface ModuleResponse {
  id: string;
  order_index: number;
  title: string;
  description: string;
  lessons: LessonResponse[];
}

export interface CourseResponse {
  id: string;
  goal: string;
  duration: string;
  category: string;
  title: string;
  description: string;
  created_at: string;
  modules: ModuleResponse[];
}

export interface QuestionResponse {
  id: string;
  order_index: number;
  text: string;
  reference_answer: string;
  question_type: string;
  code_snippet: string | null;
  created_at: string;
}

export interface CardResponse {
  id: string;
  question_id: string;
  question_text: string;
  question_reference_answer: string;
  question_type: string;
  code_snippet: string | null;
  state: number;
  stability: number | null;
  difficulty: number | null;
  due: string;
  course_id: string | null;
  course_title: string | null;
}

export interface AnswerResponse {
  verdict: "correct" | "incorrect";
  score: number;
  signal_used: "embedding" | "embedding+llm" | "llm";
  explanation?: string;
}

export interface GradeResponse {
  card_id: string;
  rating: number;
  stability: number | null;
  difficulty: number | null;
  due: string;
  state: number;
}


/**
 * Registered by AuthProvider. This module has no React context, so a 401 is
 * reported back through a callback rather than a hook.
 */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

/** Thrown on 401 so callers can distinguish "signed out" from a real failure. */
export class UnauthorizedError extends Error {
  constructor() {
    super("Not signed in");
    this.name = "UnauthorizedError";
  }
}

/**
 * The one place every request goes through.
 *
 * `credentials: "include"` is required for the session cookie to cross from
 * :5173 to :8000. `...init` is spread BEFORE headers are built, because the
 * previous shape let a caller-supplied `headers` replace the object wholesale.
 */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  // FormData must NOT get a JSON content-type: the browser has to set the
  // multipart boundary itself, and overriding it makes FastAPI return 422.
  const isForm = init?.body instanceof FormData;

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...((init?.headers as Record<string, string> | undefined) ?? {}),
    },
  });

  if (res.status === 401) {
    onUnauthorized?.();
    throw new UnauthorizedError();
  }
  return res;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, init);

  if (res.status === 204) {
    return null as T;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorMessage(body, res.status));
  }

  return res.json() as Promise<T>;
}

/**
 * FastAPI's `detail` is a string for a raised HTTPException but an ARRAY of
 * per-field objects for a 422 validation error. Reading it as a string turned
 * every validation failure into "[object Object]" in the error banner.
 */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        const entry = item as { msg?: unknown; loc?: unknown };
        const field = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : undefined;
        const msg = typeof entry.msg === "string" ? entry.msg : null;
        if (!msg) return null;
        return field ? `${String(field)}: ${msg}` : msg;
      })
      .filter((m): m is string => m !== null);
    if (messages.length > 0) return messages.join("; ");
  }

  return `Request failed with status ${status}`;
}

export function createCourse(body: CourseRequest): Promise<CourseResponse> {
  return request<CourseResponse>("/courses", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getCategories(): Promise<CategoryOption[]> {
  return request<CategoryOption[]>("/courses/categories");
}

/**
 * Preview which category a goal belongs to.
 *
 * Takes a signal because this fires while the learner types: without one, a
 * response for an earlier goal can land after a response for a later one and
 * show a stale answer with no indication it is stale.
 */
export function suggestCategory(goal: string, signal?: AbortSignal): Promise<CategorySuggestion> {
  return request<CategorySuggestion>("/courses/category-suggestion", {
    method: "POST",
    body: JSON.stringify({ goal }),
    signal,
  });
}

export function getCourse(courseId: string): Promise<CourseResponse> {
  return request<CourseResponse>(`/courses/${courseId}`);
}

export function generateQuestions(lessonId: string): Promise<QuestionResponse[]> {
  return request<QuestionResponse[]>(`/lessons/${lessonId}/questions/generate`, {
    method: "POST",
  });
}

export function getQuestions(lessonId: string): Promise<QuestionResponse[]> {
  return request<QuestionResponse[]>(`/lessons/${lessonId}/questions`);
}

export function getNextCard(
  courseId?: string,
  filters: ReviewFilters = {},
): Promise<CardResponse | null> {
  const params = reviewFilterParams(filters);
  if (courseId) params.set("course_id", courseId);
  const qs = params.toString();
  return request<CardResponse | null>(`/review/next${qs ? `?${qs}` : ""}`);
}

export interface ProgressSummary {
  total_lessons: number;
  completed_lessons: number;
  total_cards: number;
  due_now: number;
}

export interface CourseSummaryResponse {
  id: string;
  title: string;
  category: string;
  created_at: string;
  progress_summary: ProgressSummary;
}

export interface ReviewQueueResponse {
  total: number;
  due_now: number;
  due_today: number;
  due_this_week: number;
}

/** Date filters shared by the review hub and the session they launch. */
export interface ReviewFilters {
  created_from?: string;
  created_to?: string;
  due_from?: string;
  due_to?: string;
}

export interface ReviewCourseGroup {
  course_id: string;
  title: string;
  category: string;
  total_cards: number;
  due_now: number;
  oldest_created_at: string | null;
  newest_created_at: string | null;
}

/** Serialise filters for a query string, dropping empty values. */
export function reviewFilterParams(filters: ReviewFilters = {}): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  return params;
}

export function getReviewCourses(filters: ReviewFilters = {}): Promise<ReviewCourseGroup[]> {
  const qs = reviewFilterParams(filters).toString();
  return request<ReviewCourseGroup[]>(`/review/courses${qs ? `?${qs}` : ""}`);
}

export interface KeyConcept {
  name: string;
  definition: string;
  example: string;
}

/** Deep teaching content, generated lazily on first lesson open. */
export interface LessonContent {
  key_concepts: KeyConcept[];
  worked_example: string | null;
  common_pitfalls: string[];
  practice_prompts: string[];
}

export interface LessonEnrichResponse {
  status: "cached" | "generated";
  content: LessonContent | null;
}

// ── Diagrams ────────────────────────────────────────────────────────────────
// The model emits meaning, never geometry: it names a kind and fills semantic
// fields, and the renderers under components/diagram compute every coordinate.
// The backend validates each spec before storing it (app/diagram_spec.py), so
// by the time one arrives here its references already resolve.

export type DiagramTone = "brand" | "success" | "warn" | "danger" | "info" | "neutral";

/** One frame of a staged reveal. Ids name elements of the parent diagram. */
export interface DiagramStep {
  label: string;
  show: string[];
  highlight: string[];
}

interface DiagramBase {
  id: string;
  title: string;
  caption: string;
  steps: DiagramStep[];
}

export interface BoardPiece {
  at: string;
  glyph: string;
  tone: DiagramTone;
}

/** A square grid: chessboard, coordinate grid, matrix. Element ids are squares. */
export interface BoardDiagram extends DiagramBase {
  kind: "board";
  size: number;
  pieces: BoardPiece[];
  highlight: string[];
  labels: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  tone: DiagramTone;
}

export interface GraphEdge {
  from: string;
  to: string;
  label: string | null;
  directed: boolean;
}

/** Nodes and edges. One payload, four layouts — only the geometry differs. */
export interface GraphDiagram extends DiagramBase {
  kind: "graph";
  layout: "chain" | "tree" | "layered" | "circular";
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type PlotFunctionFamily =
  | "linear"
  | "quadratic"
  | "exponential"
  | "sigmoid"
  | "sine"
  | "normal";

/** A named family with numeric params — never an expression string to evaluate. */
export interface PlotFunction {
  family: PlotFunctionFamily;
  params: Record<string, number>;
}

export interface PlotSeries {
  id: string;
  label: string;
  tone: DiagramTone;
  type: "function" | "points" | "bars";
  fn: PlotFunction | null;
  points: [number, number][] | null;
}

export interface PlotMarker {
  id: string;
  at: [number, number];
  label: string;
}

export interface PlotDiagram extends DiagramBase {
  kind: "plot";
  x_label: string;
  y_label: string;
  x_range: [number, number];
  y_range: [number, number] | null;
  series: PlotSeries[];
  markers: PlotMarker[];
}

export interface GeometryAnnotation {
  at: string;
  text: string;
}

/** Positioned from side lengths, not coordinates. */
export interface GeometryDiagram extends DiagramBase {
  kind: "geometry";
  shape: "triangle" | "rectangle" | "polygon" | "circle";
  vertices: string[];
  sides: number[];
  radius: number | null;
  show_sides: boolean;
  show_angles: boolean;
  annotations: GeometryAnnotation[];
}

export type DiagramSpec = BoardDiagram | GraphDiagram | PlotDiagram | GeometryDiagram;

export interface LessonDiagramResponse {
  status: "cached" | "generated";
  diagrams: DiagramSpec[];
}

export interface LessonDetailResponse {
  id: string;
  order_index: number;
  title: string;
  description: string;
  duration_minutes: number;
  completed_at: string | null;
  objectives: ObjectiveResponse[];
  questions: QuestionResponse[];
  /** Null until the lesson has been enriched. */
  content: LessonContent | null;
  /**
   * Null until generation has been attempted. An empty array is a real answer:
   * the model was asked and said no diagram helps this lesson.
   */
  diagrams: DiagramSpec[] | null;
}

export function enrichLesson(lessonId: string): Promise<LessonEnrichResponse> {
  return request<LessonEnrichResponse>(`/lessons/${lessonId}/enrich`, { method: "POST" });
}

export function generateDiagrams(lessonId: string): Promise<LessonDiagramResponse> {
  return request<LessonDiagramResponse>(`/lessons/${lessonId}/diagram`, { method: "POST" });
}

/**
 * Clue generation reports status and nothing else.
 *
 * The clue is the listening drill's question, so it is only ever spoken — a
 * client that could read it would not have to listen, which is the whole point
 * of the drill. There is deliberately nothing here to fetch.
 */
export interface LessonClueResponse {
  status: "cached" | "generated";
}

export function generateClues(lessonId: string): Promise<LessonClueResponse> {
  return request<LessonClueResponse>(`/lessons/${lessonId}/clues`, { method: "POST" });
}

export function getCourses(): Promise<CourseSummaryResponse[]> {
  return request<CourseSummaryResponse[]>("/courses");
}

export function getReviewQueue(
  courseId?: string,
  filters: ReviewFilters = {},
): Promise<ReviewQueueResponse> {
  const params = reviewFilterParams(filters);
  if (courseId) params.set("course_id", courseId);
  const qs = params.toString();
  return request<ReviewQueueResponse>(`/review/queue${qs ? `?${qs}` : ""}`);
}

export function getLessonDetail(courseId: string, lessonId: string): Promise<LessonDetailResponse> {
  return request<LessonDetailResponse>(`/courses/${courseId}/lessons/${lessonId}`);
}

export function completeLesson(lessonId: string): Promise<null> {
  return request<null>(`/lessons/${lessonId}/complete`, { method: "POST" });
}

export function answerQuestion(questionId: string, answer: string): Promise<AnswerResponse> {
  return request<AnswerResponse>(`/questions/${questionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });
}

export function gradeCard(cardId: string, rating: number): Promise<GradeResponse> {
  return request<GradeResponse>("/review/grade", {
    method: "POST",
    body: JSON.stringify({ card_id: cardId, rating }),
  });
}

export interface WordDiffItem {
  op: "match" | "missing" | "extra" | "substituted";
  expected: string | null;
  actual: string | null;
}

export interface PronunciationCheckResponse {
  expected_text: string;
  transcribed_text: string;
  diff: WordDiffItem[];
  accuracy: number;
}

export interface SearchResultItem {
  content_type: 'lesson' | 'question'
  content_id: string
  content_text: string
  course_id: string
  lesson_id: string | null
  score: number
}

export function searchContent(
  query: string,
  courseId?: string,
  k = 5,
): Promise<SearchResultItem[]> {
  const params = new URLSearchParams({ q: query, k: String(k) })
  if (courseId) params.set('course_id', courseId)
  return request<SearchResultItem[]>(`/search?${params}`)
}

export interface AchievementResponse {
  id: string
  title: string
  description: string
  icon: string
  unlocked: boolean
  unlocked_at: string | null
}

export interface ConceptMastery {
  name: string
  mastery: number
}

export interface MasteryResponse {
  concepts: ConceptMastery[]
  overall: number
}

export function getAchievements(): Promise<AchievementResponse[]> {
  return request<AchievementResponse[]>('/achievements')
}

export function getMastery(courseId: string): Promise<MasteryResponse> {
  return request<MasteryResponse>(`/courses/${courseId}/mastery`)
}

export interface TimelineLesson {
  id: string
  title: string
  duration_minutes: number
  completed_at: string | null
  order_index: number
}

export interface TimelineModule {
  title: string
  lessons: TimelineLesson[]
}

export interface TimelineResponse {
  modules: TimelineModule[]
  total_minutes: number
  completed_minutes: number
  streak: number
}

export function getTimeline(courseId: string): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/courses/${courseId}/timeline`)
}

export interface OptimalStudyTime {
  start_hour: number
  end_hour: number
}

export interface RecommendedFocus {
  concept: string
  mastery: number
  rationale: string
}

export interface NextReview {
  question_text: string
  due: string
}

export interface InsightsResponse {
  optimal_study_time: OptimalStudyTime | null
  recommended_focus: RecommendedFocus | null
  next_reviews: NextReview[]
}

export function getInsights(courseId: string): Promise<InsightsResponse> {
  return request<InsightsResponse>(`/courses/${courseId}/insights`)
}

// ── Practice drills ────────────────────────────────────────────────────────

export type DrillKind = "mcq" | "match" | "order" | "listen" | "pronounce";

export interface DrillAvailability {
  kind: DrillKind;
  title: string;
  modality: string;
  description: string;
  available: boolean;
  item_count: number;
  reason: string | null;
}

export interface CourseDrills {
  course_id: string;
  course_title: string;
  enriched_lessons: number;
  total_lessons: number;
  target_language: string | null;
  drills: DrillAvailability[];
}

export interface McqItem {
  id: string;
  prompt: string;
  options: string[];
  answer_index: number;
  lesson_title: string;
  example: string | null;
}

export interface MatchItem {
  id: string;
  name: string;
  definition: string;
  lesson_title: string;
}

export interface OrderItem {
  id: string;
  lesson_title: string;
  /** Display order. */
  steps: string[];
  /** Display indices, in the sequence they belong. */
  correct_order: number[];
}

/** Same shape as MCQ, but the prompt is audio — the text is never sent. */
export interface ListenItem {
  id: string;
  audio_url: string;
  options: string[];
  answer_index: number;
  lesson_title: string;
}

export interface PronounceItem {
  id: string;
  phrase: string;
  concept: string;
  lesson_title: string;
}

export type DrillItem = McqItem | MatchItem | OrderItem | ListenItem | PronounceItem;

export interface DrillResponse<T = DrillItem> {
  kind: DrillKind;
  course_id: string;
  course_title: string;
  items: T[];
}

export function getCourseDrills(courseId: string): Promise<CourseDrills> {
  return request<CourseDrills>(`/courses/${courseId}/drills`);
}

export function getDrill<T = DrillItem>(
  courseId: string,
  kind: DrillKind,
  n = 8,
): Promise<DrillResponse<T>> {
  return request<DrillResponse<T>>(`/courses/${courseId}/drills/${kind}?n=${n}`);
}

export function completeDrill(
  courseId: string,
  kind: DrillKind,
  correct: number,
  total: number,
): Promise<null> {
  return request<null>(
    `/courses/${courseId}/drills/${kind}/complete?correct=${correct}&total=${total}`,
    { method: "POST" },
  );
}

export interface ForecastDay {
  date: string
  count: number
}

export function getReviewForecast(courseId?: string, days = 28): Promise<ForecastDay[]> {
  const params = new URLSearchParams({ days: String(days) })
  if (courseId) params.set("course_id", courseId)
  return request<ForecastDay[]>(`/review/forecast?${params}`)
}

export async function checkPronunciation(
  audio: Blob,
  expectedText: string,
  language = "es",
): Promise<PronunciationCheckResponse> {
  const ext = audio.type.includes("mp4") ? "mp4" : "webm";
  const form = new FormData();
  form.append("audio", audio, `recording.${ext}`);
  form.append("expected_text", expectedText);
  form.append("language", language);
  const res = await authFetch("/pronunciation-check", { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${res.status}`);
  }
  return res.json();
}


// ── Authentication ─────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  /** Null for accounts created before display names existed. */
  name: string | null;
}

export function register(
  email: string,
  password: string,
  name: string,
): Promise<AuthUser> {
  return request<AuthUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
}

export function login(email: string, password: string): Promise<AuthUser> {
  return request<AuthUser>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<null> {
  return request<null>("/auth/logout", { method: "POST" });
}

/** Resolves the current session. Throws UnauthorizedError when signed out. */
export function getMe(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}
