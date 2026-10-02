; Compile after PyInstaller: ISCC.exe /DAppVersion=1.1.0 packaging\installer.iss
#ifndef AppVersion
  #error AppVersion must be supplied by scripts/build-windows.ps1
#endif

[Setup]
AppId={{73439E6D-CE19-498F-A44F-233D688197BB}
AppName=S.A.R.A
AppVersion={#AppVersion}
AppPublisher=S.A.R.A Contributors
AppPublisherURL=https://github.com/abdulkather82821-shadow/S.A.R.A-AI-Assistant
AppSupportURL=https://github.com/abdulkather82821-shadow/S.A.R.A-AI-Assistant/issues
DefaultDirName={localappdata}\Programs\SARA
DefaultGroupName=S.A.R.A
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
UninstallDisplayIcon={app}\SARA.exe
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
SetupIconFile=assets\sara.ico
InfoBeforeFile=windows-install-notes.txt
OutputDir=..\dist\installer
OutputBaseFilename=SARA-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\SARA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\S.A.R.A"; Filename: "{app}\SARA.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\S.A.R.A"; Filename: "{app}\SARA.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SARA.exe"; Description: "Launch S.A.R.A"; Flags: nowait postinstall skipifsilent

; Intentionally no deletion of %LOCALAPPDATA%\SARA on uninstall. That directory
; contains the user's API keys/settings, not installation files.
