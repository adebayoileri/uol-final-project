const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface CourseRequest {
  goal: string;
  duration: "short_term" | "long_term";
  category: string;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (res.status === 204) {
    return null as T;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export function createCourse(body: CourseRequest): Promise<CourseResponse> {
  return request<CourseResponse>("/courses", {
    method: "POST",
    body: JSON.stringify(body),
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

export function getNextCard(courseId?: string): Promise<CardResponse | null> {
  const params = courseId ? `?course_id=${courseId}` : "";
  return request<CardResponse | null>(`/review/next${params}`);
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

export interface LessonDetailResponse {
  id: string;
  order_index: number;
  title: string;
  description: string;
  duration_minutes: number;
  completed_at: string | null;
  objectives: ObjectiveResponse[];
  questions: QuestionResponse[];
}

export function getCourses(): Promise<CourseSummaryResponse[]> {
  return request<CourseSummaryResponse[]>("/courses");
}

export function getReviewQueue(courseId?: string): Promise<ReviewQueueResponse> {
  const params = courseId ? `?course_id=${courseId}` : "";
  return request<ReviewQueueResponse>(`/review/queue${params}`);
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
  const res = await fetch(`${API_URL}/pronunciation-check`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${res.status}`);
  }
  return res.json();
}
