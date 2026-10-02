"""S.A.R.A - Smart Assistant for Responsive Actions.
Configuration loading from environment variables.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    gemini_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    owner_name: str
    latitude: str | None
    longitude: str | None

    @classmethod
    def load(cls) -> "Config":
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.getenv(
                "ELEVENLABS_VOICE_ID", "r1KmysJdVYZjJCm4mL3b"
            ),
            owner_name=os.getenv("SARA_OWNER_NAME", "Sir"),
            latitude=os.getenv("SARA_LATITUDE") or None,
            longitude=os.getenv("SARA_LONGITUDE") or None,
        )


config = Config.load()
