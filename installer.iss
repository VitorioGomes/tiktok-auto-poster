#define AppName "TikTok Auto Poster"
#define AppVersion "1.4"
#define AppExe "TikTokAutoPoster.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Bot TikTok
DefaultDirName={userdocs}\TikTokAutoPoster
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=Setup_TikTokAutoPoster
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion


[Dirs]
Name: "{app}\Nicho 1"
Name: "{app}\Nicho 1\conta1"
Name: "{app}\Nicho 1\conta2"
Name: "{app}\Nicho 1\conta3"
Name: "{app}\Nicho 1\conta4"
Name: "{app}\Nicho 1\conta5"
Name: "{app}\Nicho 1\postados"
Name: "{app}\Nicho 2"
Name: "{app}\Nicho 2\conta1"
Name: "{app}\Nicho 2\conta2"
Name: "{app}\Nicho 2\conta3"
Name: "{app}\Nicho 2\conta4"
Name: "{app}\Nicho 2\conta5"
Name: "{app}\Nicho 2\postados"

[Icons]
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName} agora"; Flags: nowait postinstall skipifsilent
