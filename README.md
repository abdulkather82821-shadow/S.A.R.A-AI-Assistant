# S.A.R.A — Smart Assistant for Responsive Actions

> A J.A.R.V.I.S-style personal AI assistant you can talk to from **any** laptop
> or mobile browser. Powered by **Google Gemini** for intelligence and
> **ElevenLabs** for voice, using the voice
> [`r1KmysJdVYZjJCm4mL3b`](https://elevenlabs.io/voices/r1KmysJdVYZjJCm4mL3b)
> (Sarah — warm, crisp American English) by default.

```
  ╔════════════════════════════════════════════╗
  ║   ███████╗ █████╗ ██████╗  █████╗         ║
  ║   ██╔════╝██╔══██╗██╔══██╗██╔══██╗        ║
  ║   ███████╗███████║██████╔╝███████║        ║
  ║   ╚════██║██╔══██║██╔══██╗██╔══██║        ║
  ║   ███████║██║  ██║██║  ██║██║  ██║        ║
  ║   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝        ║
  ║          Smart Assistant                   ║
  ║        for Responsive Actions             ║
  ╚════════════════════════════════════════════╝
```

## Features

- 🎙️ **Voice-first conversation** — hold the mic button (or tap on mobile) to speak;
  uses the browser's built-in Web Speech API with automatic fallback to Gemini
  transcription on unsupported browsers.
- 🔊 **Natural ElevenLabs voice** — S.A.R.A responds out loud using your
  chosen Sarah voice (`r1KmysJdVYZjJCm4mL3b`).
- 🧠 **Gemini 2.0 Flash reasoning** with function-calling tools:
  - Telling time & date
  - Weather anywhere (Open-Meteo, no extra key needed)
  - Web search (DuckDuckGo instant answers)
  - Live news headlines (Google News RSS)
  - Calculator / math
  - System diagnostics (CPU, RAM, battery, uptime of the host machine)
  - Open websites on your device ("open YouTube", "open Gmail"…)
  - Set countdown timers on your device
  - Run safe shell commands on the host (blocked: `rm`, `sudo`, `curl`, `wget`…)
  - Tell jokes, describe herself
- 📱 **Responsive J.A.R.V.I.S HUD** — glowing cyan UI with animated core,
  audio visualizer rings, starfield background, scanlines, and live
  time/battery/connection readouts. Works on phones and laptops.
- ⌨️ **Hotkey**: press `Ctrl/Cmd + Space` to start/stop listening.
- 🔐 **Private & local**: your voice and text go directly from your browser to
  the Python backend you run, then to Gemini/ElevenLabs over HTTPS. No third
  parties, no tracking.

## Project layout

```
S.A.R.A-AI-Assistant/
├── backend/
│   ├── main.py              # FastAPI app: /api/chat, /api/tts, /api/stt, /api/wake
│   └── sara/
│       ├── config.py        # Loads .env
│       ├── llm.py           # Gemini client + streaming chat + tool-calling loop
│       ├── tts.py           # ElevenLabs TTS synthesizer
│       └── tools.py         # Built-in skills (time, weather, search, …)
├── frontend/
│   ├── index.html           # J.A.R.V.I.S HUD
│   ├── css/style.css        # Cyan/neon theme
│   └── js/app.js            # Voice capture, SSE streaming, visualizer, actions
├── requirements.txt
├── run.py                   # Uvicorn launcher
├── run.sh                   # One-shot venv + launch script (macOS/Linux)
├── .env.example             # Copy to .env and add keys
└── README.md
```

## Quick start (macOS / Linux)

1. **Clone the repo** and open it:
   ```bash
   git clone <your-repo-url>
   cd S.A.R.A-AI-Assistant
   ```

2. **Get your API keys**:
   - **Gemini**: https://aistudio.google.com/app/apikey (free)
   - **ElevenLabs**: https://elevenlabs.io/app/settings/api-keys (free tier gives
     ~10k characters/month — plenty for personal use)

3. **Run the launcher**:
   ```bash
   ./run.sh
   ```
   On the first run it will create a `.venv`, install dependencies, and copy
   `.env.example` to `.env`. Then edit `.env` with your keys and re-run
   `./run.sh`.

4. **Open S.A.R.A**:
   - On the same machine: visit http://localhost:8000
   - From your phone on the same Wi-Fi: visit http://<your-laptop-ip>:8000
     (your OS may ask to allow Python through the firewall — say yes).

## Quick start (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edit .env with Notepad to add your API keys
python run.py
```

Then open http://localhost:8000 in Chrome/Edge.

## `.env` reference

| Variable              | Purpose                                                              | Default                        |
|-----------------------|----------------------------------------------------------------------|--------------------------------|
| `GEMINI_API_KEY`      | Google Gemini API key                                                | *(required)*                   |
| `ELEVENLABS_API_KEY`  | ElevenLabs API key                                                   | *(required)*                   |
| `ELEVENLABS_VOICE_ID` | Which voice S.A.R.A speaks with                                      | `r1KmysJdVYZjJCm4mL3b` (Sarah) |
| `SARA_OWNER_NAME`     | How S.A.R.A addresses you (e.g. `"Sir"`, `"Boss"`, `"Alex"`)         | `Sir`                          |
| `SARA_LATITUDE`       | Optional fixed latitude for weather (otherwise IP/geolocation used)  | *(auto-detect)*                |
| `SARA_LONGITUDE`      | Optional fixed longitude                                             | *(auto-detect)*                |

## Using S.A.R.A

- Click the 🎙 mic button (or press `Ctrl+Space` / `Cmd+Space`) to speak.
- On desktops with Web Speech support (Chrome/Edge/Safari), S.A.R.A listens
  until you pause, then automatically sends your request.
- On browsers without Web Speech API, tap the mic again to stop recording;
  the audio is transcribed by Gemini.
- S.A.R.A responds with text *and* spoken audio. Her voice plays automatically
  (browsers may require one tap first due to autoplay policies — the initial
  boot greeting handles that).
- Type in the box at any time if voice isn't convenient.

Try these:

- "What time is it?"
- "What's the weather in London?"
- "Search for the latest AI news"
- "Open YouTube"
- "Set a timer for 2 minutes"
- "Run a system diagnostic"
- "Tell me a joke"
- "Who are you?"

## Switching voices

You can change S.A.R.A's voice at any time by editing `ELEVENLABS_VOICE_ID` in
`.env` and restarting the server. You can grab any ElevenLabs voice ID from
its share URL (the last slug is the ID). For example:

- Sarah (default): `r1KmysJdVYZjJCm4mL3b`
- Any other voice from https://elevenlabs.io/voices → copy the ID from the URL.

You can also **clone your own voice** in ElevenLabs and paste that voice ID.

## Running on mobile

The recommended way:

1. Start S.A.R.A on your laptop with `./run.sh`.
2. Find your laptop's local IP (on macOS/Linux: `ifconfig` / `ip a`).
3. Make sure your phone is on the same Wi-Fi network.
4. Open `http://<laptop-ip>:8000` in Chrome or Safari on your phone.
5. Tap the mic and grant microphone permission when prompted.

For true always-on access you can deploy the backend to a small VPS, a
Raspberry Pi, or a service like Render / Fly.io — just make sure HTTPS is
enabled (browsers require it for microphone access except on `localhost`).

## Extending S.A.R.A

Add a new skill by writing a function in `backend/sara/tools.py`:

```python
def launch_mission(planet: str) -> dict:
    """Begin a deep-space mission to the given planet."""
    return {"action": "mission_log", "planet": planet, "status": "engaged"}
```

It's automatically registered as a Gemini function-calling tool — no other
wiring needed. Restart the server and say "Launch a mission to Mars".

## Notes & safety

- The `run_terminal_command` tool blocks obvious dangerous operations (`rm`,
  `sudo`, `curl`, `wget`, `chmod 777`, etc.). Only run S.A.R.A on a machine
  you control, and treat it as you would any shell.
- Don't commit `.env` to version control (it's already in `.gitignore`).
- If you expose the server to the internet, put it behind HTTPS (e.g. via
  Caddy/Cloudflare Tunnel) and add authentication — there's none built in
  because this is designed for personal use.

Welcome online, Sir/Madam. S.A.R.A is standing by.
