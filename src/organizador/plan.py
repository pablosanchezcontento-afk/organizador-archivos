"""Cálculo del plan de movimientos, sin tocar el disco."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from organizador.categorias import (
    EXTENSIONES_TEMPORALES,
    NOMBRES_IGNORADOS,
    Configuracion,
    extension,
)

#: Carpeta donde se guardan los registros para poder deshacer.
CARPETA_REGISTROS = ".organizador"


@dataclass(frozen=True)
class Movimiento:
    """Un archivo que se va a mover de ``origen`` a ``destino``."""

    origen: Path
    destino: Path
    categoria: str


def debe_ignorarse(ruta: Path, config: Configuracion, incluir_ocultos: bool) -> bool:
    """Indica si un archivo debe quedarse donde está."""
    nombre = ruta.name.casefold()
    if nombre in NOMBRES_IGNORADOS or nombre in config.ignorar:
        return True
    if extension(ruta) in EXTENSIONES_TEMPORALES:
        return True
    return not incluir_ocultos and ruta.name.startswith(".")


def nombre_libre(carpeta: Path, nombre: str, ocupados: set[str]) -> Path:
    """Devuelve una ruta en ``carpeta`` que no exista ni esté ya reservada.

    Si ``foto.jpg`` está ocupado prueba ``foto (1).jpg``, ``foto (2).jpg``...
    La comparación no distingue mayúsculas, igual que el sistema de archivos
    de Windows, para que el plan sea válido en cualquier sistema.
    """
    candidato = carpeta / nombre
    base, sufijo = Path(nombre).stem, Path(nombre).suffix
    contador = 1
    while candidato.exists() or str(candidato).casefold() in ocupados:
        candidato = carpeta / f"{base} ({contador}){sufijo}"
        contador += 1
    ocupados.add(str(candidato).casefold())
    return candidato


def planificar(
    carpeta: Path,
    config: Configuracion,
    *,
    por_fecha: bool = False,
    incluir_ocultos: bool = False,
) -> list[Movimiento]:
    """Calcula qué archivos se moverían y adónde, sin modificar nada.

    Solo se tienen en cuenta los archivos que están directamente en
    ``carpeta``; las subcarpetas no se recorren.

    Con ``por_fecha`` se añade una subcarpeta ``AAAA-MM`` según la fecha de
    última modificación del archivo (``Imágenes/2026-09/foto.jpg``).
    """
    ocupados: set[str] = set()
    plan: list[Movimiento] = []
    for ruta in sorted(carpeta.iterdir(), key=lambda r: r.name.casefold()):
        if not ruta.is_file() or ruta.is_symlink():
            continue
        if debe_ignorarse(ruta, config, incluir_ocultos):
            continue
        categoria = config.categoria_de(ruta)
        if categoria is None:
            continue
        destino = carpeta / categoria
        if por_fecha:
            fecha = datetime.fromtimestamp(ruta.stat().st_mtime)
            destino = destino / fecha.strftime("%Y-%m")
        plan.append(Movimiento(ruta, nombre_libre(destino, ruta.name, ocupados), categoria))
    return plan


def resumen(plan: list[Movimiento]) -> Counter[str]:
    """Número de archivos por categoría."""
    return Counter(m.categoria for m in plan)
