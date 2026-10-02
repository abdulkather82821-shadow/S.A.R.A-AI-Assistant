"""Windows desktop launcher; the UI controls a separate, loopback-only backend.

Run from source with ``python desktop_launcher.py`` or build with
``scripts/build-windows.ps1``. The packaged app does not require Python.
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
import traceback
import uuid
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from dotenv import dotenv_values

from backend.sara import __version__
from backend.sara.defaults import DEFAULT_GEMINI_MODEL, DEFAULT_VOICE_ID
from backend.sara.paths import profile_env_path, resource_root, user_data_dir

# Never route local health probes through a system/corporate HTTP proxy.
_LOCAL_HTTP = build_opener(ProxyHandler({}))

DEFAULT_SETTINGS = {
    "GEMINI_API_KEY": "",
    "ELEVENLABS_API_KEY": "",
    "ELEVENLABS_VOICE_ID": DEFAULT_VOICE_ID,
    "GEMINI_MODEL": DEFAULT_GEMINI_MODEL,
    "SARA_OWNER_NAME": "Sir",
    "SARA_LATITUDE": "",
    "SARA_LONGITUDE": "",
}


def read_settings(path: Path | None = None) -> dict[str, str]:
    path = path or profile_env_path()
    values = dotenv_values(path, interpolate=False) if path.is_file() else {}
    return {key: values.get(key) if values.get(key) is not None else default
            for key, default in DEFAULT_SETTINGS.items()}


def save_settings(values: dict[str, str], path: Path | None = None) -> Path:
    """Write atomically, preserve location settings, and never write to the bundle."""
    path = path or profile_env_path()
    settings = read_settings(path)
    settings.update({key: str(value) for key, value in values.items()
                     if key in DEFAULT_SETTINGS})
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".sara-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write("# S.A.R.A personal settings. Contains API keys; do not share.\n")
            for key, value in settings.items():
                escaped = value.replace("\\", "\\\\").replace("'", "\\'")
                stream.write(f"{key}='{escaped}'\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def server_command(port: int) -> list[str]:
    entry = [sys.executable]
    if not getattr(sys, "frozen", False):
        entry.append(str(Path(__file__).resolve()))
    return entry + ["--serve", "--port", str(port)]


class ServerController:
    """Keep server state and OS process management separate from Tkinter."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.port = 0
        self.instance = ""
        self.log_path = user_data_dir() / "sara.log"
        self._log = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if self.running:
            return
        self.stop()
        self.port = available_port()
        self.instance = uuid.uuid4().hex
        self.log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.log_path.exists() and self.log_path.stat().st_size > 2 * 1024 * 1024:
            self.log_path.replace(self.log_path.with_suffix(".log.old"))
        self._log = self.log_path.open("a", encoding="utf-8", buffering=1)
        env = os.environ.copy()
        env.update({
            "SARA_DESKTOP": "1",
            "SARA_ENV_FILE": str(profile_env_path()),
            "SARA_DATA_DIR": str(user_data_dir()),
            "SARA_DESKTOP_INSTANCE": self.instance,
            "PYINSTALLER_RESET_ENVIRONMENT": "1",
        })
        try:
            self.process = subprocess.Popen(
                server_command(self.port), env=env, cwd=user_data_dir(),
                stdin=subprocess.DEVNULL, stdout=self._log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception:
            self._log.close()
            self._log = None
            raise

    def ready(self) -> bool:
        if not self.running:
            return False
        try:
            with _LOCAL_HTTP.open(self.url + "/api/health", timeout=0.4) as response:
                health = json.load(response)
            return (health.get("ok") is True and health.get("name") == "S.A.R.A"
                    and health.get("desktop_instance") == self.instance)
        except (OSError, URLError, ValueError):
            return False

    def stop(self) -> None:
        try:
            if self.running:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            self.process = None
            if self._log is not None:
                self._log.close()
                self._log = None


class DesktopApp:
    def __init__(self, root) -> None:
        # Import lazily: headless servers and tests do not need Tk installed.
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.root, self.messagebox = root, messagebox
        self.controller = ServerController()
        self._startup_check = None
        self._deadline = 0.0
        root.title(f"S.A.R.A Desktop · {__version__}")
        root.configure(background="#07141e")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        if sys.platform == "win32":
            root.iconbitmap(str(resource_root() / "packaging" / "assets" / "sara.ico"))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#07141e")
        style.configure("TLabel", background="#07141e", foreground="#d9edf7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", foreground="#00d4ff", font=("Segoe UI", 26, "bold"))
        style.configure("Muted.TLabel", foreground="#92afc0", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("TCheckbutton", background="#07141e", foreground="#d9edf7")

        frame = ttk.Frame(root, padding=24)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="S.A.R.A", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="SMART ASSISTANT FOR RESPONSIVE ACTIONS", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 18))
        ttk.Label(frame, text="Add your API keys, then start your local assistant.").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))

        settings = read_settings()
        self.variables = {}
        self.entries = []
        self.key_entries = []
        fields = [
            ("GEMINI_API_KEY", "Gemini API key *", True),
            ("ELEVENLABS_API_KEY", "ElevenLabs API key (optional)", True),
            ("SARA_OWNER_NAME", "Your name / title", False),
            ("ELEVENLABS_VOICE_ID", "ElevenLabs voice ID", False),
            ("GEMINI_MODEL", "Gemini model", False),
        ]
        for row, (key, label, secret) in enumerate(fields, start=3):
            value = settings[key]
            if secret and value.startswith("your_"):
                value = ""
            variable = tk.StringVar(value=value)
            self.variables[key] = variable
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=7)
            entry = ttk.Entry(frame, textvariable=variable, width=40, show="*" if secret else "")
            entry.grid(row=row, column=1, sticky="ew", pady=7)
            self.entries.append(entry)
            if secret:
                self.key_entries.append(entry)

        show_keys = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Show API keys", variable=show_keys,
                        command=lambda: [entry.configure(show="" if show_keys.get() else "*")
                                         for entry in self.key_entries]).grid(row=8, column=1, sticky="w")
        links = ttk.Frame(frame)
        links.grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 12))
        ttk.Button(links, text="Get a Gemini key", command=lambda: webbrowser.open(
            "https://aistudio.google.com/app/apikey")).pack(side="left", padx=(0, 8))
        ttk.Button(links, text="Get an ElevenLabs key", command=lambda: webbrowser.open(
            "https://elevenlabs.io/app/settings/api-keys")).pack(side="left")
        ttk.Label(frame, text="Internet is required for Gemini / ElevenLabs. Without ElevenLabs, replies are text-only.\n"
                              "Use Chrome or Edge for microphone support. No Python installation is needed.",
                  style="Muted.TLabel", wraplength=570).grid(row=10, column=0, columnspan=2, sticky="w")

        actions = ttk.Frame(frame)
        actions.grid(row=11, column=0, columnspan=2, sticky="w", pady=(20, 14))
        self.start_button = ttk.Button(actions, text="Start S.A.R.A", command=self.start)
        self.open_button = ttk.Button(actions, text="Open assistant", command=self.open_browser, state="disabled")
        self.stop_button = ttk.Button(actions, text="Stop", command=self.stop, state="disabled")
        self.save_button = ttk.Button(actions, text="Save settings", command=self.save)
        for button in (self.start_button, self.open_button, self.stop_button, self.save_button):
            button.pack(side="left", padx=(0, 8))

        self.status = tk.StringVar(value="Ready to set up. Your server is stopped.")
        ttk.Label(frame, textvariable=self.status, wraplength=570).grid(row=12, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="Keep this window open while using S.A.R.A. Closing it stops the server.\n"
                              f"Settings: {profile_env_path()}\n"
                              "Keys are saved in a local .env file, not encrypted. Do not share it.",
                  style="Muted.TLabel", wraplength=570).grid(row=13, column=0, columnspan=2, sticky="w", pady=(12, 8))
        ttk.Button(frame, text="Open settings / logs folder", command=self.open_folder).grid(
            row=14, column=0, columnspan=2, sticky="w")
        self.entries[0].focus_set()
        if self.variables["GEMINI_API_KEY"].get().strip():
            root.after(300, self.start)
        root.after(1500, self.monitor)

    def save(self) -> bool:
        values = {key: variable.get().strip() for key, variable in self.variables.items()}
        if any("\n" in value or "\r" in value for value in values.values()):
            self.messagebox.showerror("Invalid settings", "Settings must be single-line values.", parent=self.root)
            return False
        for key in ("SARA_OWNER_NAME", "ELEVENLABS_VOICE_ID", "GEMINI_MODEL"):
            values[key] = values[key] or DEFAULT_SETTINGS[key]
            self.variables[key].set(values[key])
        try:
            save_settings(values)
        except OSError as exc:
            self.messagebox.showerror("Couldn't save settings", str(exc), parent=self.root)
            return False
        self.status.set("Settings saved. Start S.A.R.A to use them.")
        return True

    def busy(self, value: bool) -> None:
        state = "disabled" if value else "normal"
        for widget in (*self.entries, self.start_button, self.save_button):
            widget.configure(state=state)
        self.stop_button.configure(state="normal" if value else "disabled")
        self.open_button.configure(state="disabled")

    def start(self) -> None:
        key = self.variables["GEMINI_API_KEY"].get().strip()
        if not key or key.startswith("your_"):
            self.messagebox.showinfo("Gemini key required", "Add your Gemini API key first.\n"
                                     "Use the 'Get a Gemini key' button to create one.", parent=self.root)
            self.entries[0].focus_set()
            return
        if not self.save():
            return
        try:
            self.controller.start()
        except OSError as exc:
            self.messagebox.showerror("Couldn't start S.A.R.A", str(exc), parent=self.root)
            return
        self.busy(True)
        self.status.set("Starting your local server…")
        self._deadline = time.monotonic() + 45
        self._startup_check = self.root.after(250, self.check_startup)

    def check_startup(self) -> None:
        self._startup_check = None
        if self.controller.ready():
            self.status.set(f"Online · {self.controller.url}")
            self.open_button.configure(state="normal")
            self.open_browser()
        elif not self.controller.running or time.monotonic() >= self._deadline:
            self.stop()
            self.status.set(f"Startup failed. Check {self.controller.log_path}")
            self.messagebox.showerror("S.A.R.A couldn't start", "See sara.log in the settings / logs folder.\n"
                                      "Check your settings, then try again.", parent=self.root)
        else:
            self._startup_check = self.root.after(250, self.check_startup)

    def stop(self) -> None:
        if self._startup_check is not None:
            self.root.after_cancel(self._startup_check)
            self._startup_check = None
        self.controller.stop()
        self.busy(False)
        self.status.set("Server stopped. You can edit settings or start again.")

    def monitor(self) -> None:
        if self.controller.process is not None and not self.controller.running and self._startup_check is None:
            self.stop()
            self.status.set(f"Server exited. Check {self.controller.log_path}")
        self.root.after(1500, self.monitor)

    def open_browser(self) -> None:
        if not webbrowser.open(self.controller.url):
            self.messagebox.showinfo("Open S.A.R.A", f"Open this address in Chrome or Edge:\n{self.controller.url}",
                                     parent=self.root)

    def open_folder(self) -> None:
        path = user_data_dir()
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as exc:
            self.messagebox.showerror("Couldn't open folder", str(exc), parent=self.root)

    def close(self) -> None:
        self.stop()
        self.root.destroy()


def check_install(report_path: Path) -> int:
    """Offline build diagnostic: verify bundled SDKs, assets and the native GUI."""
    report = {"version": __version__, "ok": False}
    try:
        import tkinter as tk
        from backend.main import app
        from backend.sara.llm import _build_tools
        from google import genai
        from elevenlabs.client import ElevenLabs

        assert app.title.startswith("S.A.R.A")
        # Construct configured SDKs and tool schemas with dummy keys, without
        # calling a provider. Missing-key-only tests would miss lazy imports.
        google_client = genai.Client(api_key="offline-installation-diagnostic")
        ElevenLabs(api_key="offline-installation-diagnostic")
        if hasattr(google_client, "close"):
            google_client.close()
        assert _build_tools()[0].function_declarations
        for asset in ("frontend/index.html", "frontend/css/style.css", "frontend/js/app.js",
                      "packaging/assets/sara.ico"):
            if not (resource_root() / asset).is_file():
                raise FileNotFoundError(asset)
        root = tk.Tk()
        root.withdraw()
        # Construct the real window, but prevent automatic API-backed startup.
        desktop = DesktopApp(root)
        root.update_idletasks()
        desktop.close()
        report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="S.A.R.A desktop launcher")
    parser.add_argument("--serve", action="store_true", help="internal local-server mode")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check-install", type=Path, metavar="REPORT", help="write an offline installation diagnostic")
    args = parser.parse_args()
    os.environ["SARA_DESKTOP"] = "1"
    if args.check_install:
        return check_install(args.check_install)
    if args.serve:
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        os.environ["SARA_LOCAL_ORIGIN"] = f"http://127.0.0.1:{args.port}"
        from backend.main import app
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=args.port, loop="asyncio", http="h11", ws="none",
                    access_log=False, use_colors=False)
        return 0

    import tkinter as tk
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    # Windowed Windows executables have no stdout/stderr; give logging and SDK
    # error messages a real stream rather than letting Uvicorn fail at startup.
    if sys.stdout is None or sys.stderr is None:
        directory = user_data_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        log_name = "sara.log" if "--serve" in sys.argv else "launcher.log"
        log_stream = (directory / log_name).open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log_stream
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        if "--serve" not in sys.argv and "--check-install" not in sys.argv:
            from tkinter import messagebox
            messagebox.showerror("S.A.R.A error", f"S.A.R.A couldn't start. See {user_data_dir() / 'launcher.log'}")
        raise SystemExit(1)
