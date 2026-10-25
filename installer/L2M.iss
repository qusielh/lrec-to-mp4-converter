; ---------------------------------------------------------------------------
; L2M (free edition) - Inno Setup script
;
; Builds L2M_Setup.exe, a single installer that ships the self-contained
; one-file L2M.exe. No Python is required on the user's PC: everything
; (engine, UI, ffmpeg, tsdecode) is already inside the exe. The only optional
; prerequisite is WebView2; the installer offers Microsoft's download page if
; it is missing.
;
; Compile with:  iscc installer\L2M.iss
; Output:        dist\installer\L2M_Setup.exe
; ---------------------------------------------------------------------------

#define AppName        "L2M"
#define AppVersion     "1.1.0"
#define AppPublisher   "Qusie"
#define AppExeName     "L2M.exe"
#define SourceExe      "..\dist\L2M.exe"
#define WebView2Url    "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

[Setup]
AppId={{8F3B2C41-2E9A-4A55-9C7D-7B4A11E2C001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/qusielh/lrec-to-mp4-converter
AppSupportURL=https://github.com/qusielh/lrec-to-mp4-converter/issues
AppUpdatesURL=https://github.com/qusielh/lrec-to-mp4-converter/releases
AppCopyright=Copyright (C) 2026 Qusie
AppComments=L2M - Linktivity recording (.lrec) to MP4 converter
VersionInfoVersion=1.1.0.0
VersionInfoCompany=Qusie
VersionInfoDescription=L2M Setup
VersionInfoCopyright=Copyright (C) 2026 Qusie
VersionInfoProductName=L2M
VersionInfoProductVersion=1.1.0.0
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=L2M_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\l2m.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\l2m.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\l2m.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\l2m.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WEBVIEW2_GUID = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function WebView2Installed(): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WEBVIEW2_GUID, 'pv', Version) or
    RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WEBVIEW2_GUID, 'pv', Version) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WEBVIEW2_GUID, 'pv', Version);
  if Result then
    Result := (Version <> '') and (Version <> '0.0.0.0');
end;

procedure InstallWebView2();
var
  ResultCode: Integer;
begin
  if WebView2Installed() then
    exit;
  if MsgBox('L2M needs the Microsoft WebView2 Runtime, which is missing on this PC.' + #13#10 + #13#10 +
            'Download and install it now? (You need an internet connection.)',
            mbConfirmation, MB_YESNO) = IDYES then
  begin
    ShellExec('open', '{#WebView2Url}', '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
  end;
end;

procedure InitializeWizard();
begin
  InstallWebView2();
end;
