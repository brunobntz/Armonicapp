; armonica.iss — El instalador de Windows de Armónica, para el profe.
;
; Lo compila `python -m herramientas.empaquetar instalador`, que pasa:
;   /DVersion=0.1.0  /DArmado=<empaquetado\_armado\Armonica>
;   /DEjemplos=<empaquetado\ejemplos>  /O<dist>
;
; Instalación por usuario, sin pedir administrador, en
; %LOCALAPPDATA%\Programs\Armonica. Los datos del profe van a
; Documentos\Armonica: ni una versión nueva ni el desinstalador los tocan.

#ifndef Version
  #error Falta /DVersion
#endif
#ifndef Armado
  #error Falta /DArmado
#endif
#ifndef Ejemplos
  #define Ejemplos "ejemplos"
#endif

[Setup]
; El AppId no cambia nunca: así una versión nueva se instala encima.
AppId={{DE843E22-3123-424E-AFFC-A46A5622326D}
AppName=Armónica
AppVersion={#Version}
AppPublisher=Bruno
DefaultDirName={autopf}\Armonica
DefaultGroupName=Armónica
DisableProgramGroupPage=yes
; La carpeta es fija (instalación por usuario): sin pantalla para elegirla,
; así el profe no puede apuntar el programa a Documentos ni al Escritorio.
DisableDirPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=Armonica-{#Version}-instalador
SetupIconFile={#Armado}\Armonica.ico
UninstallDisplayIcon={app}\Armonica.ico
UninstallDisplayName=Armónica
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; La app la cierra el código de abajo: con pythonw no hay ventana, y el
; cierre de aplicaciones de Windows no la ve.
CloseApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Poner un ícono en el escritorio"

[Files]
Source: "{#Armado}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Los ejemplos que eligió Bruno: solo si el profe no tiene ya un archivo con
; ese nombre, y el desinstalador no los borra.
Source: "{#Ejemplos}\*"; DestDir: "{userdocs}\Armonica"; Flags: recursesubdirs createallsubdirs onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist

[Icons]
Name: "{group}\Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"
Name: "{autodesktop}\Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"; Tasks: escritorio

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; Description: "Abrir Armónica"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Las cachés que Python escribe al usar la app (__pycache__) viven en app\
; y en python\. Se borran solo esas dos carpetas, nunca {app} entera y
; recursiva: los datos del profe están en Documentos\Armonica, fuera de
; {app}, y el desinstalador no los toca.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"
Type: dirifempty; Name: "{app}"

[Code]
const
  PrimerPuerto = 8000;
  UltimoPuerto = 8010;

{ Cierra Armónica si está abierta: pregunta /api/hola en cada puerto y, si
  contesta, le pide /api/apagar, el mismo botón de Ajustes. Devuelve '' si
  quedó cerrada (o no estaba), o el motivo para mostrar si no se pudo. }
function CerrarLaApp(): String;
var
  Puerto: Integer;
  Pedido: Variant;
  Respuesta: String;
begin
  Result := '';
  { El lanzador tiene el mutex Local\Armonica-lanzador mientras vive su app: si
    no existe, no hay app abierta y no hay nada que cerrar. Sin esta salida se
    probarían los 11 puertos, y cada uno cerrado tarda unos 2 segundos en
    fallar: unos 22 segundos en pantalla sin que parezca pasar nada. }
  if not CheckForMutexes('Local\Armonica-lanzador') then
    Exit;
  for Puerto := PrimerPuerto to UltimoPuerto do
  begin
    try
      Pedido := CreateOleObject('WinHttp.WinHttpRequest.5.1');
      Pedido.SetTimeouts(300, 300, 1000, 1000);
      Pedido.Open('GET', 'http://127.0.0.1:' + IntToStr(Puerto) + '/api/hola', False);
      Pedido.Send('');
      Respuesta := Pedido.ResponseText;
      if (Pedido.Status = 200) and (Pos('"armonica"', Respuesta) > 0) then
      begin
        Pedido := CreateOleObject('WinHttp.WinHttpRequest.5.1');
        Pedido.SetTimeouts(300, 300, 3000, 3000);
        Pedido.Open('POST', 'http://127.0.0.1:' + IntToStr(Puerto) + '/api/apagar', False);
        Pedido.SetRequestHeader('Content-Type', 'application/json');
        Pedido.Send('{}');
        Respuesta := Pedido.ResponseText;
        if Pos('"ok": true', Respuesta) > 0 then
          Sleep(2000)
        else
          Result := 'Armónica está grabando. Pará la grabación, cerrala desde Ajustes y volvé a abrir este programa.';
        { Hay una sola app: se cierre o no, no se siguen probando los otros puertos. }
        Exit;
      end;
    except
      { Nada escuchando en ese puerto, u otro programa: se sigue. }
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := CerrarLaApp();
end;

function InitializeUninstall(): Boolean;
var
  Motivo: String;
begin
  Motivo := CerrarLaApp();
  Result := Motivo = '';
  if not Result then
    MsgBox(Motivo, mbError, MB_OK);
end;
