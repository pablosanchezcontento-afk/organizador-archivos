"""Categorías de archivos y lectura de la configuración del usuario."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CATEGORIAS_POR_DEFECTO: dict[str, list[str]] = {
    "Imágenes": ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "heic", "ico", "tif", "tiff"],
    "Vídeos": ["mp4", "mkv", "mov", "avi", "webm", "wmv", "m4v"],
    "Música": ["mp3", "wav", "flac", "ogg", "m4a", "aac", "opus"],
    "PDF": ["pdf"],
    "Documentos": ["doc", "docx", "odt", "rtf", "txt", "md", "epub"],
    "Hojas de cálculo": ["xls", "xlsx", "ods", "csv"],
    "Presentaciones": ["ppt", "pptx", "odp", "key"],
    "Comprimidos": ["zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz"],
    "Instaladores": ["exe", "msi", "msix", "appx", "dmg", "pkg", "deb", "rpm", "apk", "iso"],
    "Código": [
        "py",
        "java",
        "js",
        "ts",
        "html",
        "css",
        "json",
        "xml",
        "sql",
        "sh",
        "ps1",
        "c",
        "cpp",
    ],
    "Fuentes": ["ttf", "otf", "woff", "woff2"],
}

CATEGORIA_OTROS = "Otros"

#: Extensiones de descargas a medias: nunca se mueven.
EXTENSIONES_TEMPORALES = frozenset(
    {"crdownload", "part", "partial", "download", "tmp", "opdownload"}
)

#: Nombres de archivo que gestiona el sistema operativo y no se tocan.
NOMBRES_IGNORADOS = frozenset({"desktop.ini", "thumbs.db", ".ds_store"})


def extension(ruta: Path) -> str:
    """Devuelve la extensión en minúsculas y sin punto ("" si no tiene).

    Para archivos como ``copia.tar.gz`` devuelve ``gz``.
    """
    return ruta.suffix.lower().removeprefix(".")


@dataclass(frozen=True)
class Configuracion:
    """Opciones que controlan cómo se ordena una carpeta."""

    categorias: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in CATEGORIAS_POR_DEFECTO.items()}
    )
    #: Si es ``False``, los archivos sin categoría se quedan donde están.
    mover_otros: bool = True
    #: Nombres (sin distinguir mayúsculas) que se dejan siempre en su sitio.
    ignorar: frozenset[str] = frozenset()

    def categoria_de(self, ruta: Path) -> str | None:
        """Categoría de un archivo, ``Otros`` si no encaja o ``None`` si no se mueve."""
        ext = extension(ruta)
        for nombre, extensiones in self.categorias.items():
            if ext and ext in extensiones:
                return nombre
        return CATEGORIA_OTROS if self.mover_otros else None


class ErrorConfiguracion(ValueError):
    """El archivo de configuración no tiene el formato esperado."""


def cargar_configuracion(ruta: Path | None) -> Configuracion:
    """Lee un archivo TOML y lo combina con las categorías por defecto.

    Formato::

        mover_otros = false
        ignorar = ["notas.txt"]

        [categorias]
        "Apuntes" = ["pdf", "docx"]   # nueva categoría o sustituye a una existente
        "Vídeos" = []                 # lista vacía: elimina la categoría

    Las extensiones de una categoría del usuario se quitan del resto, así que
    ``"Apuntes" = ["pdf"]`` hace que los PDF vayan a *Apuntes* y no a *PDF*.
    """
    if ruta is None:
        return Configuracion()
    try:
        datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ErrorConfiguracion(f"No existe el archivo de configuración: {ruta}") from e
    except tomllib.TOMLDecodeError as e:
        raise ErrorConfiguracion(f"El archivo {ruta} no es TOML válido: {e}") from e

    categorias = {k: list(v) for k, v in CATEGORIAS_POR_DEFECTO.items()}
    propias = datos.get("categorias", {})
    if not isinstance(propias, dict):
        raise ErrorConfiguracion("[categorias] debe ser una tabla de nombre = [extensiones]")

    for nombre, extensiones in propias.items():
        if not isinstance(extensiones, list) or not all(isinstance(e, str) for e in extensiones):
            raise ErrorConfiguracion(f"La categoría '{nombre}' debe ser una lista de extensiones")
        normalizadas = [e.lower().removeprefix(".") for e in extensiones]
        for otra in categorias.values():
            otra[:] = [e for e in otra if e not in normalizadas]
        if normalizadas:
            # Las categorías del usuario se comprueban antes que las de serie.
            categorias.pop(nombre, None)
            categorias = {nombre: normalizadas, **categorias}
        else:
            categorias.pop(nombre, None)

    mover_otros = datos.get("mover_otros", True)
    if not isinstance(mover_otros, bool):
        raise ErrorConfiguracion("mover_otros debe ser true o false")

    ignorar = datos.get("ignorar", [])
    if not isinstance(ignorar, list) or not all(isinstance(n, str) for n in ignorar):
        raise ErrorConfiguracion("ignorar debe ser una lista de nombres de archivo")

    return Configuracion(
        categorias={k: v for k, v in categorias.items() if v},
        mover_otros=mover_otros,
        ignorar=frozenset(n.casefold() for n in ignorar),
    )
