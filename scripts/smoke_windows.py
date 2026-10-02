"""Offline end-to-end checks for the frozen app and the actual Windows installer.

CI runs this twice: against PyInstaller output, then after a real silent install.
No personal settings, API keys or external services are used.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, ProxyHandler, build_opener


_LOCAL_HTTP = build_opener(ProxyHandler({}))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def read_url(url: str, **kwargs) -> tuple[int, str]:
    with _LOCAL_HTTP.open(Request(url, **kwargs), timeout=5) as response:
        return response.status, response.read().decode("utf-8")


def expect_forbidden(url: str, headers: dict[str, str]) -> None:
    try:
        read_url(url, headers=headers)
    except HTTPError as exc:
        assert exc.code == 403, f"Expected 403, got {exc.code}"
    else:
        raise AssertionError("A foreign website could reach the desktop API")


def exercise(executable: Path, workdir: Path, env: dict[str, str]) -> None:
    report = workdir / "installation-report.json"
    result = subprocess.run([str(executable), "--check-install", str(report)], env=env,
                            cwd=workdir, timeout=60)
    if not report.is_file():
        profile_log = Path(env["SARA_DATA_DIR"]) / "launcher.log"
        if profile_log.is_file():
            print(profile_log.read_text(encoding="utf-8", errors="replace"), flush=True)
        raise AssertionError(f"Installation diagnostic produced no report (exit {result.returncode})")
    diagnostic = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 0 and diagnostic["ok"], diagnostic
    print("Bundled GUI, SDKs and static assets: OK", flush=True)

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    instance = uuid.uuid4().hex
    env = dict(env, SARA_DESKTOP_INSTANCE=instance)
    log = workdir / "server-output.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen([str(executable), "--serve", "--port", str(port)],
                                   env=env, cwd=workdir, stdout=stream, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise AssertionError(f"Packaged server exited: {process.returncode}")
                try:
                    _, body = read_url(base + "/api/health")
                    health = json.loads(body)
                    if health.get("desktop_instance") == instance:
                        break
                except (OSError, URLError, ValueError):
                    pass
                if time.monotonic() > deadline:
                    raise AssertionError("Packaged server failed to become ready")
                time.sleep(0.2)
            assert health["ok"] and health["name"] == "S.A.R.A"
            assert not health["gemini_configured"] and not health["elevenlabs_configured"]
            assert "S.A.R.A" in read_url(base + "/")[1]
            assert read_url(base + "/css/style.css")[0] == 200
            assert read_url(base + "/js/app.js")[0] == 200
            assert read_url(base + "/api/config")[0] == 200
            assert json.loads(read_url(base + "/api/wake")[1])["text"]
            _, chat = read_url(base + "/api/chat", method="POST",
                               headers={"Content-Type": "application/json"},
                               data=json.dumps({"message": "Hello"}).encode())
            assert "event: text" in chat and "event: end" in chat
            expect_forbidden(base + "/api/health", {"Origin": "https://untrusted.example"})
            expect_forbidden(base + "/api/health", {"Host": "untrusted.example"})
            print("Frozen local server, frontend, offline chat and origin guard: OK", flush=True)
        except Exception:
            print(log.read_text(encoding="utf-8", errors="replace"), flush=True)
            profile_log = Path(env["SARA_DATA_DIR"]) / "sara.log"
            if profile_log.exists():
                print(profile_log.read_text(encoding="utf-8", errors="replace"), flush=True)
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--executable", type=Path)
    target.add_argument("--installer", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sara-windows-smoke-") as directory:
        work = Path(directory)
        profile = work / "personal profile"
        profile.mkdir()
        settings = profile / ".env"
        # Explicit blank keys ensure no inherited credentials can trigger API calls.
        settings.write_text("GEMINI_API_KEY=''\nELEVENLABS_API_KEY=''\n"
                            "SARA_OWNER_NAME='Smoke Test'\n", encoding="utf-8")
        original_settings = settings.read_bytes()
        env = os.environ.copy()
        env.update(SARA_DATA_DIR=str(profile), SARA_ENV_FILE=str(settings), SARA_DESKTOP="1")
        for key in ("GEMINI_API_KEY", "ELEVENLABS_API_KEY"):
            env.pop(key, None)
        if args.executable:
            exercise(args.executable.resolve(), work, env)
        else:
            installed = work / "Installed SARA With Spaces"
            installer_log = work / "installer.log"
            result = subprocess.run([str(args.installer.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                                     "/NORESTART", "/SP-", f"/DIR={installed}", f"/LOG={installer_log}"],
                                    env=env, timeout=180)
            if result.returncode != 0:
                if installer_log.is_file():
                    print(installer_log.read_text(encoding="utf-8-sig", errors="replace"), flush=True)
                raise AssertionError(f"Silent install failed with exit code {result.returncode}")
            try:
                assert (installed / "unins000.exe").is_file()
                assert not (installed / ".env").exists(), "The installer bundled credentials"
                assert not (installed / "_internal" / ".env").exists()
                exercise(installed / "SARA.exe", work, env)
            finally:
                subprocess.run([str(installed / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                                "/NORESTART"], env=env, check=True, timeout=180)
            assert not (installed / "SARA.exe").exists()
            assert settings.read_bytes() == original_settings, "Uninstall removed personal settings"
            print("Per-user silent install and uninstall (settings preserved): OK", flush=True)


if __name__ == "__main__":
    # Windows pipes otherwise default to cp1252, which cannot print diagnostic
    # BOMs, Unicode paths or provider messages reliably.
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
