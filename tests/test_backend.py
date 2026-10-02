import json

import pytest
from fastapi.testclient import TestClient

from backend.sara import __version__
from backend.sara.config import Config
from desktop_launcher import save_settings


@pytest.fixture
def client(monkeypatch):
    import backend.main as backend

    monkeypatch.setattr(backend.config, "gemini_api_key", "")
    monkeypatch.setattr(backend.config, "elevenlabs_api_key", "")
    monkeypatch.setattr(backend.llm, "client", None)
    monkeypatch.setattr(backend.llm, "_missing_key", True)
    monkeypatch.setattr(backend.tts_service, "client", None)
    monkeypatch.setattr(backend.tts_service, "_missing_key", True)
    with TestClient(backend.app, base_url="http://127.0.0.1:43210") as client:
        yield client


def test_health_and_public_configuration_hide_keys(client, monkeypatch):
    import backend.main as backend

    monkeypatch.setattr(backend.config, "gemini_api_key", "private-test-gemini-key")
    monkeypatch.setattr(backend.config, "elevenlabs_api_key", "private-test-elevenlabs-key")
    for route in ("/api/health", "/api/config"):
        response = client.get(route)
        assert response.status_code == 200
        assert response.json()["gemini_configured"] is True
        assert response.json()["elevenlabs_configured"] is True
        assert "private-test" not in response.text
    assert client.get("/api/health").json()["version"] == __version__


def test_frontend_and_assets(client):
    assert "S.A.R.A" in client.get("/").text
    assert client.get("/css/style.css").headers["content-type"].startswith("text/css")
    assert client.get("/js/app.js").status_code == 200
    assert client.get("/does-not-exist").status_code == 404


@pytest.mark.parametrize("path", ["/.env", "/README.md", "/backend/main.py",
                                  "/%2e%2e/README.md", "/%2e%2e/.env"])
def test_non_frontend_files_are_not_public(client, path):
    assert client.get(path).status_code == 404


def test_missing_keys_are_handled_without_network_calls(client):
    assert client.get("/api/health").json()["gemini_configured"] is False
    wake = client.get("/api/wake")
    assert wake.status_code == 200
    assert wake.json()["text"]
    chat = client.post("/api/chat", json={"message": "Hello"})
    assert chat.status_code == 200
    assert "event: text" in chat.text
    assert "event: end" in chat.text
    assert "API key not configured" in chat.text
    stt = client.post("/api/stt", json={"audio_data_url": "data:audio/webm;base64,AA=="})
    assert stt.status_code == 400


def test_desktop_allows_its_own_origin(client, monkeypatch):
    monkeypatch.setenv("SARA_DESKTOP", "1")
    monkeypatch.setenv("SARA_LOCAL_ORIGIN", "http://127.0.0.1:43210")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/config", headers={"Origin": "http://127.0.0.1:43210"}).status_code == 200


@pytest.mark.parametrize("headers", [
    {"Origin": "https://untrusted.example"},
    {"Origin": "null"},
    {"Origin": "http://127.0.0.1:9999"},
    {"Host": "untrusted.example:43210"},
    {"Sec-Fetch-Site": "cross-site"},
])
def test_desktop_blocks_foreign_websites_and_hosts(client, monkeypatch, headers):
    monkeypatch.setenv("SARA_DESKTOP", "1")
    monkeypatch.setenv("SARA_LOCAL_ORIGIN", "http://127.0.0.1:43210")
    assert client.get("/api/health", headers=headers).status_code == 403
    assert client.post("/api/chat", headers=headers, json={"message": "Hello"}).status_code == 403


def test_source_mode_still_supports_hosted_preview(client):
    assert client.get("/api/health", headers={"Host": "8000-preview.e2b.app"}).status_code == 200


def test_installed_profile_overrides_inherited_environment(monkeypatch):
    monkeypatch.setenv("SARA_DESKTOP", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "stale-inherited-key")
    save_settings({"GEMINI_API_KEY": "profile-key", "GEMINI_MODEL": "custom-gemini-model",
                   "SARA_OWNER_NAME": "Alex"})
    config = Config.load()
    assert config.gemini_api_key == "profile-key"
    assert config.gemini_model == "custom-gemini-model"
    assert config.owner_name == "Alex"


def test_source_environment_takes_precedence(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "deployment-key")
    save_settings({"GEMINI_API_KEY": "file-key"})
    assert Config.load().gemini_api_key == "deployment-key"


def test_model_selection_is_used_by_llm(monkeypatch):
    from backend.sara import llm as module

    monkeypatch.setattr(module.config, "gemini_api_key", "offline-test-key")
    monkeypatch.setattr(module.config, "gemini_model", "custom-gemini-model")
    monkeypatch.setattr(module.genai, "Client", lambda **kwargs: object())
    instance = module.SaraLLM()
    assert instance.model == "custom-gemini-model"
