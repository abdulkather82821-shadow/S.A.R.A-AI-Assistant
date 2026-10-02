"""Resource and configuration paths for source and installed applications."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_desktop() -> bool:
    return bool(getattr(sys, "frozen", False)) or os.getenv("SARA_DESKTOP") == "1"


def resource_root() -> Path:
    """Bundled assets are read-only; never save credentials alongside them."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Use a writable, per-user location, independent of the working directory."""
    if override := os.getenv("SARA_DATA_DIR"):
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "SARA"


def profile_env_path() -> Path:
    if override := os.getenv("SARA_ENV_FILE"):
        return Path(override).expanduser().resolve()
    return user_data_dir() / ".env"


def config_path() -> Path:
    if os.getenv("SARA_ENV_FILE") or is_desktop():
        return profile_env_path()
    return resource_root() / ".env"
