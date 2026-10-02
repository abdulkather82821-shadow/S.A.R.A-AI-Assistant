# Build on Windows: python -m PyInstaller --clean --noconfirm packaging/sara.spec
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
from backend.sara import __version__

# Explicit allowlist: never bundle the repo root, .env, logs, or user settings.
datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "packaging" / "assets" / "sara.ico"), "packaging/assets"),
]
binaries = []
hiddenimports = [
    "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on", "backend.main",
]
for package in ("google.genai", "elevenlabs"):
    # Modules are already in PYZ. Duplicating SDK .py files can exceed Windows
    # MAX_PATH (notably ElevenLabs generated types) in user-selected folders.
    package_data, package_binaries, package_imports = collect_all(package, include_py_files=False)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
for distribution in ("google-genai", "elevenlabs"):
    datas += copy_metadata(distribution)

version_tuple = tuple(int(part) for part in __version__.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple,
                      mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1,
                      subtype=0x0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "S.A.R.A Contributors"),
            StringStruct("FileDescription", "S.A.R.A Desktop AI Assistant"),
            StringStruct("FileVersion", __version__),
            StringStruct("InternalName", "SARA"),
            StringStruct("OriginalFilename", "SARA.exe"),
            StringStruct("ProductName", "S.A.R.A"),
            StringStruct("ProductVersion", __version__),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

analysis = Analysis(
    [str(ROOT / "desktop_launcher.py")], pathex=[str(ROOT)],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["pytest", "IPython", "matplotlib", "numpy"], noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True, name="SARA",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon=str(ROOT / "packaging" / "assets" / "sara.ico"),
    version=version_info,
)
collection = COLLECT(
    exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="SARA",
)
