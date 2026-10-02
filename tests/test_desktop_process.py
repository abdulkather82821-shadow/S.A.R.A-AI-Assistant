"""Exercise the real subprocess lifecycle without a display or cloud keys."""
import json
import time
from urllib.request import urlopen

from desktop_launcher import ServerController, save_settings


def wait_until_ready(controller):
    deadline = time.monotonic() + 20
    while not controller.ready():
        assert controller.running, controller.log_path.read_text(encoding="utf-8", errors="replace")
        assert time.monotonic() < deadline, "Desktop backend did not become ready"
        time.sleep(0.1)


def test_real_server_starts_stops_and_reloads_profile():
    controller = ServerController()
    try:
        save_settings({"SARA_OWNER_NAME": "First Owner", "GEMINI_MODEL": "first-model"})
        controller.start()
        wait_until_ready(controller)
        with urlopen(controller.url + "/api/health", timeout=2) as response:
            first = json.load(response)
        assert first["owner"] == "First Owner"
        assert first["gemini_model"] == "first-model"
        assert first["gemini_configured"] is False
        first_process = controller.process
        first_instance = controller.instance
        controller.stop()
        assert first_process.poll() is not None

        save_settings({"SARA_OWNER_NAME": "Second Owner", "GEMINI_MODEL": "second-model"})
        controller.start()
        wait_until_ready(controller)
        with urlopen(controller.url + "/api/health", timeout=2) as response:
            second = json.load(response)
        assert second["owner"] == "Second Owner"
        assert second["gemini_model"] == "second-model"
        assert controller.instance != first_instance
    finally:
        controller.stop()
    assert not controller.running
