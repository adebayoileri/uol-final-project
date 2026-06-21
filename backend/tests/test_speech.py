"""Tests for /transcribe, /pronunciation-check, and /tts.

The whisper-cli and piper subprocess calls are mocked — no real binaries or
models are required to run these tests. See docs/decisions.md and the manual
verification commands for real-binary integration testing.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.word_diff import compute_word_diff

client = TestClient(app)


def _fake_whisper_run(transcript_text: str):
    def _run(cmd, **kwargs):
        of_index = cmd.index("-of")
        Path(f"{cmd[of_index + 1]}.txt").write_text(transcript_text, encoding="utf-8")
        return None

    return _run


@pytest.fixture()
def fake_model_path(tmp_path):
    model_file = tmp_path / "ggml-base.en.bin"
    model_file.write_text("fake model bytes")
    with patch("app.services.transcriber.WHISPER_MODEL_PATH", str(model_file)):
        yield model_file


def _fake_piper_run(wav_bytes: bytes = b"RIFF....WAVEfake"):
    def _run(cmd, **kwargs):
        f_index = cmd.index("-f")
        Path(cmd[f_index + 1]).write_bytes(wav_bytes)
        return None

    return _run


@pytest.fixture()
def fake_voices_dir(tmp_path):
    (tmp_path / "en_US-lessac-medium.onnx").write_text("fake voice bytes")
    (tmp_path / "es_ES-davefx-medium.onnx").write_text("fake voice bytes")
    with patch("app.services.tts.PIPER_VOICES_DIR", str(tmp_path)):
        yield tmp_path


# ---------------------------------------------------------------------------
# POST /transcribe
# ---------------------------------------------------------------------------

def test_transcribe_returns_200_and_text(fake_model_path):
    with patch(
        "app.services.transcriber.subprocess.run",
        side_effect=_fake_whisper_run("hello world"),
    ):
        resp = client.post("/transcribe", files={"audio": ("test.wav", b"fake-audio", "audio/wav")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "hello world"
    assert isinstance(data["duration_seconds"], float)


def test_transcribe_failure_returns_503(fake_model_path):
    with patch(
        "app.services.transcriber.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["whisper-cli"], stderr=b"boom"),
    ):
        resp = client.post("/transcribe", files={"audio": ("test.wav", b"fake-audio", "audio/wav")})
    assert resp.status_code == 503


def test_transcribe_missing_model_returns_503():
    with patch("app.services.transcriber.WHISPER_MODEL_PATH", "/nonexistent/model.bin"):
        resp = client.post("/transcribe", files={"audio": ("test.wav", b"fake-audio", "audio/wav")})
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /pronunciation-check
# ---------------------------------------------------------------------------

def test_pronunciation_check_returns_diff(fake_model_path):
    with patch(
        "app.services.transcriber.subprocess.run",
        side_effect=_fake_whisper_run("hello world"),
    ):
        resp = client.post(
            "/pronunciation-check",
            files={"audio": ("test.wav", b"fake-audio", "audio/wav")},
            data={"expected_text": "hello world"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["expected_text"] == "hello world"
    assert data["transcribed_text"] == "hello world"
    assert data["accuracy"] == 1.0
    assert all(item["op"] == "match" for item in data["diff"])


def test_pronunciation_check_failure_returns_503(fake_model_path):
    with patch(
        "app.services.transcriber.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["whisper-cli"], stderr=b"boom"),
    ):
        resp = client.post(
            "/pronunciation-check",
            files={"audio": ("test.wav", b"fake-audio", "audio/wav")},
            data={"expected_text": "hello world"},
        )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /tts
# ---------------------------------------------------------------------------

def test_tts_returns_200_audio_wav(fake_voices_dir):
    with patch("app.services.tts.subprocess.run", side_effect=_fake_piper_run()):
        resp = client.post("/tts", json={"text": "hello world", "lang": "en"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert len(resp.content) > 0


def test_tts_invalid_lang_returns_422():
    resp = client.post("/tts", json={"text": "hello world", "lang": "fr"})
    assert resp.status_code == 422


def test_tts_failure_returns_503(fake_voices_dir):
    with patch(
        "app.services.tts.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["piper"], stderr=b"boom"),
    ):
        resp = client.post("/tts", json={"text": "hello world", "lang": "en"})
    assert resp.status_code == 503


def test_tts_missing_voice_returns_503(tmp_path):
    with patch("app.services.tts.PIPER_VOICES_DIR", str(tmp_path)):
        resp = client.post("/tts", json={"text": "hello world", "lang": "en"})
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# compute_word_diff (pure unit tests, no mocking)
# ---------------------------------------------------------------------------

def test_word_diff_all_match():
    diff = compute_word_diff("hello world", "hello world")
    assert all(d["op"] == "match" for d in diff)
    assert len(diff) == 2


def test_word_diff_ignores_punctuation():
    diff = compute_word_diff("hello world", "hello, world.")
    assert all(d["op"] == "match" for d in diff)


def test_word_diff_with_substitution():
    diff = compute_word_diff("ask what you", "ask not you")
    ops = [d["op"] for d in diff]
    assert ops == ["match", "substituted", "match"]


def test_word_diff_with_missing_word():
    diff = compute_word_diff("ask what you can do", "ask what can do")
    ops = [d["op"] for d in diff]
    assert "missing" in ops


def test_word_diff_with_extra_word():
    diff = compute_word_diff("ask what", "ask what now")
    ops = [d["op"] for d in diff]
    assert "extra" in ops
