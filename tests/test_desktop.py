import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import desktop_launcher as launcher
from backend.sara import paths


def test_source_resources_are_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert (paths.resource_root() / "frontend" / "index.html").is_file()
    monkeypatch.delenv("SARA_ENV_FILE")
    assert paths.config_path() == paths.resource_root() / ".env"


def test_frozen_resources_and_settings_use_separate_locations(monkeypatch, tmp_path):
    bundle = tmp_path / "read-only-bundle"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.delenv("SARA_ENV_FILE")
    assert paths.resource_root() == bundle
    assert paths.config_path() == paths.user_data_dir() / ".env"
    assert paths.config_path().parent != paths.resource_root()


def test_windows_profile_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.delenv("SARA_DATA_DIR")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local App Data"))
    assert paths.user_data_dir() == tmp_path / "Local App Data" / "SARA"


def test_desktop_config_never_uses_working_directory_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("GEMINI_API_KEY=wrong-key\n", encoding="utf-8")
    monkeypatch.setenv("SARA_DESKTOP", "1")
    monkeypatch.delenv("SARA_ENV_FILE")
    assert paths.config_path() == paths.user_data_dir() / ".env"


def test_settings_default_without_creating_files():
    assert launcher.read_settings() == launcher.DEFAULT_SETTINGS
    assert not paths.profile_env_path().exists()


def test_settings_round_trip_unicode_quotes_backslashes_and_dollars(tmp_path):
    file = tmp_path / "profile with spaces" / ".env"
    settings = {"GEMINI_API_KEY": "test-key", "SARA_OWNER_NAME": "O'Brien \\ Sara ${HOME} — 李\nA"}
    launcher.save_settings(settings, file)
    loaded = launcher.read_settings(file)
    assert all(loaded[key] == value for key, value in settings.items())
    assert loaded["GEMINI_MODEL"] == launcher.DEFAULT_SETTINGS["GEMINI_MODEL"]
    if os.name != "nt":
        assert file.stat().st_mode & 0o777 == 0o600


def test_saving_visible_fields_preserves_location():
    launcher.save_settings({"SARA_LATITUDE": "12.5", "SARA_LONGITUDE": "80.2"})
    launcher.save_settings({"GEMINI_API_KEY": "test-key", "UNRECOGNIZED_KEY": "ignored"})
    settings = launcher.read_settings()
    assert settings["SARA_LATITUDE"] == "12.5"
    assert settings["SARA_LONGITUDE"] == "80.2"
    assert "UNRECOGNIZED_KEY" not in paths.profile_env_path().read_text(encoding="utf-8")


def test_failed_atomic_write_preserves_old_settings(monkeypatch):
    file = launcher.save_settings({"GEMINI_API_KEY": "original-key"})
    monkeypatch.setattr(launcher.os, "replace", Mock(side_effect=OSError("disk failure")))
    with pytest.raises(OSError, match="disk failure"):
        launcher.save_settings({"GEMINI_API_KEY": "new-key"})
    assert launcher.read_settings()["GEMINI_API_KEY"] == "original-key"
    assert list(file.parent.glob(".sara-*.tmp")) == []


def test_source_and_frozen_server_commands(monkeypatch):
    source = launcher.server_command(43210)
    assert Path(source[1]).name == "desktop_launcher.py"
    assert source[-3:] == ["--serve", "--port", "43210"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launcher.server_command(43210) == [sys.executable, "--serve", "--port", "43210"]


def test_controller_passes_personal_settings_and_cleans_up(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    popen = Mock(return_value=process)
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher, "available_port", lambda: 43210)
    controller = launcher.ServerController()
    controller.start()
    assert controller.url == "http://127.0.0.1:43210"
    kwargs = popen.call_args.kwargs
    assert kwargs["env"]["SARA_ENV_FILE"] == str(paths.profile_env_path())
    assert kwargs["env"]["SARA_DESKTOP"] == "1"
    assert kwargs["env"]["SARA_DESKTOP_INSTANCE"] == controller.instance
    assert kwargs["cwd"] == paths.user_data_dir()
    log = kwargs["stdout"]
    controller.stop()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)
    assert log.closed
    assert controller.process is None


def test_controller_kills_unresponsive_process(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("SARA", 5), None]
    controller = launcher.ServerController()
    controller.process = process
    controller.stop()
    process.kill.assert_called_once()
    assert controller.process is None


def test_controller_closes_log_after_launch_failure(monkeypatch):
    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(side_effect=OSError("cannot launch")))
    controller = launcher.ServerController()
    with pytest.raises(OSError, match="cannot launch"):
        controller.start()
    assert controller._log is None
    assert controller.process is None
