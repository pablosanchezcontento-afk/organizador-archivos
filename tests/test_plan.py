from __future__ import annotations

from datetime import datetime
from pathlib import Path

from conftest import crear

from organizador.categorias import Configuracion
from organizador.plan import nombre_libre, planificar, resumen


def nombres(plan) -> dict[str, str]:
    return {m.origen.name: m.destino.relative_to(m.origen.parent).as_posix() for m in plan}


def test_planifica_por_tipo_sin_tocar_nada(descargas: Path) -> None:
    antes = sorted(p.name for p in descargas.iterdir())
    plan = planificar(descargas, Configuracion())

    assert nombres(plan) == {
        "apuntes.pdf": "PDF/apuntes.pdf",
        "cancion.mp3": "Música/cancion.mp3",
        "captura.png": "Imágenes/captura.png",
        "datos.csv": "Hojas de cálculo/datos.csv",
        "foto.JPG": "Imágenes/foto.JPG",
        "notas.docx": "Documentos/notas.docx",
        "proyecto.zip": "Comprimidos/proyecto.zip",
        "raro.xyz": "Otros/raro.xyz",
        "script.py": "Código/script.py",
        "setup.exe": "Instaladores/setup.exe",
        "sin_extension": "Otros/sin_extension",
    }
    assert sorted(p.name for p in descargas.iterdir()) == antes


def test_ignora_temporales_sistema_ocultos_y_subcarpetas(descargas: Path) -> None:
    movidos = {m.origen.name for m in planificar(descargas, Configuracion())}
    assert "video.mp4.crdownload" not in movidos
    assert "desktop.ini" not in movidos
    assert ".oculto.txt" not in movidos
    assert "dentro.pdf" not in movidos


def test_incluir_ocultos(descargas: Path) -> None:
    plan = planificar(descargas, Configuracion(), incluir_ocultos=True)
    assert ".oculto.txt" in {m.origen.name for m in plan}


def test_ignorar_por_nombre(descargas: Path) -> None:
    config = Configuracion(ignorar=frozenset({"setup.exe"}))
    assert "setup.exe" not in {m.origen.name for m in planificar(descargas, config)}


def test_por_fecha_usa_la_fecha_de_modificacion(tmp_path: Path) -> None:
    crear(tmp_path, "viaje.jpg", fecha=datetime(2025, 7, 14, 12, 0))
    plan = planificar(tmp_path, Configuracion(), por_fecha=True)
    assert nombres(plan) == {"viaje.jpg": "Imágenes/2025-07/viaje.jpg"}


def test_no_sobrescribe_archivos_existentes(tmp_path: Path) -> None:
    crear(tmp_path, "foto.jpg")
    crear(tmp_path / "Imágenes", "foto.jpg")
    crear(tmp_path / "Imágenes", "foto (1).jpg")
    plan = planificar(tmp_path, Configuracion())
    assert nombres(plan) == {"foto.jpg": "Imágenes/foto (2).jpg"}


def test_nombre_libre_tiene_en_cuenta_las_reservas_sin_distinguir_mayusculas(
    tmp_path: Path,
) -> None:
    ocupados: set[str] = set()
    primero = nombre_libre(tmp_path, "Informe.pdf", ocupados)
    segundo = nombre_libre(tmp_path, "informe.PDF", ocupados)
    assert primero.name == "Informe.pdf"
    assert segundo.name == "informe (1).PDF"


def test_resumen_cuenta_por_categoria(descargas: Path) -> None:
    conteo = resumen(planificar(descargas, Configuracion()))
    assert conteo["Imágenes"] == 2
    assert conteo["Otros"] == 2
    assert sum(conteo.values()) == 11


def test_carpeta_vacia(tmp_path: Path) -> None:
    assert planificar(tmp_path, Configuracion()) == []
