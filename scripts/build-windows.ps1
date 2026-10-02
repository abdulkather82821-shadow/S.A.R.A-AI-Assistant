# Run in PowerShell on 64-bit Windows with Python 3.11+ and Inno Setup 6.3+.
[CmdletBinding()]
param([switch]$SkipDependencyInstall)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & python -c "import sys, struct; assert sys.platform == 'win32' and struct.calcsize('P') == 8, 'Build on 64-bit Windows'; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"
    if ($LASTEXITCODE -ne 0) { throw "Unsupported build environment" }

    if (-not $SkipDependencyInstall) {
        & python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    }
    & python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

    & python -m PyInstaller --clean --noconfirm packaging/sara.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    & python scripts/smoke_windows.py --executable dist/SARA/SARA.exe
    if ($LASTEXITCODE -ne 0) { throw "Packaged application smoke test failed" }

    $Compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($Compiler) {
        $CompilerPath = $Compiler.Source
    } else {
        $CompilerPath = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    }
    if (-not (Test-Path $CompilerPath)) {
        throw "Install Inno Setup 6.3+ from https://jrsoftware.org/isdl.php, then rerun this script"
    }
    $Version = (& python -c "from backend.sara import __version__; print(__version__)").Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not read application version" }
    & $CompilerPath "/DAppVersion=$Version" packaging/installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed" }

    $Installer = Join-Path $Root "dist\installer\SARA-Setup-$Version-x64.exe"
    & python scripts/smoke_windows.py --installer $Installer
    if ($LASTEXITCODE -ne 0) { throw "Install / uninstall smoke test failed" }

    $Hash = (Get-FileHash $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
    $Checksum = "$Hash  $([System.IO.Path]::GetFileName($Installer))`n"
    [System.IO.File]::WriteAllText("$Installer.sha256", $Checksum, [System.Text.Encoding]::ASCII)
    Copy-Item packaging/windows-install-notes.txt dist/installer/INSTALL-WINDOWS.txt
    Write-Host "Installer ready: $Installer"
    Write-Host "SHA-256: $Hash"
} finally {
    Pop-Location
}
