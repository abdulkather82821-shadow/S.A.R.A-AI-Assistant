# Install S.A.R.A on a Windows laptop

## Requirements

- **64-bit Windows 10 (1809 or newer) or Windows 11.** The build is x64, not a
  native ARM64 or 32-bit Windows package.
- A browser; **Chrome or Edge** is recommended for microphone support.
- Internet access and your own **Google Gemini API key**. An **ElevenLabs key**
  is optional but required for ElevenLabs spoken replies. Provider quotas and
  charges still apply; this is not an offline AI model.
- **No separate Python, Git, Node.js, or developer tools are needed to install.**

## Download and install

1. Open the repository's [Build Windows installer workflow](https://github.com/abdulkather82821-shadow/S.A.R.A-AI-Assistant/actions/workflows/windows-installer.yml).
2. Choose a successful run for the branch/version you want. In **Artifacts**,
   download **SARA-Windows-x64** and extract it. GitHub requires sign-in for
   Actions artifact downloads, and these artifacts expire after 30 days.
3. Run **`SARA-Setup-1.1.0-x64.exe`** (the version changes for later builds).
   The installer installs for your Windows user and does not require admin
   rights. A Start-menu shortcut and uninstaller are included; a desktop
   shortcut is optional.
4. Launch **S.A.R.A** from the Start menu. In the native settings window, paste
   your Gemini API key. Use the **Get a Gemini key** button if needed. Add an
   ElevenLabs key for spoken replies, and optionally change your name, the
   voice ID, or the Gemini model.
5. Select **Start S.A.R.A**. The assistant opens in your default browser on a
   local address such as `http://127.0.0.1:54321`. Allow microphone access when
   asked. If your default browser isn't Chrome/Edge, copy the local address
   into one of those browsers.

Keep the desktop window open while using S.A.R.A. **Stop** stops the local
server so you can edit settings. Closing the desktop window also stops it.
After your first setup, launching S.A.R.A starts the server automatically.
A valid key and a model available to your Google account are needed for chat;
settings are not validated against the cloud until you use them.

### Windows security warnings

The installer and application are **unsigned**. Windows may show an unknown
publisher / SmartScreen warning. Only install a build you trust; do not
indiscriminately disable security protections. A `.sha256` file accompanies
an installer to verify download integrity, not its publisher or safety:

```powershell
Get-FileHash .\SARA-Setup-1.1.0-x64.exe -Algorithm SHA256
Get-Content .\SARA-Setup-1.1.0-x64.exe.sha256
```

Compare the hashes. Public distribution without unknown-publisher warnings
requires a Windows code-signing certificate, which this project does not
supply.

## Settings, privacy and uninstall

| Location | Contents |
| --- | --- |
| `%LOCALAPPDATA%\Programs\SARA` | Installed app and bundled runtime (default installation folder) |
| `%LOCALAPPDATA%\SARA\.env` | Personal API keys and settings |
| `%LOCALAPPDATA%\SARA\sara.log` | Local backend error log |
| `%LOCALAPPDATA%\SARA\launcher.log` | Desktop launcher error log |

The application never saves keys inside its installation files or bundles
keys in a build. The local `.env` is **not encrypted**; keep your Windows
account secure and do not share this file. Inspect logs for sensitive data
before sharing them.

The installed server listens **only on loopback**, uses an available port,
and rejects foreign Origin/Host headers. It is not exposed to your Wi-Fi
network. Prompts and audio still go to Gemini/ElevenLabs as applicable. Some
existing assistant tools can run shell commands; the command blocklist is
not a security sandbox. Run as a normal user, not as administrator, and only
make trusted requests.

Uninstall from **Windows Settings → Apps → Installed apps → S.A.R.A**.
Your personal configuration is preserved for reinstalls. To remove keys and
logs as well, delete `%LOCALAPPDATA%\SARA` after uninstalling. Do not delete
that directory if you want to preserve your settings.

## Troubleshooting

- **The browser doesn't open:** select **Open assistant**, or copy the local
  URL from the status line into Chrome/Edge.
- **Microphone doesn't work:** use Chrome/Edge, allow microphone access in
  browser and Windows privacy settings, and try the text input.
- **No spoken replies:** check the ElevenLabs key, voice ID and account quota.
  Without an ElevenLabs key, replies are text-only.
- **An API/model error:** check the key and change **Gemini model** to one
  supported by your account. Stop, save settings and start again.
- **Startup failure:** use **Open settings / logs folder** and inspect
  `sara.log`. No fixed port or Python installation is required.
- **Can't connect from a phone:** the installer intentionally supports only
  the local laptop. Use the source/LAN setup in the main README for other
  devices, with HTTPS for microphone access away from localhost.

## Build the `.exe` yourself (developers only)

PyInstaller builds must run **on Windows**, not on Linux with a renamed
binary. Install 64-bit Python 3.11+ and [Inno Setup 6.3+](https://jrsoftware.org/isdl.php).
Then open PowerShell in the repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\build-windows.ps1
```

If your system policy prevents virtual-environment activation, use the
[GitHub Actions workflow](https://github.com/abdulkather82821-shadow/S.A.R.A-AI-Assistant/actions/workflows/windows-installer.yml)
or invoke the build tools with the virtual environment on `PATH` instead of
weakening a machine-wide policy.

The script installs build dependencies, runs offline tests, freezes the app
with PyInstaller, checks the bundled GUI/backend/assets, compiles the Inno
Setup installer, performs a silent install/uninstall smoke test, and writes:

```text
dist/installer/SARA-Setup-1.1.0-x64.exe
dist/installer/SARA-Setup-1.1.0-x64.exe.sha256
dist/installer/INSTALL-WINDOWS.txt
```

Neither a provider API key nor a GitHub secret is required for a build. Build
outputs are ignored by Git; share them using Actions artifacts or a GitHub
Release, not commits. The stable installer AppId and separate profile folder
support reinstalling/upgrading without bundling or deleting personal keys.

### Source desktop development

```powershell
python -m pip install -r requirements.txt
python desktop_launcher.py
```

Tkinter is included with standard python.org Windows installations. For
source GUI development on Linux, install your distribution's Tk package;
headless server mode and the test suite do not require Tk.

`SARA_DATA_DIR` can override the profile directory, and `SARA_ENV_FILE` can
select a configuration file (useful for isolated testing). Bundled resource
paths are independent of the working directory. The desktop's `--serve` and
`--check-install REPORT.json` options are intended for its internal process
management and offline build diagnostics.
