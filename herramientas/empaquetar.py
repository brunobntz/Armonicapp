"""
empaquetar.py — Arma el instalador de Windows de Armónica, para el profe.

Lo corre Bruno en su máquina (herramientas\\empaquetar.ps1 lo llama con el
Python del .venv). Los pasos, en orden; cualquiera que falle corta todo:

    fijar        una vez, o al cambiar una versión: baja las ruedas de
                 empaquetado/requisitos.in y escribe requisitos.txt con el
                 SHA-256 de cada una. Se commitea.
    armar        toma el código commiteado (git archive HEAD), corre los
                 tests en esa copia, baja lo que falte verificando los
                 SHA-256 y arma el programa en empaquetado/_armado/Armonica.
    humo         abre ese programa como lo abre el acceso directo, con los
                 datos en una carpeta temporal y sin navegador, y lo cierra.
    instalador   compila empaquetado/armonica.iss con Inno Setup a dist/.

Sin argumentos hace armar, humo e instalador.

POR QUÉ git archive Y NO LA CARPETA: en la carpeta de trabajo están el
config.py con los valores de la máquina de Bruno y el .env con la clave del
coach. Al paquete va solo lo commiteado.
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMPAQUETADO = RAIZ / "empaquetado"
DESCARGAS = EMPAQUETADO / "_descargas"
RUEDAS = DESCARGAS / "ruedas"
ARMADO = EMPAQUETADO / "_armado" / "Armonica"
DIST = RAIZ / "dist"

# Lo que va a {app}\app además del paquete armonica.
ARCHIVOS_SUELTOS = ("config.py", "VERSION", "lanzador.pyw", "LICENSE")

# Con este archivo el Python embebido usa exactamente estas rutas y nada del
# sistema. ..\app es donde está el código (lo asume lanzador.CARPETA_PROGRAMA).
PTH = "python314._pth"
LINEAS_PTH = ("python314.zip", ".", "Lib\\site-packages", "..\\app")

# Las ruedas para el programa instalado: Windows de 64 bits, CPython 3.14,
# solo binarias (nada se compila en la máquina de Bruno).
OPCIONES_DE_RUEDAS = ["--only-binary=:all:", "--platform", "win_amd64",
                      "--python-version", "3.14", "--implementation", "cp"]


def sha256_de(ruta):
    hash_ = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            hash_.update(bloque)
    return hash_.hexdigest()


def leer_descargas(ruta=None):
    """Lo que se baja de afuera, con su SHA-256 fijo: {nombre: descarga}."""
    with open(ruta or EMPAQUETADO / "descargas.json", encoding="utf-8") as archivo:
        descargas = json.load(archivo)
    for descarga in descargas:
        faltan = {"nombre", "archivo", "url", "sha256"} - set(descarga)
        if faltan:
            raise ValueError(f"A la descarga {descarga.get('nombre', '?')} le falta: "
                             f"{', '.join(sorted(faltan))}.")
    return {descarga["nombre"]: descarga for descarga in descargas}


def bajar(descarga, carpeta=None, abrir=urllib.request.urlopen):
    """
    El archivo de `descarga`, en `carpeta`: el que ya estaba si su SHA-256
    es el fijado, si no se baja. Si lo bajado no coincide, se borra y es un
    error: nunca se usa algo distinto de lo fijado.
    """
    carpeta = Path(carpeta or DESCARGAS)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / descarga["archivo"]
    if destino.is_file() and sha256_de(destino) == descarga["sha256"]:
        return destino
    parcial = destino.with_name(destino.name + ".parcial")
    print(f"  Bajando {descarga['archivo']}...")
    with abrir(descarga["url"]) as respuesta, open(parcial, "wb") as archivo:
        shutil.copyfileobj(respuesta, archivo)
    obtenido = sha256_de(parcial)
    if obtenido != descarga["sha256"]:
        parcial.unlink()
        raise ValueError(f"{descarga['archivo']}: el SHA-256 no coincide (fijado "
                         f"{descarga['sha256']}, vino {obtenido}). No se usa.")
    os.replace(parcial, destino)
    return destino


def archivos_de_la_app(raiz):
    """Lo que va a {app}\\app: los sueltos y el paquete armonica, sin cachés."""
    raiz = Path(raiz)
    faltan = [nombre for nombre in ARCHIVOS_SUELTOS if not (raiz / nombre).is_file()]
    if faltan:
        raise ValueError(f"Faltan en el código: {', '.join(faltan)}.")
    archivos = list(ARCHIVOS_SUELTOS)
    for ruta in sorted((raiz / "armonica").rglob("*")):
        if ruta.is_file() and "__pycache__" not in ruta.parts and ruta.suffix != ".pyc":
            archivos.append(ruta.relative_to(raiz).as_posix())
    return archivos


def escribir_pth(carpeta_python):
    (Path(carpeta_python) / PTH).write_text("\n".join(LINEAS_PTH) + "\n", encoding="utf-8")


def cambios_sin_commitear(porcelain):
    """De `git status --porcelain`, los archivos que irían al paquete."""
    cambiados = []
    for linea in porcelain.splitlines():
        ruta = linea[3:].strip().strip('"')
        if " -> " in ruta:
            ruta = ruta.split(" -> ", 1)[1]
        if ruta in ARCHIVOS_SUELTOS or ruta.startswith("armonica/"):
            cambiados.append(ruta)
    return cambiados


def extraer_ffmpeg(zip_ffmpeg, carpeta_ffmpeg, carpeta_licencia):
    """Del zip de BtbN, solo bin/ffmpeg.exe y su LICENSE.txt."""
    carpeta_ffmpeg = Path(carpeta_ffmpeg)
    carpeta_licencia = Path(carpeta_licencia)
    encontrados = set()
    with zipfile.ZipFile(zip_ffmpeg) as zip_:
        for nombre in zip_.namelist():
            partes = nombre.split("/")
            if partes[-2:] == ["bin", "ffmpeg.exe"]:
                carpeta_ffmpeg.mkdir(parents=True, exist_ok=True)
                (carpeta_ffmpeg / "ffmpeg.exe").write_bytes(zip_.read(nombre))
                encontrados.add("ffmpeg.exe")
            elif len(partes) == 2 and partes[1] == "LICENSE.txt":
                carpeta_licencia.mkdir(parents=True, exist_ok=True)
                (carpeta_licencia / "LICENSE.txt").write_bytes(zip_.read(nombre))
                encontrados.add("LICENSE.txt")
    faltan = {"ffmpeg.exe", "LICENSE.txt"} - encontrados
    if faltan:
        raise ValueError(f"El zip de ffmpeg no trae: {', '.join(sorted(faltan))}.")


def copiar_licencias(site_packages, destino):
    """
    Las licencias de cada paquete instalado (lo que trae su .dist-info) a
    destino/<paquete>/, más el README de PortAudio, que viaja adentro de
    sounddevice y es la licencia de esa biblioteca. Devuelve los paquetes
    que no traían ninguna, para avisar.
    """
    site_packages = Path(site_packages)
    destino = Path(destino)
    sin_licencia = []
    for info in sorted(site_packages.glob("*.dist-info")):
        paquete = info.name[: -len(".dist-info")].rsplit("-", 1)[0]
        copiadas = 0
        for archivo in sorted(info.rglob("*")):
            relativo = archivo.relative_to(info)
            es_licencia = (relativo.parts[0] == "licenses" or archivo.name.upper().startswith(
                ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")))
            if not archivo.is_file() or not es_licencia:
                continue
            if relativo.parts[0] == "licenses":
                relativo = Path(*relativo.parts[1:])
            final = destino / paquete / relativo
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archivo, final)
            copiadas += 1
        if not copiadas:
            sin_licencia.append(paquete)
    portaudio = site_packages / "_sounddevice_data" / "portaudio-binaries" / "README.md"
    if portaudio.is_file():
        (destino / "portaudio").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(portaudio, destino / "portaudio" / "README.md")
    return sin_licencia


def nombre_canonico(nombre):
    return re.sub(r"[-_.]+", "-", nombre).lower()


def leer_requisitos_in(texto):
    """{nombre canónico: (nombre, versión)}: una línea nombre==versión por paquete."""
    fijados = {}
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        nombre, separador, version = linea.partition("==")
        if not separador or not nombre.strip() or not version.strip():
            raise ValueError(f"En requisitos.in cada línea es nombre==versión: {linea!r}")
        fijados[nombre_canonico(nombre.strip())] = (nombre.strip(), version.strip())
    return fijados


def requisitos_con_hash(ruedas, fijados):
    """
    El texto de requisitos.txt: cada paquete fijado con el SHA-256 de su
    rueda. Una rueda que no está fijada (una dependencia nueva) o un paquete
    fijado sin su rueda es un error: lo que entra al paquete se elige a mano.
    """
    con_hash = {}
    for rueda in ruedas:
        rueda = Path(rueda)
        nombre, version = rueda.name.split("-")[:2]
        canonico = nombre_canonico(nombre)
        if canonico not in fijados:
            raise ValueError(f"pip trajo {rueda.name}, que no está en requisitos.in: fijalo a mano.")
        if fijados[canonico][1] != version:
            raise ValueError(f"{rueda.name} no es la versión fijada ({fijados[canonico][1]}).")
        con_hash[canonico] = sha256_de(rueda)
    faltan = sorted(set(fijados) - set(con_hash))
    if faltan:
        raise ValueError(f"Sin rueda para Windows y Python 3.14: {', '.join(faltan)}.")
    lineas = ["# Generado por `python -m herramientas.empaquetar fijar`: no editar a mano."]
    for canonico in sorted(con_hash):
        nombre, version = fijados[canonico]
        lineas.append(f"{nombre}=={version} --hash=sha256:{con_hash[canonico]}")
    return "\n".join(lineas) + "\n"


def texto_leeme_licencias(descargas):
    """licencias\\LEEME.txt: qué hay adentro y de dónde sale cada cosa."""
    ffmpeg = descargas["ffmpeg"]
    python = descargas["python"]
    version_python = re.search(r"python-([\d.]+)-embed", python["archivo"]).group(1)
    return (
        "Armónica viene con estas piezas, cada una con su licencia en esta carpeta.\n\n"
        "Armónica (MIT): Armonica\\LICENSE\n"
        f"Python {version_python} embebido (PSF): Python\\LICENSE.txt\n"
        f"  {python['url']}\n"
        "Paquetes de Python: una carpeta por paquete, con lo que trae cada uno.\n"
        "PortAudio (lo usa sounddevice): portaudio\\README.md\n"
        "ffmpeg (LGPL 2.1 o posterior), compilado por BtbN/FFmpeg-Builds: ffmpeg\\LICENSE.txt\n"
        f"  binario: {ffmpeg['url']}\n"
        "  código fuente de FFmpeg: https://git.ffmpeg.org/ffmpeg.git\n"
        "  scripts con que se compiló: https://github.com/BtbN/FFmpeg-Builds\n"
    )


def buscar_iscc(entorno=None):
    """El compilador de Inno Setup, o None si no está instalado."""
    entorno = os.environ if entorno is None else entorno
    candidatos = []
    if entorno.get("ISCC"):
        candidatos.append(Path(entorno["ISCC"]))
    if entorno.get("LOCALAPPDATA"):
        candidatos.append(Path(entorno["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        if entorno.get(variable):
            candidatos.append(Path(entorno[variable]) / "Inno Setup 6" / "ISCC.exe")
    return next((candidato for candidato in candidatos if candidato.is_file()), None)


def nombre_del_instalador(version):
    return f"Armonica-{version}-instalador.exe"


def _pip(*argumentos):
    """pip del .venv: el mismo Python 3.14 que el embebido."""
    subprocess.run([sys.executable, "-m", "pip", *argumentos], check=True)


def fijar():
    """
    Baja las ruedas de requisitos.in para Windows y Python 3.14, con sus
    dependencias, y escribe requisitos.txt con el SHA-256 de cada una. Si pip
    trae algo que no está en requisitos.in, corta: hay que fijarlo a mano.
    """
    requisitos_in = EMPAQUETADO / "requisitos.in"
    fijados = leer_requisitos_in(requisitos_in.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="armonica-ruedas-") as temporal:
        _pip("download", "-r", str(requisitos_in), "-d", temporal, *OPCIONES_DE_RUEDAS)
        ruedas = sorted(Path(temporal).glob("*.whl"))
        texto = requisitos_con_hash(ruedas, fijados)
        if RUEDAS.exists():
            shutil.rmtree(RUEDAS)
        RUEDAS.mkdir(parents=True)
        for rueda in ruedas:
            shutil.copy2(rueda, RUEDAS / rueda.name)
    destino = EMPAQUETADO / "requisitos.txt"
    destino.write_text(texto, encoding="utf-8")
    print(f"  Fijadas {len(fijados)} ruedas en {destino.relative_to(RAIZ)}. Commitealo.")
    return destino


def avisar_cambios():
    """Lo que está cambiado sin commitear no entra: se avisa y se sigue."""
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ, check=True,
                               capture_output=True, text=True).stdout
    for ruta in cambios_sin_commitear(porcelain):
        print(f"  Aviso: {ruta} tiene cambios sin commitear: no entran al paquete.")


def copiar_commiteado(destino):
    """El código de HEAD, tal cual está commiteado, en `destino`."""
    archivo = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=RAIZ,
                             check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archivo)) as tar:
        tar.extractall(destino, filter="data")


def correr_tests(codigo):
    """Los tests en la copia commiteada. Si fallan, no se arma nada."""
    print("  Corriendo los tests sobre lo commiteado...")
    resultado = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                               cwd=codigo)
    if resultado.returncode != 0:
        raise SystemExit("Los tests fallan sobre lo commiteado: no se arma.")


def armar():
    """
    El programa en empaquetado/_armado/Armonica, con el layout que espera
    el lanzador. Devuelve la versión.
    """
    avisar_cambios()
    with tempfile.TemporaryDirectory(prefix="armonica-armado-") as temporal:
        codigo = Path(temporal) / "codigo"
        copiar_commiteado(codigo)
        # Lo fijado también se lee de lo commiteado: un descargas.json o un
        # requisitos.txt editado y sin commitear (justo después de `fijar`)
        # no puede cambiar en silencio qué se baja y qué entra al paquete.
        # RUEDAS, en la carpeta de trabajo, es solo un caché: pip verifica
        # cada rueda contra los hashes de requisitos.txt.
        descargas = leer_descargas(codigo / "empaquetado" / "descargas.json")
        correr_tests(codigo)
        zip_python = bajar(descargas["python"])
        zip_ffmpeg = bajar(descargas["ffmpeg"])
        requisitos = codigo / "empaquetado" / "requisitos.txt"
        _pip("download", "--require-hashes", "-r", str(requisitos), "-d", str(RUEDAS),
             *OPCIONES_DE_RUEDAS)

        if ARMADO.exists():
            shutil.rmtree(ARMADO)
        python = ARMADO / "python"
        with zipfile.ZipFile(zip_python) as zip_:
            zip_.extractall(python)
        escribir_pth(python)
        site_packages = python / "Lib" / "site-packages"
        _pip("install", "--no-index", "--find-links", str(RUEDAS), "--require-hashes",
             "-r", str(requisitos), "--target", str(site_packages))

        for relativo in archivos_de_la_app(codigo):
            final = ARMADO / "app" / relativo
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(codigo / relativo, final)
        shutil.copyfile(codigo / "Armonica.ico", ARMADO / "Armonica.ico")

        licencias = ARMADO / "licencias"
        extraer_ffmpeg(zip_ffmpeg, ARMADO / "ffmpeg", licencias / "ffmpeg")
        (licencias / "Armonica").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(codigo / "LICENSE", licencias / "Armonica" / "LICENSE")
        (licencias / "Python").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(python / "LICENSE.txt", licencias / "Python" / "LICENSE.txt")
        for paquete in copiar_licencias(site_packages, licencias):
            print(f"  Aviso: {paquete} no trae archivo de licencia en su .dist-info.")
        (licencias / "LEEME.txt").write_text(texto_leeme_licencias(descargas), encoding="utf-8")

        version = (codigo / "VERSION").read_text(encoding="utf-8").strip()
    print(f"  Armado {version} en {ARMADO.relative_to(RAIZ)}.")
    return version


# Lo que el programa armado tiene que poder importar y encontrar. audio.hay_ffmpeg()
# solo mira si hay algún ffmpeg en el PATH, y en la máquina de Bruno hay uno
# instalado aparte: por eso se comprueba además que el que se encuentra es el
# del paquete (la carpeta esperada llega en ARMONICA_FFMPEG_ESPERADO) y que corre.
CHEQUEO_DE_BIBLIOTECAS = (
    "import os, shutil, subprocess; "
    "import numpy, sounddevice, rich, pypdf; "
    "from armonica import audio, imagenes; "
    "assert imagenes.hay_soporte_heic(), 'falta el soporte de fotos HEIC'; "
    "assert audio.hay_ffmpeg(), 'falta ffmpeg'; "
    "esperado = os.path.normcase(os.environ['ARMONICA_FFMPEG_ESPERADO']); "
    "usado = shutil.which('ffmpeg'); "
    "assert usado and os.path.normcase(os.path.dirname(usado)) == esperado, "
    "'se usa otro ffmpeg que el del paquete: ' + str(usado); "
    "assert subprocess.run(['ffmpeg', '-version'], capture_output=True, "
    "creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).returncode == 0, "
    "'el ffmpeg del paquete no corre'; "
    "print('  Bibliotecas: ok')"
)


def _traer_json(url):
    with urllib.request.urlopen(url, timeout=15) as respuesta:
        return json.loads(respuesta.read())


def _mandar_json(url, cuerpo):
    pedido = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=15) as respuesta:
        return json.loads(respuesta.read())


def humo(programa=None, espera=30.0):
    """
    Abre el programa armado (o instalado) como lo abre el acceso directo
    (pythonw + lanzador.pyw), con los datos en una carpeta temporal y sin
    navegador; verifica que conteste como la versión instalada y lo cierra
    con /api/apagar, el botón de Ajustes. Prende el micrófono un momento.
    """
    from armonica import lanzador

    programa = Path(programa or ARMADO).resolve()
    if lanzador.buscar_instancia() is not None:
        raise SystemExit("Hay una Armónica abierta (puertos 8000 a 8010): cerrala antes de la prueba.")
    version = (programa / "app" / "VERSION").read_text(encoding="utf-8").strip()

    with tempfile.TemporaryDirectory(prefix="armonica-humo-") as temporal:
        # Con el PATH mínimo (la carpeta de ffmpeg del paquete y System32), no
        # puede aparecer otro ffmpeg del sistema que tape uno faltante o roto.
        # Sin bytecode: el python armado no ensucia app\ con __pycache__ en la
        # carpeta que después empaqueta Inno Setup.
        ffmpeg = programa / "ffmpeg"
        sistema = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        entorno = dict(os.environ, PATH=str(ffmpeg) + os.pathsep + sistema,
                       ARMONICA_FFMPEG_ESPERADO=str(ffmpeg), PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([str(programa / "python" / "python.exe"), "-c", CHEQUEO_DE_BIBLIOTECAS],
                       cwd=temporal, env=entorno, check=True)

        datos = Path(temporal) / "Armonica"
        entorno_app = dict(os.environ, ARMONICA_DATOS=str(datos), ARMONICA_SIN_NAVEGADOR="1",
                           PYTHONDONTWRITEBYTECODE="1")
        proceso = subprocess.Popen([str(programa / "python" / "pythonw.exe"),
                                    str(programa / "app" / "lanzador.pyw")],
                                   cwd=str(programa / "app"), env=entorno_app)
        try:
            puerto = lanzador.esperar_instancia(espera=espera)
            if puerto is None:
                raise SystemExit("La app armada no contestó /api/hola.")
            base = f"http://127.0.0.1:{puerto}"
            inicio = _traer_json(base + "/api/inicio")
            if inicio.get("empaquetada") is not True or inicio.get("version") != version:
                raise SystemExit(f"La app armada no se presenta bien: empaquetada="
                                 f"{inicio.get('empaquetada')}, version={inicio.get('version')}.")
            if not _traer_json(base + "/api/canciones").get("ok"):
                raise SystemExit("La app armada no pudo listar las canciones.")
            if not (datos / "registro.txt").is_file():
                raise SystemExit("La app armada no escribió registro.txt.")
            if not _mandar_json(base + "/api/apagar", {}).get("ok"):
                raise SystemExit("La app armada no aceptó cerrarse.")
            proceso.wait(timeout=15)
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait()
    print(f"  Prueba de humo de {version}: ok.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Arma el instalador de Windows de Armónica.")
    parser.add_argument("paso", nargs="?", default="todo",
                        choices=["fijar", "armar", "humo", "instalador", "todo"])
    parser.add_argument("--programa", default=None,
                        help="la carpeta del programa para `humo` (por defecto, la armada)")
    argumentos = parser.parse_args(argv)
    if argumentos.paso == "fijar":
        fijar()
        return 0
    if argumentos.paso == "armar":
        armar()
        return 0
    if argumentos.paso == "humo":
        humo(argumentos.programa)
        return 0
    raise SystemExit(f"El paso {argumentos.paso} todavía no está.")


if __name__ == "__main__":
    sys.exit(main())
