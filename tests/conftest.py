"""Offline tests: never read developer keys or contact the AI providers."""
import pytest


@pytest.fixture(autouse=True)
def isolated_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path / "profile"))
    monkeypatch.setenv("SARA_ENV_FILE", str(tmp_path / "profile" / ".env"))
    for key in ("GEMINI_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID",
                "GEMINI_MODEL", "SARA_OWNER_NAME", "SARA_LATITUDE", "SARA_LONGITUDE"):
        monkeypatch.setenv(key, "")
    for key in ("SARA_DESKTOP", "SARA_LOCAL_ORIGIN", "SARA_DESKTOP_INSTANCE"):
        monkeypatch.delenv(key, raising=False)
