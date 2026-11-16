; Inno Setup 6 script for the Digital Rain installer.
; Built by build.ps1, which passes the version in: ISCC /DAppVersion=1.0.0 DigitalRain.iss
; Writes DigitalRain-Setup.exe to the repository root.
;
; Per-user install, no admin. The folder is the one tools\build\install.ps1 and the docs use.
; The uninstaller removes the program folder and leaves the settings in %APPDATA%\MatrixRain.

#ifndef AppVersion
  #error Pass the version in: ISCC /DAppVersion=x.y.z DigitalRain.iss
#endif

#define AppName "Digital Rain"
#define Scr "MatrixRain.scr"

[Setup]
; Stable id: every release upgrades the previous install in place. Never change it.
AppId={{6F0C7E2A-3B54-4D1B-9A7E-5C2D8E41B6A3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=phabzlabs
AppPublisherURL=https://github.com/phabzlabs/digital-rain
AppSupportURL=https://github.com/phabzlabs/digital-rain/issues
AppUpdatesURL=https://github.com/phabzlabs/digital-rain/releases
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\MatrixRain
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
UsePreviousAppDir=no
; GPL v3 needs no acceptance, so a short notice instead of an "I accept" page.
InfoBeforeFile=notice.txt
SetupIconFile=..\..\icon.ico
UninstallDisplayIcon={app}\{#Scr}
UninstallDisplayName={#AppName}
OutputDir=..\..
OutputBaseFilename=DigitalRain-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Close a running saver or preview from this folder (Restart Manager) instead of failing on locked files.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\dist\MatrixRain\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[UninstallDelete]
; Anything the saver wrote beside itself (caches). Settings live in %APPDATA%\MatrixRain and stay.
Type: filesandordirs; Name: "{app}"

[Run]
; Set Digital Rain as the screensaver: the same picker as right-click Install on the .scr.
; Checked by default, never run in a silent install.
; No quotes round the path: Windows' own Install verb passes it bare, and desk.cpl stores
; a quoted path as is, which leaves the picker blank.
Filename: "{sys}\rundll32.exe"; Parameters: "desk.cpl,InstallScreenSaver {app}\{#Scr}"; Description: "Set Digital Rain as my screensaver"; Flags: postinstall nowait skipifsilent

[Code]
// Windows Defender scans freshly written libraries the first time they load, which made the
// first launch after an install take seconds. --warm-up loads them once, hidden, for about a
// second. Exec starts the .scr directly (ShellExecute on a .scr would add /S and drop the arguments).
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Warming up Digital Rain...';
    if not Exec(ExpandConstant('{app}\{#Scr}'), '--warm-up', ExpandConstant('{app}'),
                SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Log('Warm-up did not start: ' + SysErrorMessage(ResultCode))
    else
      Log('Warm-up exit code ' + IntToStr(ResultCode));
  end;
end;

// Uninstall: if Windows still has Digital Rain as the screensaver, clear the setting so it does
// not point at a deleted file. desk.cpl may store the long or the 8.3 short path.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Saver: String;
begin
  if CurUninstallStep = usUninstall then
    if RegQueryStringValue(HKCU, 'Control Panel\Desktop', 'SCRNSAVE.EXE', Saver) then
    begin
      Saver := Uppercase(RemoveQuotes(Saver));
      if (Pos('\MATRIXRAIN.SCR', Saver) > 0) or (Pos('\MATRIX~1.SCR', Saver) > 0) then
      begin
        RegDeleteValue(HKCU, 'Control Panel\Desktop', 'SCRNSAVE.EXE');
        Log('Cleared the screensaver setting: ' + Saver);
      end;
    end;
end;
