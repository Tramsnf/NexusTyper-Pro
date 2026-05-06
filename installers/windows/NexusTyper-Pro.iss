; Inno Setup script for NexusTyper Pro.
;
; Driven by .github/workflows/release.yml. The build step passes:
;   /DMyAppVersion=<display>     e.g. 3.4 or 0.0.0-dev.42
;   /DMyAppVersionNumeric=<4pt>  e.g. 3.4.0.0 — required by Windows VersionInfo
;   /DSourceDir=<path>           PyInstaller --windowed output folder
;   /DOutputDir=<path>           where to drop the resulting Setup.exe
;
; Keep AppId stable across releases — Inno Setup uses it to detect upgrades and
; replace prior installs. Regenerate ONLY if you fork the project under a new
; identity, otherwise users will end up with two parallel installs.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef MyAppVersionNumeric
  #define MyAppVersionNumeric "0.0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\NexusTyper Pro"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

#define MyAppName        "NexusTyper Pro"
#define MyAppPublisher   "NexusTyper"
#define MyAppURL         "https://github.com/Tramsnf/NexusTyper-Pro"
#define MyAppExeName     "NexusTyper Pro.exe"

[Setup]
AppId={{B2F3D7C4-1E5A-4F8B-A6F2-9C6D4E1F3A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersionNumeric}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#SourcePath}\..\..\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename=NexusTyper-Pro-{#MyAppVersion}-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; "lowest" lets the installer fall back to a per-user install when the user
; isn't an admin, instead of forcing a UAC prompt. Combined with
; PrivilegesRequiredOverridesAllowed=dialog, the wizard offers both choices.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile={#SourcePath}\..\..\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
