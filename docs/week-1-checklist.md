# Week 1 Checklist (May 4–10)

The plan's Week 1 deliverables: repo initialised, models running, baseline measurements, decisions.md and report-notes.md alive.

The repo scaffold is done. The rest is work you do on your Mac. Tick items as you go.

## 1. Toolchain install (~30 min)

- [ ] Node 20+ installed: `node --version` should print v20+ or v22+
- [ ] pnpm installed: `pnpm --version`
- [ ] Python 3.11+ installed: `python3 --version` should be 3.11+
- [ ] uv installed: `uv --version`
- [ ] ffmpeg installed: `ffmpeg -version` (Whisper needs this)
- [ ] git configured: `git config user.name` and `git config user.email` are set

## 2. Project bootstrap (~15 min)

- [ ] `cd backend && uv sync` runs cleanly
- [ ] `cd backend && uv run uvicorn app.main:app --reload --port 8000` — visit http://localhost:8000 and see the hello-world JSON response
- [ ] `cd frontend && pnpm install` runs cleanly
- [ ] `cd frontend && pnpm dev` — visit http://localhost:5173 and see the Vite app
- [ ] `git init && git add . && git commit -m "Week 1: scaffold"` succeeds
- [ ] Push to a private GitHub repo (`gh repo create course-agent --private --source=. --push` if you have the gh CLI)

## 3. Ollama install and LLM baseline (~30 min, mostly download time)

- [ ] Ollama installed (download from ollama.com)
- [ ] `ollama --version` works
- [ ] `ollama pull llama3.1:8b` completes (~4.7GB download)
- [ ] `ollama pull mistral:7b` completes (~4.1GB download) — second candidate for the bake-off
- [ ] Smoke test: `ollama run llama3.1:8b "Write a 3-bullet study plan to learn Spanish in 4 weeks."` returns a sensible answer
- [ ] Note in `decisions.md`: subjective speed (fast / acceptable / slow), any RAM pressure observed in Activity Monitor

## 4. Whisper baseline (~20 min)

- [ ] `uv pip install mlx-whisper` (or whisper.cpp build, your call) runs cleanly in the backend env
- [ ] Record a 30-second voice memo of yourself describing a learning goal (e.g., "I want to learn Spanish to travel in Mexico for 3 months"). Save as `notebooks/sample_goal.wav`.
- [ ] Transcribe it with `mlx-whisper notebooks/sample_goal.wav --model mlx-community/whisper-base` (or equivalent)
- [ ] Note in `decisions.md`: time to transcribe, accuracy (any errors?), model size used

## 5. Risk-retirement gate (this is the actual Week 1 goal)

Answer these in `decisions.md` before closing Week 1:

- [ ] Does Llama 3.1 8B run at usable speed on your hardware? (Define "usable" as: a 200-token response in under 15 seconds.) **If no, document the fallback decision to Llama 3.2 3B or Phi-3 mini.**
- [ ] Does Whisper transcribe a 30-second clip in under 10 seconds? **If no, document the fallback to a smaller variant.**
- [ ] Is there enough RAM headroom to run Ollama + Whisper + a browser at the same time? Check Activity Monitor while all three are running.

## 6. Continuous habits (start now)

- [ ] Added at least one entry to `docs/report-notes.md` this week
- [ ] Added at least one entry to `docs/decisions.md` this week (the spike measurements count)
- [ ] 15-minute end-of-week review written in a `weekly-log.md` file (create it now): What shipped? What's blocked? What's next week?

## Done when

All boxes ticked. Ollama and Whisper running. `decisions.md` has real numbers from your hardware. You're ready for Week 2 (literature review and model survey).
