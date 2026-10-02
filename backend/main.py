"""S.A.R.A FastAPI application.

Endpoints:
  GET  /api/health           - health check + server info
  GET  /api/config           - public config (which keys are set, voice id, owner)
  POST /api/chat             - streaming chat (SSE) - returns text deltas + tool events
  POST /api/tts              - text-to-speech: returns MP3 audio
  POST /api/stt              - speech-to-text via Gemini's multimodal audio input
  GET  /api/wake             - simple wake/startup greeting
  GET  / ...                 - static frontend files
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    JSONResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles
from urllib.parse import urlsplit

from backend.sara import __version__
from backend.sara.config import config
from backend.sara.llm import llm
from backend.sara.paths import is_desktop, resource_root
from backend.sara.tts import tts as tts_service

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
FRONTEND_DIR = resource_root() / "frontend"

app = FastAPI(
    title="S.A.R.A — Smart Assistant for Responsive Actions",
    version=__version__,
    description="A J.A.R.V.I.S-style personal AI assistant (Gemini + ElevenLabs).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("SARA_LOCAL_ORIGIN", "http://127.0.0.1:8000")] if is_desktop() else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def desktop_origin_guard(request: Request, call_next):
    """Do not let arbitrary websites or DNS rebinding reach an installed app.

    Source/LAN/hosted launches keep their existing behavior. The desktop
    launcher also binds only to loopback, using an automatically chosen port.
    """
    if is_desktop():
        allowed = os.getenv("SARA_LOCAL_ORIGIN", "http://127.0.0.1:8000")
        if (request.headers.get("host") != urlsplit(allowed).netloc
                or request.headers.get("origin") not in (None, allowed)
                or request.headers.get("sec-fetch-site") == "cross-site"):
            return JSONResponse({"detail": "Local desktop requests only."}, status_code=403)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class STTRequest(BaseModel):
    """Client sends audio as a base64-encoded data URL; we forward to Gemini."""
    audio_data_url: str


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "name": "S.A.R.A",
        "version": __version__,
        "gemini_model": config.gemini_model,
        "desktop_instance": os.getenv("SARA_DESKTOP_INSTANCE", ""),
        "gemini_configured": bool(config.gemini_api_key) and not config.gemini_api_key.startswith("your_"),
        "elevenlabs_configured": bool(config.elevenlabs_api_key) and not config.elevenlabs_api_key.startswith("your_"),
        "voice_id": config.elevenlabs_voice_id,
        "owner": config.owner_name,
        "time": time.time(),
    }


@app.get("/api/config")
async def public_config() -> dict[str, Any]:
    return {
        "name": "S.A.R.A",
        "full_name": "Smart Assistant for Responsive Actions",
        "owner": config.owner_name,
        "voice_id": config.elevenlabs_voice_id,
        "gemini_configured": bool(config.gemini_api_key) and not config.gemini_api_key.startswith("your_"),
        "elevenlabs_configured": bool(config.elevenlabs_api_key) and not config.elevenlabs_api_key.startswith("your_"),
    }


@app.get("/api/wake")
async def wake():
    """Return an opening greeting synthesized as audio, plus the text."""
    import datetime as _dt
    hour = _dt.datetime.now().hour
    if hour < 5:
        greeting = f"Systems online. It's the middle of the night, {config.owner_name}. What can I do for you?"
    elif hour < 12:
        greeting = f"Good morning, {config.owner_name}. S.A.R.A is online and ready."
    elif hour < 18:
        greeting = f"Good afternoon, {config.owner_name}. All systems nominal."
    else:
        greeting = f"Good evening, {config.owner_name}. S.A.R.A standing by."
    audio = tts_service.synthesize(greeting)
    return {
        "text": greeting,
        "audio_base64": "data:audio/mp3;base64," + _b64(audio),
    }


def _b64(b: bytes) -> str:
    import base64
    return base64.b64encode(b).decode("ascii")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Stream assistant response as Server-Sent Events."""
    async def event_stream():
        loop = asyncio.get_running_loop()

        # We can't directly iterate an async generator from a sync SDK in all
        # paths, but SaraLLM.chat_stream is an async generator that runs sync
        # Gemini calls. We'll offload each iteration to a thread to avoid
        # blocking the loop.
        agen = llm.chat_stream(req.history, req.message)

        async def anext():
            try:
                return await agen.__anext__()
            except StopAsyncIteration:
                return None

        full_text = ""
        while True:
            evt = await anext()
            if evt is None:
                break
            if evt["type"] == "text":
                full_text += evt["text"]
                yield _sse("text", {"text": evt["text"]})
            elif evt["type"] == "tool_call":
                yield _sse("tool_call", {"name": evt["name"]})
            elif evt["type"] == "tool_result":
                yield _sse(
                    "tool_result",
                    {"name": evt["name"], "result": evt["result"]},
                )
            elif evt["type"] == "end":
                # Synthesize full final text in a thread and attach audio.
                final_text = evt.get("text") or full_text
                audio = await loop.run_in_executor(None, tts_service.synthesize, final_text)
                yield _sse(
                    "end",
                    {
                        "text": final_text,
                        "audio_base64": "data:audio/mp3;base64," + _b64(audio),
                    },
                )
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    audio = tts_service.synthesize(req.text)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/stt")
async def speech_to_text(req: STTRequest):
    """Accepts a base64 data URL (e.g. from MediaRecorder webm/opus) and
    transcribes it with Gemini.  Returns {'text': ...}.
    Falls back gracefully if Gemini isn't configured or audio is empty.
    """
    if not config.gemini_api_key or config.gemini_api_key.startswith("your_"):
        raise HTTPException(400, "Gemini API key not configured.")

    import base64, re
    m = re.match(r"^data:(audio/\w+);base64,(.*)$", req.audio_data_url)
    if not m:
        raise HTTPException(400, "Invalid audio data URL.")
    mime = m.group(1)
    raw = base64.b64decode(m.group(2))
    if len(raw) < 500:
        return {"text": ""}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.gemini_api_key)
        # Use the audio as inline bytes; transcribe + lightly punctuate.
        response = client.models.generate_content(
            model=config.gemini_model,
            contents=[
                "Transcribe the following user speech accurately. "
                "Return ONLY the transcribed text, no commentary, no quotes.",
                types.Part.from_bytes(data=raw, mime_type=mime),
            ],
            config=types.GenerateContentConfig(temperature=0.1, candidate_count=1),
        )
        text = (response.text or "").strip().strip('"').strip()
        return {"text": text}
    except Exception as exc:
        return {"text": "", "error": str(exc)}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
# StaticFiles confines requests to the frontend directory, including when the
# app is frozen. Configuration and per-user credentials are never web assets.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
