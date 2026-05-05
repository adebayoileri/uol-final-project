# Course Agent

A local-first AI course creation system using multiple pre-trained models. Final-year project.

## Stack

- **Frontend**: React + Vite + TypeScript (pnpm)
- **Backend**: FastAPI + Python 3.11+ (uv)
- **Database**: SQLite (added in Phase 2)
- **Models** (all local, added in later phases):
  - Llama 3.1 8B via Ollama (text generation)
  - Whisper via mlx-whisper (speech-to-text)
  - sentence-transformers all-MiniLM-L6-v2 (embeddings)
  - Piper TTS (text-to-speech)


Required:

1. **Node 20+** — `brew install node@20` (or use nvm)
2. **pnpm** — `npm install -g pnpm`
3. **Python 3.11+** — `brew install python@3.11`
4. **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
5. **Ollama** — download from [ollama.com](https://ollama.com), then `ollama pull llama3.1:8b`
6. **ffmpeg** (Whisper dependency) — `brew install ffmpeg`

## Project setup

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev
```

Backend runs at http://localhost:8000, frontend at http://localhost:5173.

## Layout

```
course-agent/
├── frontend/          # React + Vite app
├── backend/           # FastAPI app
├── notebooks/         # Jupyter notebooks for model experiments (Week 3 bake-off)
└── docs/              # Project notes — see below
    ├── decisions.md       # Every model/design choice with rationale
    ├── report-notes.md    # Continuous notes feeding the final 7000-word report
    └── future-work.md     # Anything cut from scope
```
