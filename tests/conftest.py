from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest


def crear(carpeta: Path, nombre: str, contenido: str = "x", fecha: datetime | None = None) -> Path:
    """Crea un archivo de prueba, opcionalmente con una fecha de modificación."""
    ruta = carpeta / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    if fecha is not None:
        marca = fecha.timestamp()
        os.utime(ruta, (marca, marca))
    return ruta


@pytest.fixture
def descargas(tmp_path: Path) -> Path:
    """Una carpeta de descargas típica."""
    carpeta = tmp_path / "Descargas"
    carpeta.mkdir()
    for nombre in [
        "foto.JPG",
        "captura.png",
        "apuntes.pdf",
        "notas.docx",
        "datos.csv",
        "setup.exe",
        "proyecto.zip",
        "cancion.mp3",
        "script.py",
        "sin_extension",
        "raro.xyz",
    ]:
        crear(carpeta, nombre)
    crear(carpeta, "video.mp4.crdownload")  # descarga a medias
    crear(carpeta, "desktop.ini")
    crear(carpeta, ".oculto.txt")
    (carpeta / "Subcarpeta").mkdir()
    crear(carpeta / "Subcarpeta", "dentro.pdf")
    return carpeta
