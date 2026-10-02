"""S.A.R.A configuration for source launches and the Windows desktop app."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .defaults import DEFAULT_GEMINI_MODEL, DEFAULT_VOICE_ID
from .paths import config_path, is_desktop


@dataclass
class Config:
    gemini_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    owner_name: str
    latitude: str | None
    longitude: str | None
    gemini_model: str = DEFAULT_GEMINI_MODEL

    @classmethod
    def load(cls) -> "Config":
        # Installed settings take precedence over stale inherited variables.
        # Source launches retain the usual environment-over-.env behavior.
        load_dotenv(config_path(), override=is_desktop(), interpolate=False)
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID,
            owner_name=os.getenv("SARA_OWNER_NAME") or "Sir",
            latitude=os.getenv("SARA_LATITUDE") or None,
            longitude=os.getenv("SARA_LONGITUDE") or None,
            gemini_model=os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
        )


config = Config.load()
