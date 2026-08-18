# Course Agent

A local-first AI course creation system using multiple pre-trained models. Final-year project.

## Stack

- **Frontend**: React + Vite + TypeScript (Yarn)
- **Backend**: FastAPI + Python 3.11+ (uv)
- **Database**: SQLite (added in Phase 2)
- **Models** (all local, added in later phases):
  - Llama 3.1 8B via Ollama (text generation)
  - Whisper via whisper.cpp's `whisper-cli` (speech-to-text)
  - sentence-transformers all-MiniLM-L6-v2 (embeddings)
  - Piper TTS via the `piper-tts` pip package (text-to-speech)


Required:

1. **Node 20+** — `brew install node@20` (or use nvm)
2. **Yarn 3** — `corepack enable` (the version is pinned in `frontend/package.json`)
3. **Python 3.11+** — `brew install python@3.11`
4. **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
5. **Ollama** — download from [ollama.com](https://ollama.com), then `ollama pull llama3.1:8b`
6. **whisper-cli** — `brew install whisper-cpp`
7. **ffmpeg** — `brew install ffmpeg` (used to prep audio test fixtures)

## Project setup

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
yarn install
yarn dev
```

Backend runs at http://localhost:8000, frontend at http://localhost:5173.

## Authentication

The app requires an account. Create the first one either by registering through
the UI at `/register`, or by seeding it:

```bash
cd backend
SEED_USER_PASSWORD='choose-a-password' uv run python -m scripts.seed_user
```

This creates `bayo@superlearned.com` and adopts any pre-authentication data
(courses, events, study sessions) into that account. It is safe to re-run — it
only adopts rows that have no owner.

Re-running does **not** change an existing account's password, so that adopting
data can never alter credentials as a side effect. To set a new password:

```bash
SEED_USER_PASSWORD='new-password' uv run python -m scripts.seed_user --reset-password
```

The password is passed inline rather than read from `backend/.env`, because
nothing in this project loads dotenv. The script exits non-zero if the variable
is unset or under 8 characters, so there is never a default credential in the
repository.

Sessions are server-side with an `HttpOnly` cookie. The cookie is not `Secure`,
which is required for it to work over `http://localhost`; a cross-host
deployment would need `samesite="none"` and `secure=True` together.

## Environment variables

Copy `backend/.env.example` to `backend/.env` and adjust as needed. All have working defaults if unset:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WHISPER_MODEL_PATH` | `backend/models/ggml-base.en.bin` | Path to the whisper.cpp GGML model used by `/transcribe` and `/pronunciation-check`. |
| `PIPER_VOICE_EN` | `en_US-lessac-medium` | Piper voice name used for `/tts` when `lang="en"`. |
| `PIPER_VOICE_ES` | `es_ES-davefx-medium` | Piper voice name used for `/tts` when `lang="es"`. |

One-time setup to download the model and voices referenced above:

```bash
cd backend

# Whisper model
mkdir -p models
curl -L -o models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

# Piper voices
.venv/bin/python -m piper.download_voices en_US-lessac-medium --data-dir voices
.venv/bin/python -m piper.download_voices es_ES-davefx-medium --data-dir voices
```

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
