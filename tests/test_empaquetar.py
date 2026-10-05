"""
Tests de herramientas/empaquetar.py — las piezas del armado del instalador.

Nada de esto baja algo de internet ni toca el repo: todo pasa en tmp_path.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -v
"""

import hashlib
import io
import re
import zipfile
from pathlib import Path

import pytest

from herramientas import empaquetar


RAIZ = Path(__file__).resolve().parent.parent
ISS = RAIZ / "empaquetado" / "armonica.iss"


def test_las_descargas_fijadas_se_leen():
    descargas = empaquetar.leer_descargas()
    assert set(descargas) == {"python", "ffmpeg"}
    assert descargas["python"]["url"].startswith("https://www.python.org/")
    assert len(descargas["ffmpeg"]["sha256"]) == 64


def test_una_descarga_incompleta_es_un_error(tmp_path):
    ruta = tmp_path / "descargas.json"
    ruta.write_text('[{"nombre": "python", "url": "x"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="archivo"):
        empaquetar.leer_descargas(ruta)


def _descarga(contenido, sha256=None):
    return {"nombre": "x", "archivo": "x.zip", "url": "https://example.invalid/x.zip",
            "sha256": sha256 or hashlib.sha256(contenido).hexdigest()}


def test_bajar_verifica_el_sha256(tmp_path):
    contenido = b"contenido de prueba"
    destino = empaquetar.bajar(_descarga(contenido), tmp_path,
                               abrir=lambda url: io.BytesIO(contenido))
    assert destino.read_bytes() == contenido


def test_un_sha256_distinto_no_se_usa(tmp_path):
    with pytest.raises(ValueError, match="no coincide"):
        empaquetar.bajar(_descarga(b"bueno", sha256="0" * 64), tmp_path,
                         abrir=lambda url: io.BytesIO(b"bueno"))
    assert list(tmp_path.iterdir()) == []


def test_lo_ya_bajado_no_se_vuelve_a_bajar(tmp_path):
    contenido = b"ya estaba"
    (tmp_path / "x.zip").write_bytes(contenido)

    def no_bajar(url):
        raise AssertionError("no tenía que bajar")

    assert empaquetar.bajar(_descarga(contenido), tmp_path, abrir=no_bajar).read_bytes() == contenido


def test_los_archivos_de_la_app(tmp_path):
    for nombre in empaquetar.ARCHIVOS_SUELTOS:
        (tmp_path / nombre).write_text("x", encoding="utf-8")
    (tmp_path / "armonica" / "web").mkdir(parents=True)
    (tmp_path / "armonica" / "__pycache__").mkdir()
    (tmp_path / "armonica" / "servidor.py").write_text("x", encoding="utf-8")
    (tmp_path / "armonica" / "web" / "app.js").write_text("x", encoding="utf-8")
    (tmp_path / "armonica" / "__pycache__" / "servidor.cpython-314.pyc").write_bytes(b"x")
    (tmp_path / "main.py").write_text("x", encoding="utf-8")
    assert empaquetar.archivos_de_la_app(tmp_path) == [
        "config.py", "VERSION", "lanzador.pyw", "LICENSE",
        "armonica/servidor.py", "armonica/web/app.js"]


def test_sin_un_archivo_suelto_no_se_arma(tmp_path):
    (tmp_path / "armonica").mkdir()
    with pytest.raises(ValueError, match="config.py"):
        empaquetar.archivos_de_la_app(tmp_path)


def test_el_pth_del_python_embebido(tmp_path):
    empaquetar.escribir_pth(tmp_path)
    assert (tmp_path / "python314._pth").read_text(encoding="utf-8").splitlines() == [
        "python314.zip", ".", "Lib\\site-packages", "..\\app"]


def test_los_cambios_sin_commitear_que_irian_al_paquete():
    porcelain = (" M config.py\n"
                 "?? EVALUATION_2026-09-18.md\n"
                 " M armonica/servidor.py\n"
                 "R  viejo.py -> armonica/nuevo.py\n"
                 " M README.md\n")
    assert empaquetar.cambios_sin_commitear(porcelain) == [
        "config.py", "armonica/servidor.py", "armonica/nuevo.py"]


def test_de_ffmpeg_solo_el_ejecutable_y_su_licencia(tmp_path):
    zip_falso = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(zip_falso, "w") as z:
        z.writestr("ffmpeg-n8.1/bin/ffmpeg.exe", b"exe")
        z.writestr("ffmpeg-n8.1/bin/ffprobe.exe", b"otro")
        z.writestr("ffmpeg-n8.1/LICENSE.txt", b"LGPL")
        z.writestr("ffmpeg-n8.1/doc/ffmpeg.html", b"doc")
    empaquetar.extraer_ffmpeg(zip_falso, tmp_path / "ffmpeg", tmp_path / "licencias")
    assert sorted(p.name for p in (tmp_path / "ffmpeg").iterdir()) == ["ffmpeg.exe"]
    assert (tmp_path / "licencias" / "LICENSE.txt").read_bytes() == b"LGPL"


def test_un_zip_sin_ffmpeg_es_un_error(tmp_path):
    zip_falso = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(zip_falso, "w") as z:
        z.writestr("otra-cosa/LICENSE.txt", b"x")
    with pytest.raises(ValueError, match="ffmpeg.exe"):
        empaquetar.extraer_ffmpeg(zip_falso, tmp_path / "f", tmp_path / "l")


def test_las_licencias_de_cada_paquete(tmp_path):
    site = tmp_path / "site-packages"
    (site / "numpy-2.5.3.dist-info").mkdir(parents=True)
    (site / "numpy-2.5.3.dist-info" / "LICENSE.txt").write_text("BSD", encoding="utf-8")
    (site / "pi_heif-1.4.0.dist-info" / "licenses").mkdir(parents=True)
    (site / "pi_heif-1.4.0.dist-info" / "licenses" / "LICENSE.txt").write_text("LGPL", encoding="utf-8")
    (site / "mdurl-0.1.2.dist-info").mkdir()
    (site / "mdurl-0.1.2.dist-info" / "METADATA").write_text("x", encoding="utf-8")
    (site / "_sounddevice_data" / "portaudio-binaries").mkdir(parents=True)
    (site / "_sounddevice_data" / "portaudio-binaries" / "README.md").write_text("PA", encoding="utf-8")

    sin_licencia = empaquetar.copiar_licencias(site, tmp_path / "licencias")

    assert (tmp_path / "licencias" / "numpy" / "LICENSE.txt").read_text(encoding="utf-8") == "BSD"
    assert (tmp_path / "licencias" / "pi_heif" / "LICENSE.txt").read_text(encoding="utf-8") == "LGPL"
    assert (tmp_path / "licencias" / "portaudio" / "README.md").read_text(encoding="utf-8") == "PA"
    assert sin_licencia == ["mdurl"]


def test_los_requisitos_con_su_hash(tmp_path):
    fijados = empaquetar.leer_requisitos_in("# comentario\nnumpy==2.5.3\nmarkdown-it-py==4.2.0\n")
    assert fijados == {"numpy": ("numpy", "2.5.3"), "markdown-it-py": ("markdown-it-py", "4.2.0")}
    numpy = tmp_path / "numpy-2.5.3-cp314-cp314-win_amd64.whl"
    numpy.write_bytes(b"n")
    md = tmp_path / "markdown_it_py-4.2.0-py3-none-any.whl"
    md.write_bytes(b"m")

    texto = empaquetar.requisitos_con_hash([numpy, md], fijados)

    assert f"numpy==2.5.3 --hash=sha256:{hashlib.sha256(b'n').hexdigest()}" in texto
    assert f"markdown-it-py==4.2.0 --hash=sha256:{hashlib.sha256(b'm').hexdigest()}" in texto


def test_una_rueda_sin_fijar_es_un_error(tmp_path):
    fijados = empaquetar.leer_requisitos_in("numpy==2.5.3\n")
    numpy = tmp_path / "numpy-2.5.3-cp314-cp314-win_amd64.whl"
    numpy.write_bytes(b"n")
    colado = tmp_path / "colado-1.0-py3-none-any.whl"
    colado.write_bytes(b"c")
    with pytest.raises(ValueError, match="colado"):
        empaquetar.requisitos_con_hash([numpy, colado], fijados)
    with pytest.raises(ValueError, match="numpy"):
        empaquetar.requisitos_con_hash([], fijados)


def test_requisitos_in_mal_escrito():
    with pytest.raises(ValueError):
        empaquetar.leer_requisitos_in("numpy>=2\n")


def test_el_leeme_de_licencias_dice_de_donde_sale_ffmpeg():
    texto = empaquetar.texto_leeme_licencias(empaquetar.leer_descargas())
    assert "github.com/BtbN/FFmpeg-Builds" in texto
    assert "LGPL 3" in texto        # el LICENSE.txt de la compilación de BtbN es la v3
    assert "3.14.6" in texto
    # El código fuente exacto: la versión de BtbN y el commit de FFmpeg, sacados
    # del archivo fijado en descargas.json.
    assert "autobuild-2026-10-01-13-06" in texto
    assert "330caae0c1" in texto


def test_buscar_inno_setup(tmp_path):
    iscc = tmp_path / "Programs" / "Inno Setup 6" / "ISCC.exe"
    iscc.parent.mkdir(parents=True)
    iscc.write_bytes(b"")
    assert empaquetar.buscar_iscc({"LOCALAPPDATA": str(tmp_path)}) == iscc
    assert empaquetar.buscar_iscc({"LOCALAPPDATA": str(tmp_path / "nada")}) is None


def test_el_nombre_del_instalador():
    assert empaquetar.nombre_del_instalador("0.1.0") == "Armonica-0.1.0-instalador.exe"


def test_buscar_edge(tmp_path):
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    assert empaquetar.buscar_edge({"ProgramFiles(x86)": str(tmp_path)}) == edge
    assert empaquetar.buscar_edge({"EDGE": str(edge)}) == edge
    assert empaquetar.buscar_edge({"ProgramFiles(x86)": str(tmp_path / "nada")}) is None


def test_la_orden_que_imprime_la_guia(tmp_path):
    html = tmp_path / "web" / "guia.html"
    orden = empaquetar.orden_del_pdf(Path("C:/Edge/msedge.exe"), html, tmp_path / "g.pdf",
                                     tmp_path / "perfil")
    assert orden[0].endswith("msedge.exe")
    assert "--headless" in orden
    assert f"--print-to-pdf={tmp_path / 'g.pdf'}" in orden
    # Un perfil aparte: así no se engancha al Edge que Bruno tenga abierto.
    assert f"--user-data-dir={tmp_path / 'perfil'}" in orden
    assert "--no-pdf-header-footer" in orden
    assert orden[-1] == html.resolve().as_uri()


def entradas_de_la_seccion(texto, seccion):
    """Las líneas de una sección del .iss, sin comentarios ni vacías."""
    lineas, adentro = [], False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.startswith("[") and limpia.endswith("]"):
            adentro = limpia == f"[{seccion}]"
            continue
        if adentro and limpia and not limpia.startswith(";"):
            lineas.append(limpia)
    return lineas


def destinos_de_los_iconos(texto):
    return [re.match(r'Name: "([^"]+)"', linea).group(1)
            for linea in entradas_de_la_seccion(texto, "Icons")]


def test_los_iconos_para_abrir_la_app():
    """
    Escritorio sin preguntar (con la pregunta, Bruno lo destildó y después
    no encontraba cómo abrirla), Inicio, y uno en Documentos\\Armonica, al
    lado de sus frases y canciones.
    """
    texto = ISS.read_text(encoding="utf-8-sig")
    assert "[Tasks]" not in texto
    destinos = destinos_de_los_iconos(texto)
    for destino in ("{group}\\Armónica", "{autodesktop}\\Armónica",
                    "{userdocs}\\Armonica\\Abrir Armónica"):
        assert destino in destinos
    for linea in entradas_de_la_seccion(texto, "Icons"):
        assert "Tasks:" not in linea
        if "lanzador.pyw" in linea:
            assert 'Filename: "{app}\\python\\pythonw.exe"' in linea


def test_el_desinstalador_borra_la_clave_del_coach():
    texto = ISS.read_text(encoding="utf-8-sig")
    borrar = entradas_de_la_seccion(texto, "UninstallDelete")
    assert 'Type: files; Name: "{localappdata}\\Armonica\\coach.env"' in borrar
    assert 'Type: dirifempty; Name: "{localappdata}\\Armonica"' in borrar


def test_la_guia_esta_en_el_menu_inicio():
    texto = ISS.read_text(encoding="utf-8-sig")
    assert "{group}\\Guía de Armónica" in destinos_de_los_iconos(texto)
    guia = [linea for linea in entradas_de_la_seccion(texto, "Icons") if "Guía de Armónica" in linea]
    # El nombre sale del armado: si cambia allá, el ícono no se queda
    # apuntando a un PDF que ya no existe.
    assert f'Filename: "{{app}}\\{empaquetar.NOMBRE_DEL_PDF}"' in guia[0]
