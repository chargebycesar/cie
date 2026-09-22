; Instalador de Boletines IRVE. Se construye con empaquetar\construir.ps1,
; que es quien pasa VersionApp, CarpetaApp y CarpetaSalida.

#ifndef VersionApp
  #define VersionApp "1.0.0"
#endif
#ifndef CarpetaApp
  #define CarpetaApp "trabajo\app"
#endif
#ifndef CarpetaSalida
  #define CarpetaSalida "salida"
#endif

[Setup]
AppId={{9C4E1F2A-5B7D-4E11-9E3C-BOLETINESIRVE}
AppName=Boletines IRVE
AppVersion={#VersionApp}
AppPublisher=Bufala Tech SL
DefaultDirName={autopf}\Boletines IRVE
DefaultGroupName=Boletines IRVE
DisableProgramGroupPage=yes
OutputDir={#CarpetaSalida}
OutputBaseFilename=BoletinesIRVE-{#VersionApp}-instalador
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; El programa entero, con su propio Python dentro
Source: "{#CarpetaApp}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Los expedientes se guardan en Documentos, no dentro de Archivos de programa
Name: "{userdocs}\Boletines IRVE"

[Icons]
Name: "{group}\Boletines IRVE"; Filename: "{app}\Boletines IRVE.bat"; \
      IconFilename: "{app}\web\icono.ico"; WorkingDir: "{app}"
Name: "{userdesktop}\Boletines IRVE"; Filename: "{app}\Boletines IRVE.bat"; \
      IconFilename: "{app}\web\icono.ico"; WorkingDir: "{app}"; Tasks: escritorio

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; \
      GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\Boletines IRVE.bat"; Description: "Abrir Boletines IRVE"; \
          Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
; La carpeta de expedientes NO se borra al desinstalar: son documentos del usuario
Type: filesandordirs; Name: "{app}\__pycache__"
