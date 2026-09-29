"""Aplicar un plan de movimientos y deshacerlo a partir del registro."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from organizador.plan import CARPETA_REGISTROS, Movimiento

VERSION_REGISTRO = 1


@dataclass
class Resultado:
    """Qué se ha movido y qué ha fallado."""

    movidos: list[tuple[Path, Path]] = field(default_factory=list)
    errores: list[tuple[Path, str]] = field(default_factory=list)
    registro: Path | None = None


def aplicar(carpeta: Path, plan: list[Movimiento]) -> Resultado:
    """Mueve los archivos del plan y guarda un registro para poder deshacer.

    Si un archivo no se puede mover (por ejemplo, porque está abierto en otro
    programa), se anota el error y se continúa con los demás.
    """
    resultado = Resultado()
    for mov in plan:
        try:
            mov.destino.parent.mkdir(parents=True, exist_ok=True)
            if mov.destino.exists():
                raise FileExistsError(f"ya existe {mov.destino.name}")
            shutil.move(mov.origen, mov.destino)
        except OSError as e:
            resultado.errores.append((mov.origen, str(e)))
        else:
            resultado.movidos.append((mov.origen, mov.destino))

    if resultado.movidos:
        resultado.registro = _guardar_registro(carpeta, resultado.movidos)
    return resultado


def _guardar_registro(carpeta: Path, movidos: list[tuple[Path, Path]]) -> Path:
    carpeta_registros = carpeta / CARPETA_REGISTROS
    carpeta_registros.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    registro = carpeta_registros / f"registro-{marca}.json"
    datos = {
        "version": VERSION_REGISTRO,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "carpeta": str(carpeta),
        "movimientos": [
            {
                "origen": o.relative_to(carpeta).as_posix(),
                "destino": d.relative_to(carpeta).as_posix(),
            }
            for o, d in movidos
        ],
    }
    registro.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return registro


def ultimo_registro(carpeta: Path) -> Path | None:
    """El registro más reciente de la carpeta, o ``None`` si no hay ninguno."""
    carpeta_registros = carpeta / CARPETA_REGISTROS
    if not carpeta_registros.is_dir():
        return None
    registros = sorted(carpeta_registros.glob("registro-*.json"))
    return registros[-1] if registros else None


def deshacer(carpeta: Path, registro: Path) -> Resultado:
    """Devuelve los archivos a su sitio original según el registro.

    No sobrescribe nada: si el sitio original vuelve a estar ocupado, o el
    archivo ya no está donde se dejó, se anota el error. Las carpetas de
    categoría que queden vacías se eliminan. El registro se borra si todo
    se ha deshecho correctamente.
    """
    datos = json.loads(registro.read_text(encoding="utf-8"))
    resultado = Resultado(registro=registro)
    carpetas_tocadas: set[Path] = set()

    for mov in reversed(datos["movimientos"]):
        origen = carpeta / mov["origen"]
        destino = carpeta / mov["destino"]
        if not destino.exists():
            resultado.errores.append((destino, "ya no está en la carpeta de destino"))
            continue
        if origen.exists():
            resultado.errores.append((origen, "el sitio original está ocupado"))
            continue
        try:
            shutil.move(destino, origen)
        except OSError as e:  # pragma: no cover - depende del sistema operativo
            resultado.errores.append((destino, str(e)))
        else:
            resultado.movidos.append((destino, origen))
            carpetas_tocadas.add(destino.parent)

    _borrar_carpetas_vacias(carpeta, carpetas_tocadas)
    if not resultado.errores:
        registro.unlink()
    return resultado


def _borrar_carpetas_vacias(raiz: Path, carpetas: set[Path]) -> None:
    # De la más profunda a la menos profunda, sin salir nunca de la raíz.
    for carpeta in sorted(carpetas, key=lambda c: len(c.parts), reverse=True):
        actual = carpeta
        while actual != raiz and raiz in actual.parents:
            try:
                actual.rmdir()
            except OSError:
                break
            actual = actual.parent
