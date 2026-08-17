from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.routes.courses import router as courses_router
from app.routes.lessons import router as lessons_router
from app.routes.questions import router as questions_router
from app.routes.review import router as review_router
from app.routes.search import router as search_router
from app.routes.speech import router as speech_router
from app.routes.audio import router as audio_narration_router
from app.routes.audio_serve import router as audio_serve_router
from app.auth.routes import router as auth_router
from app.routes.achievements import router as achievements_router
from app.routes.drills import router as drills_router
from app.routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Course Agent",
    description="Local-first AI course creation system. Final-year project.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for the Vite dev server. Tighten before any deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ungated: registration, login and logout must be reachable without a session.
app.include_router(auth_router)

app.include_router(courses_router)
app.include_router(lessons_router)
app.include_router(questions_router)
app.include_router(review_router)
app.include_router(search_router)
app.include_router(speech_router)
app.include_router(audio_narration_router)
app.include_router(audio_serve_router)
app.include_router(chat_router)
app.include_router(achievements_router)
app.include_router(drills_router)

from app.routes.insights import router as insights_router
app.include_router(insights_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "course-agent", "version": "0.1.0"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
