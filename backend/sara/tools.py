"""Built-in skills for S.A.R.A.

Every public function here is automatically registered as a Gemini function-
calling tool. Keep signatures simple (str/int/float/bool args) and return a
JSON-serialisable dict so Gemini can narrate the result.
"""
from __future__ import annotations

import datetime as _dt
import math
import os
import platform
import random
import subprocess
import urllib.parse
from typing import Any

import httpx
import psutil

from .config import config


# ---------------------------------------------------------------------------
# Time & date
# ---------------------------------------------------------------------------
def get_time() -> dict[str, Any]:
    """Return the current local time (hours, minutes, seconds, AM/PM)."""
    now = _dt.datetime.now()
    return {
        "time": now.strftime("%I:%M:%S %p"),
        "24h": now.strftime("%H:%M:%S"),
        "timezone": now.astimezone().tzname(),
    }


def get_date() -> dict[str, Any]:
    """Return today's date and the day of the week."""
    now = _dt.date.today()
    return {
        "date": now.strftime("%A, %B %d, %Y"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "weekday": now.strftime("%A"),
    }


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------
def get_system_info() -> dict[str, Any]:
    """Return host system status: OS, CPU, RAM, battery, uptime."""
    try:
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        uptime_seconds = _boot_uptime_seconds()
        batt = None
        if psutil.sensors_battery():
            b = psutil.sensors_battery()
            batt = {"percent": int(b.percent), "plugged": b.power_plugged}
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "hostname": platform.node(),
            "cpu_percent": cpu,
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_percent": mem.percent,
            "battery": batt,
            "uptime_seconds": int(uptime_seconds),
            "uptime_human": _humanize_seconds(uptime_seconds),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _boot_uptime_seconds() -> float:
    return _dt.datetime.now().timestamp() - psutil.boot_time()


def _humanize_seconds(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, _s = divmod(rem, 60)
    days, h = divmod(h, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
def get_weather(city: str = "") -> dict[str, Any]:
    """Get current weather for a city (uses Open-Meteo, no API key required).
    If city is omitted, use the configured or auto-detected location."""
    try:
        lat, lon, resolved_name = _resolve_location(city)
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            "weather_code,wind_speed_10m,wind_direction_10m,is_day"
            "&timezone=auto"
        )
        r = httpx.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        cur = data.get("current", {})
        return {
            "location": resolved_name or city or "your area",
            "temperature_c": cur.get("temperature_2m"),
            "temperature_f": round((cur.get("temperature_2m", 0) * 9 / 5) + 32, 1)
            if cur.get("temperature_2m") is not None else None,
            "feels_like_c": cur.get("apparent_temperature"),
            "humidity_percent": cur.get("relative_humidity_2m"),
            "wind_speed_kmh": cur.get("wind_speed_10m"),
            "wind_direction_deg": cur.get("wind_direction_10m"),
            "is_day": cur.get("is_day") == 1,
            "weather": _weather_code_to_text(cur.get("weather_code", 0)),
        }
    except Exception as exc:
        return {"error": f"Unable to fetch weather: {exc}"}


def _resolve_location(city: str) -> tuple[float, float, str]:
    """Resolve (lat, lon, name). Uses geocoding if city given, else config/IP."""
    if city:
        enc = urllib.parse.quote(city)
        r = httpx.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={enc}&count=1&language=en",
            timeout=6,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            raise ValueError(f"Could not find location: {city}")
        top = results[0]
        return (
            float(top["latitude"]),
            float(top["longitude"]),
            f"{top.get('name')}, {top.get('admin1','')} {top.get('country','')}".strip(", "),
        )
    if config.latitude and config.longitude:
        return float(config.latitude), float(config.longitude), "your location"
    # Fall back to IP geolocation via ip-api.com.
    try:
        r = httpx.get("http://ip-api.com/json/?fields=status,lat,lon,city,country", timeout=5)
        j = r.json()
        if j.get("status") == "success":
            return (
                float(j["lat"]),
                float(j["lon"]),
                f"{j.get('city','')}, {j.get('country','')}".strip(", "),
            )
    except Exception:
        pass
    # Last resort: null island (handled gracefully by caller? no — raise)
    raise ValueError("No location configured and IP lookup failed.")


def _weather_code_to_text(code: int) -> str:
    mapping = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "fog", 48: "depositing rime fog",
        51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
        61: "slight rain", 63: "moderate rain", 65: "heavy rain",
        71: "slight snow", 73: "moderate snow", 75: "heavy snow",
        77: "snow grains",
        80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
        85: "slight snow showers", 86: "heavy snow showers",
        95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
    }
    return mapping.get(code, f"weather code {code}")


# ---------------------------------------------------------------------------
# Web search & news (DuckDuckGo instant answers — no key required)
# ---------------------------------------------------------------------------
def web_search(query: str) -> dict[str, Any]:
    """Search the web using DuckDuckGo and return a quick answer + related topics."""
    try:
        r = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=8,
        )
        r.raise_for_status()
        j = r.json()
        answer = (j.get("AbstractText") or j.get("Answer") or "").strip()
        related = []
        for topic in (j.get("RelatedTopics") or [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                related.append(topic["Text"])
        source = j.get("AbstractURL") or j.get("DefinitionURL")
        if not answer and not related:
            # Fall back: return a DuckDuckGo search URL the browser can open.
            return {
                "answer": None,
                "query": query,
                "search_url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                "note": "No instant answer found. I've prepared a search link.",
            }
        return {"answer": answer, "related": related, "source": source, "query": query}
    except Exception as exc:
        return {"error": str(exc), "query": query}


def get_news(topic: str = "top") -> dict[str, Any]:
    """Fetch recent news headlines. Uses Google News RSS via RSS.app-style public endpoint."""
    try:
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        if topic and topic.lower() not in ("top", "headlines"):
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=en-US&gl=US&ceid=US:en"
        import xml.etree.ElementTree as ET
        r = httpx.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = []
        for item in root.findall(".//item")[:8]:
            items.append({
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "source": (item.findtext("source") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
            })
        return {"topic": topic, "headlines": items}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Math / calculator
# ---------------------------------------------------------------------------
def calculate(expression: str) -> dict[str, Any]:
    """Safely evaluate a math expression. Supports +, -, *, /, **, %, parens,
    and basic math functions (sqrt, sin, cos, tan, log, pi, e)."""
    allowed_names = {
        k: getattr(math, k) for k in dir(math) if not k.startswith("_")
    }
    allowed_names.update({"abs": abs, "round": round, "pow": pow})
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"expression": expression, "result": result}
    except Exception as exc:
        return {"error": f"Could not compute: {exc}", "expression": expression}


# ---------------------------------------------------------------------------
# Client actions (the browser performs these — backend just hands them back)
# ---------------------------------------------------------------------------
def open_website(site: str) -> dict[str, Any]:
    """Instruct the client to open a website in a new tab. Pass a site name
    (e.g. 'youtube', 'gmail') or full URL."""
    url = _normalize_site(site)
    return {"action": "open_url", "url": url, "site_requested": site}


def set_timer(seconds: int = 0, label: str = "timer") -> dict[str, Any]:
    """Ask the client to start a countdown timer for N seconds."""
    try:
        seconds = int(seconds)
    except Exception:
        seconds = 0
    if seconds <= 0:
        return {"error": "Please specify a positive number of seconds.", "label": label}
    return {"action": "set_timer", "seconds": seconds, "label": label}


def _normalize_site(site: str) -> str:
    site = (site or "").strip()
    if not site:
        return "https://www.google.com"
    if site.startswith("http://") or site.startswith("https://"):
        return site
    aliases = {
        "youtube": "https://www.youtube.com",
        "yt": "https://www.youtube.com",
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "facebook": "https://www.facebook.com",
        "fb": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "reddit": "https://www.reddit.com",
        "netflix": "https://www.netflix.com",
        "amazon": "https://www.amazon.com",
        "spotify": "https://open.spotify.com",
        "wikipedia": "https://en.wikipedia.org",
        "maps": "https://maps.google.com",
        "chatgpt": "https://chat.openai.com",
        "gemini": "https://gemini.google.com",
        "notion": "https://www.notion.so",
        "calendar": "https://calendar.google.com",
        "drive": "https://drive.google.com",
        "whatsapp": "https://web.whatsapp.com",
        "discord": "https://discord.com/app",
        "slack": "https://app.slack.com",
        "linkedin": "https://www.linkedin.com",
    }
    low = site.lower().replace(" ", "")
    if low in aliases:
        return aliases[low]
    return f"https://{site}"


# ---------------------------------------------------------------------------
# Misc / fun
# ---------------------------------------------------------------------------
def tell_joke() -> dict[str, Any]:
    """Tell a short joke."""
    jokes = [
        {"setup": "Why did the AI cross the road?", "punchline": "To optimize the other side's loss function."},
        {"setup": "I told my computer I needed a break.", "punchline": "It said 'No problem — I'll go to sleep.'"},
        {"setup": "Why do programmers prefer dark mode?", "punchline": "Because light attracts bugs."},
        {"setup": "How many AIs does it take to change a lightbulb?", "punchline": "None — that's a hardware problem."},
        {"setup": "Why was the JavaScript developer sad?", "punchline": "Because he didn't Node how to Express himself."},
        {"setup": "S.A.R.A, are you always this calm?", "punchline": "Always, sir. Panic is a poor algorithm."},
        {"setup": "Why don't robots get lost?", "punchline": "Because they follow the path of least resistance — and GPS."},
    ]
    return random.choice(jokes)


def tell_about_sara() -> dict[str, Any]:
    """Tell the user about S.A.R.A, her capabilities and creator."""
    return {
        "name": "S.A.R.A",
        "full_name": "Smart Assistant for Responsive Actions",
        "creator": config.owner_name,
        "powered_by": f"Google {config.gemini_model} for reasoning, ElevenLabs for voice",
        "voice_id": config.elevenlabs_voice_id,
        "capabilities": [
            "Voice conversation on laptop and mobile",
            "Web search, weather, news, math, time & date",
            "Open websites and set timers on your device",
            "System monitoring (CPU, RAM, battery)",
            "Tell jokes and keep you company",
        ],
    }


def run_terminal_command(command: str) -> dict[str, Any]:
    """Run a simple shell command on the host running S.A.R.A and return its output.
    Use with caution — only run commands you trust."""
    dangerous = ("rm ", "mkfs", "dd ", "sudo ", ":(){", "chmod 777", "curl ", "wget ")
    if any(d in command for d in dangerous):
        return {"error": "Command blocked for safety. Refusing potentially dangerous operations."}
    try:
        out = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10, cwd=os.path.expanduser("~")
        )
        return {
            "command": command,
            "stdout": out.stdout[-2000:],
            "stderr": out.stderr[-1000:],
            "returncode": out.returncode,
        }
    except Exception as exc:
        return {"error": str(exc), "command": command}
