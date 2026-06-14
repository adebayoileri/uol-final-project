from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.routes.courses import router as courses_router


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

app.include_router(courses_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "course-agent", "version": "0.1.0"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
