"""ElevenLabs text-to-speech integration for S.A.R.A.

Uses the ElevenLabs SDK to synthesize speech with the user's chosen voice
(`r1KmysJdVYZjJCm4mL3b` - "Sarah" by default). Returns MP3 audio bytes.
"""
from __future__ import annotations

import io
from typing import Optional

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from .config import config


class SaraTTS:
    def __init__(self) -> None:
        self.client: Optional[ElevenLabs] = None
        self._missing_key = True
        if config.elevenlabs_api_key and not config.elevenlabs_api_key.startswith("your_"):
            self.client = ElevenLabs(api_key=config.elevenlabs_api_key)
            self._missing_key = False

    def synthesize(self, text: str) -> bytes:
        """Synthesize `text` and return MP3 bytes. Falls back to silence on error."""
        if self._missing_key or self.client is None:
            return _silence_mp3()
        if not text or not text.strip():
            return _silence_mp3()

        # Clean text for speech (remove URLs, extra punctuation quirks).
        cleaned = _clean_for_speech(text)

        try:
            audio_iter = self.client.text_to_speech.convert(
                voice_id=config.elevenlabs_voice_id,
                output_format="mp3_44100_128",
                text=cleaned,
                model_id="eleven_turbo_v2_5",  # fast, low-latency
                voice_settings=VoiceSettings(
                    stability=0.45,
                    similarity_boost=0.8,
                    style=0.35,
                    use_speaker_boost=True,
                ),
            )
            buf = io.BytesIO()
            for chunk in audio_iter:
                if chunk:
                    buf.write(chunk)
            data = buf.getvalue()
            return data if data else _silence_mp3()
        except Exception as exc:
            print(f"[S.A.R.A TTS error] {exc}")
            return _silence_mp3()


def _clean_for_speech(text: str) -> str:
    """Lightly sanitize text so TTS doesn't try to read URLs/Markdown."""
    import re
    # Replace URLs with "link"
    text = re.sub(r"https?://\S+", "a link", text)
    # Replace markdown bold/italics
    text = re.sub(r"[*_`#]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _silence_mp3() -> bytes:
    """A minimal, valid silent MP3 frame (~0.026s) so the player has something."""
    return bytes.fromhex(
        "FFFB904400000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
    )


tts = SaraTTS()
