"""
Tests de armonica/clases.py — leer los apuntes de las clases.

Todos los recaps de acá son INVENTADOS. Tienen la misma forma que los que
manda un profesor real (el recap automático de una reunión), pero ningún
contenido real: el material de clase es de un tercero y no va al repo.
"""

import inspect
import os
import zipfile

import pytest

from armonica import clases


RECAP = """# Clase 2026-03-04

**Profesor:** Alguien · **Duración:** 50 min

## Propósito de la reunión

Revisar el ejercicio de la semana.

## Puntos clave

- **La escala de dos octavas:** salió entera, con el bend del 3 un poco corto.
- **El cambio de acorde:** llega tarde al compás 5; hay que anticipar.

## Temas

### La escala

- Se tocó en 2a posición.

### El cambio

- Anticipar un compás.

## Próximos pasos

- **Ana:** practicar el bend del 3 hasta que quede afinado.
- **Ana:** tocar la frase sobre la pista a 70 BPM, anticipando el compás 5.
- **Profe:** mandar la pista nueva.
- **Ana:** mirar la pentatónica mayor en primera posición para el contraste.
"""

SIN_RECAP = """# Clase 2026-03-11 — sin recap

No hay recap de esta clase. Existió, pero no quedó registro.
"""

PROSA = """Hoy vimos el bend del 2. Me sale bajo. Practicar despacio con el afinador.
"""


@pytest.fixture
def carpeta(tmp_path):
    (tmp_path / "2026-03-04.md").write_text(RECAP, encoding="utf-8")
    (tmp_path / "2026-03-11.md").write_text(SIN_RECAP, encoding="utf-8")
    (tmp_path / "2026-02-25.txt").write_text(PROSA, encoding="utf-8")
    (tmp_path / "LEEME.md").write_text("no soy una clase", encoding="utf-8")
    (tmp_path / "aprendizaje.md").write_text("# Síntesis\n\nLo que sale de leerlas juntas.",
                                             encoding="utf-8")
    return str(tmp_path)


# =============================================================================
# La garantia mas importante: este modulo NO ESCRIBE
# =============================================================================

def test_el_modulo_no_tiene_ninguna_apertura_en_modo_escritura():
    """
    La carpeta de clases puede ser el cuaderno personal de alguien, o el de
    su asistente. La app la lee y no la toca. Este test lee el código fuente
    del módulo y falla si aparece cualquier apertura para escribir.
    """
    import re
    fuente = inspect.getsource(clases)

    # Toda apertura de archivo del modulo tiene que ser para leer.
    for apertura in re.findall(r"open\(([^)]*)\)", fuente):
        assert not re.search(r"""["'][wax]""", apertura), \
            f"el modulo de clases no puede escribir: open({apertura})"
    assert 'zipfile.ZipFile(ruta, "w"' not in fuente

    for marca in ("os.remove", "os.rename", "os.unlink", "shutil", "makedirs",
                  "write_text", "write_bytes", "rmtree", "os.rmdir"):
        assert marca not in fuente, f"el modulo de clases no puede escribir: aparece {marca!r}"


# =============================================================================
# Leer y entender
# =============================================================================

def test_lista_las_clases_por_fecha_y_saltea_lo_que_no_es_clase(carpeta):
    lista = clases.listar(carpeta)
    assert [c.archivo for c in lista] == ["2026-02-25.txt", "2026-03-04.md", "2026-03-11.md"]


def test_entiende_un_recap_con_secciones(carpeta):
    clase = next(c for c in clases.listar(carpeta) if c.fecha == "2026-03-04")

    assert clase.titulo == "Clase 2026-03-04"
    assert clase.con_recap is True
    assert clase.puntos_clave == [
        "La escala de dos octavas: salió entera, con el bend del 3 un poco corto.",
        "El cambio de acorde: llega tarde al compás 5; hay que anticipar.",
    ]
    assert clase.temas == ["La escala", "El cambio"]
    assert clase.proximos_pasos[0] == {"para": "Ana",
                                       "texto": "practicar el bend del 3 hasta que quede afinado."}
    assert clase.proximos_pasos[2]["para"] == "Profe"


def test_los_pasos_anidados_por_persona_salen_uno_por_tarea(tmp_path):
    """
    La otra forma en que vienen los próximos pasos: el nombre solo, y las
    tareas debajo con sangría. Tiene que dar un paso por tarea, todos a
    nombre de esa persona, sin el guion pegado adelante.
    """
    (tmp_path / "2026-05-01.md").write_text(
        "# Clase\n\n## Próximos pasos\n\n- **Ana:**\n  - Practicar la escala.\n"
        "  - Tocar sobre la pista, anticipando\n    el compás 5.\n- **Profe:**\n  - Mandar la pista.\n",
        encoding="utf-8")

    pasos = clases.listar(str(tmp_path))[0].proximos_pasos

    assert pasos == [
        {"para": "Ana", "texto": "Practicar la escala."},
        {"para": "Ana", "texto": "Tocar sobre la pista, anticipando el compás 5."},
        {"para": "Profe", "texto": "Mandar la pista."},
    ]


def test_una_clase_sin_recap_se_marca_y_no_se_le_inventa_nada(carpeta):
    clase = next(c for c in clases.listar(carpeta) if c.fecha == "2026-03-11")
    assert clase.con_recap is False
    assert clase.puntos_clave == [] and clase.proximos_pasos == []


def test_la_prosa_sin_secciones_se_lee_entera(carpeta):
    clase = next(c for c in clases.listar(carpeta) if c.fecha == "2026-02-25")
    assert clase.con_recap is True
    assert "bend del 2" in clase.texto
    assert clase.puntos_clave == []
    assert clase.titulo == "2026-02-25"


def test_lee_un_docx_sin_bibliotecas(tmp_path):
    """Un .docx es un zip con XML: el texto sale con la biblioteca estándar."""
    documento = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Hoy vimos el bend</w:t></w:r><w:r><w:t> del 3.</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Practicar despacio.</w:t></w:r></w:p></w:body></w:document>"
    )
    ruta = tmp_path / "2026-04-01.docx"
    with zipfile.ZipFile(ruta, "w") as zip_:
        zip_.writestr("word/document.xml", documento)

    clase = clases.leer_clase(str(ruta))

    assert clase.error == ""
    assert clase.texto == "Hoy vimos el bend del 3.\nPracticar despacio."


def test_un_archivo_roto_no_rompe_la_lista(tmp_path):
    (tmp_path / "2026-04-02.docx").write_bytes(b"esto no es un zip")
    lista = clases.listar(str(tmp_path))
    assert len(lista) == 1
    assert lista[0].error.startswith("no se pudo leer")
    assert lista[0].con_recap is False


def test_una_carpeta_que_no_existe_da_una_lista_vacia():
    assert clases.listar(os.path.join("no", "existe")) == []


def test_la_sintesis_se_busca_en_la_carpeta_y_en_la_de_arriba(tmp_path):
    (tmp_path / "aprendizaje.md").write_text("arriba", encoding="utf-8")
    adentro = tmp_path / "clases"
    adentro.mkdir()
    assert clases.sintesis(str(adentro)) == "arriba"
    (adentro / "aprendizaje.md").write_text("adentro", encoding="utf-8")
    assert clases.sintesis(str(adentro)) == "adentro"


# =============================================================================
# La carpeta configurable
# =============================================================================

def test_por_defecto_lee_de_material(tmp_path, monkeypatch):
    monkeypatch.delenv("CARPETA_CLASES", raising=False)
    assert clases.carpeta_de_clases(str(tmp_path / "no.env")) == "material"


def test_el_env_puede_apuntar_a_otra_carpeta(tmp_path, monkeypatch):
    monkeypatch.delenv("CARPETA_CLASES", raising=False)
    env = tmp_path / ".env"
    env.write_text("CARPETA_CLASES=C:\\donde\\sea\\clases\n", encoding="utf-8")
    assert clases.carpeta_de_clases(str(env)) == "C:\\donde\\sea\\clases"


# =============================================================================
# Que hacer en la app con cada cosa
# =============================================================================

def test_las_sugerencias_mandan_a_la_solapa_que_corresponde(carpeta):
    clase = next(c for c in clases.listar(carpeta) if c.fecha == "2026-03-04")
    propuestas = clases.sugerencias(clase.proximos_pasos)

    bend = propuestas[0]
    assert bend["para"] == "Ana"
    assert [p["solapa"] for p in bend["propuestas"]] == ["vivo"]

    pista = propuestas[1]
    assert "vivo" in [p["solapa"] for p in pista["propuestas"]]        # pista, BPM
    assert "frases" in [p["solapa"] for p in pista["propuestas"]]      # la frase

    profe = propuestas[2]
    assert profe["para"] == "Profe"
    assert all(p["solapa"] in ("vivo", "frases", "teoria") for p in profe["propuestas"])

    teoria = propuestas[3]
    la_de_teoria = next(p for p in teoria["propuestas"] if p["solapa"] == "teoria")
    assert la_de_teoria["config"] == {"posicion": 1, "escala": "pentatonica_mayor"}


def test_lo_que_no_dispara_ninguna_regla_no_propone_nada():
    propuestas = clases.sugerencias([{"para": "Ana", "texto": "comprar una armónica en La"}])
    assert propuestas[0]["propuestas"] == []


# =============================================================================
# Buscar y el resumen
# =============================================================================

def test_buscar_sin_acentos_ni_mayusculas_devuelve_pedazos(carpeta):
    resultados = clases.buscar(clases.listar(carpeta), "BEND DEL 3")
    assert [r["fecha"] for r in resultados] == ["2026-03-04"]
    assert "bend del 3" in resultados[0]["pedazos"][0]


def test_buscar_vacio_no_devuelve_nada(carpeta):
    assert clases.buscar(clases.listar(carpeta), "   ") == []


def test_el_resumen_junta_todo_para_la_solapa(carpeta):
    datos = clases.resumen(carpeta)

    assert datos["existe"] is True
    assert datos["cantidad"] == 3
    assert datos["ultima"]["fecha"] == "2026-03-04"          # la ultima CON recap
    assert "texto" in datos["ultima"]
    assert [c["fecha"] for c in datos["clases"]] == ["2026-03-11", "2026-03-04", "2026-02-25"]
    assert datos["para_practicar"][0]["fecha"] == "2026-03-04"
    assert datos["sintesis"].startswith("# Síntesis")


def test_el_resumen_de_una_carpeta_vacia_no_rompe():
    datos = clases.resumen(os.path.join("no", "existe"))
    assert datos["existe"] is False
    assert datos["ultima"] is None
    assert datos["clases"] == [] and datos["para_practicar"] == []
