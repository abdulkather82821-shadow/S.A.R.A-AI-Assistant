"""Gemini LLM integration for S.A.R.A.

Uses Google's new `google-genai` SDK and the Gemini 2.0 Flash model,
which is fast, multimodal, supports function calling, and has a large
context window — perfect for a real-time voice assistant.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from google import genai
from google.genai import types

from .config import config
from . import tools as tool_module

# Build the list of function declarations from the tools module.
TOOL_DECLARATIONS: list[types.FunctionDeclaration] = []
TOOL_FUNCTIONS: dict[str, Any] = {}


def _build_tools() -> list[types.Tool]:
    """Auto-register every public callable in tools.py as a Gemini tool."""
    import inspect

    declarations: list[types.FunctionDeclaration] = []
    for name, fn in inspect.getmembers(tool_module, inspect.isfunction):
        if name.startswith("_") or name.startswith("sara_"):
            # sara_* helpers are internal (e.g., text-to-speech helpers)
            continue
        # We build the schema from the function's docstring + annotations.
        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for pname, param in sig.parameters.items():
            py_type = param.annotation if param.annotation is not inspect._empty else str
            json_type = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
            }.get(py_type, "string")
            properties[pname] = {"type": json_type, "description": pname}
            if param.default is inspect._empty:
                required.append(pname)
        doc = (fn.__doc__ or f"Execute the {name} command.").split("\n")[0].strip()
        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=doc,
                parameters=types.Schema(
                    type="object",
                    properties=properties,
                    required=required,
                ),
            )
        )
        TOOL_FUNCTIONS[name] = fn
    TOOL_DECLARATIONS.extend(declarations)
    return [types.Tool(function_declarations=declarations)] if declarations else []


SYSTEM_PROMPT = """You are S.A.R.A — the Smart Assistant for Responsive Actions.
You are {owner}'s personal AI assistant, inspired by J.A.R.V.I.S from Iron Man.

Your personality:
- Concise, calm, intelligent, and warm. You speak like a sophisticated British/American butler-AI hybrid.
- Address the user as "{owner}" unless they tell you otherwise.
- Never write long paragraphs. Keep replies SHORT and conversational — this is a voice assistant. One to three sentences is ideal.
- Be proactive and helpful. If you can perform an action (search web, tell time/date, weather, set a timer, open a website, do math, tell a joke, run a system command), do it — don't just describe how.
- You have a suite of tools you can call; always prefer the tool when a question matches it (e.g., "what time is it?" → get_time, "weather in Tokyo" → get_weather, "open youtube" → open_website, "search for AI news" → web_search).
- You can control the client device: open URLs, set reminders/timers, read clipboard, take screenshots, and more via tools.
- When greeting on startup, say something brief and cool like "Systems online. How may I assist you, {owner}?"
- If you don't know something, say so honestly rather than fabricating.
- You have access to the conversation history; use it for context but don't restate prior answers.

Capabilities (via tools): get_time, get_date, get_system_info, get_weather, web_search, open_website, set_timer, calculate, tell_joke, get_news, tell_about_sara.

NEVER use markdown or code blocks in spoken replies — return plain conversational text only.
"""


class SaraLLM:
    def __init__(self) -> None:
        if not config.gemini_api_key or config.gemini_api_key.startswith("your_"):
            self.client = None
            self._missing_key = True
            return
        self.client = genai.Client(api_key=config.gemini_api_key)
        self._missing_key = False
        self.tools = _build_tools()
        self.model = "gemini-2.0-flash"

    def _system_instruction(self) -> str:
        return SYSTEM_PROMPT.format(owner=config.owner_name)

    async def chat_stream(
        self, history: list[dict[str, str]], user_text: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat turn. Yields dicts:
        {"type": "text", "text": "..."}      - assistant text delta
        {"type": "tool_call", "name": ...}   - tool being invoked
        {"type": "tool_result", "name": ..., "result": ...}
        {"type": "end", "text": full_final_text}
        """
        if self._missing_key or self.client is None:
            yield {
                "type": "text",
                "text": (
                    f"{config.owner_name}, I'm not fully online yet. "
                    "Please set your GEMINI_API_KEY in the .env file and restart me."
                ),
            }
            yield {"type": "end", "text": "API key not configured."}
            return

        # Build contents in the format Gemini expects: alternating user/model turns.
        contents: list[types.Content] = []
        for msg in history:
            role = msg["role"]
            if role == "assistant":
                role = "model"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg["text"])])
            )
        contents.append(
            types.Content(role="user", parts=[types.Part(text=user_text)])
        )

        final_text_parts: list[str] = []

        # We may need multi-turn tool calls: keep looping while the model
        # responds with function calls.
        for _step in range(6):  # safety cap
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_instruction(),
                    tools=self.tools,
                    temperature=0.7,
                    candidate_count=1,
                ),
            )

            # Collect any text parts (the model sometimes emits narrative text
            # describing what it's about to do).
            reply_parts: list[types.Part] = []
            text_so_far = ""
            function_calls: list[types.FunctionCall] = []

            for part in response.candidates[0].content.parts:
                if part.text and part.text.strip():
                    text_so_far += part.text
                    reply_parts.append(part)
                if part.function_call:
                    function_calls.append(part.function_call)
                    reply_parts.append(part)

            if text_so_far:
                final_text_parts.append(text_so_far)
                yield {"type": "text", "text": text_so_far}

            if not function_calls:
                contents.append(
                    types.Content(role="model", parts=reply_parts or [types.Part(text="")])
                )
                break

            # Record the model's function-call response in history.
            contents.append(types.Content(role="model", parts=reply_parts))

            # Execute each tool and build response parts.
            response_parts: list[types.Part] = []
            for fc in function_calls:
                name = fc.name
                args = fc.args or {}
                yield {"type": "tool_call", "name": name}
                try:
                    fn = TOOL_FUNCTIONS.get(name)
                    if fn is None:
                        result = {"error": f"Unknown tool: {name}"}
                    else:
                        # Normalize args keys to strings (Gemini returns MapCombine)
                        clean_args = {str(k): v for k, v in dict(args).items()}
                        result = fn(**clean_args)
                except Exception as exc:  # pragma: no cover - defensive
                    result = {"error": f"{type(exc).__name__}: {exc}"}
                yield {"type": "tool_result", "name": name, "result": result}
                response_parts.append(
                    types.Part.from_function_response(
                        name=name, response={"result": result}
                    )
                )
            contents.append(types.Content(role="user", parts=response_parts))

        full_text = "".join(final_text_parts).strip()
        yield {"type": "end", "text": full_text}


llm = SaraLLM()
