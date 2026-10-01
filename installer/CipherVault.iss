#define AppVersion "0.3.1"
[Setup]
AppId={{70AD8075-A9EB-4568-AF47-B32B8D187E52}
AppName=Cipher Vault
AppVersion={#AppVersion}
AppPublisher=Cipher Vault
DefaultDirName={localappdata}\Programs\Cipher Vault
DefaultGroupName=Cipher Vault
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installers
OutputBaseFilename=CipherVault-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\CipherVault.exe
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\windows-{#AppVersion}\CipherVault.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Getting Started.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Cipher Vault"; Filename: "{app}\CipherVault.exe"
Name: "{group}\Getting Started"; Filename: "{app}\Getting Started.txt"
Name: "{autodesktop}\Cipher Vault"; Filename: "{app}\CipherVault.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CipherVault.exe"; Description: "Open Cipher Vault"; Flags: nowait postinstall skipifsilent
