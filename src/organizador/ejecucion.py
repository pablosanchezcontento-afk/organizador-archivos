"""Aplicar un plan de movimientos y deshacerlo a partir del registro."""

from __future__ import annotations

import errno
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from organizador.plan import CARPETA_REGISTROS, Movimiento

VERSION_REGISTRO = 1
#: Prefijo del diario que se escribe mientras se mueven archivos. Si el proceso se corta
#: (apagón, Ctrl+C), el diario permite deshacer lo que llegó a moverse.
PREFIJO_DIARIO = "en-curso-"


class RegistroInvalido(ValueError):
    """El registro está dañado o intenta tocar rutas fuera de la carpeta."""


@dataclass
class Resultado:
    """Qué se ha movido y qué ha fallado."""

    movidos: list[tuple[Path, Path]] = field(default_factory=list)
    errores: list[tuple[Path, str]] = field(default_factory=list)
    registro: Path | None = None


def aplicar(carpeta: Path, plan: list[Movimiento]) -> Resultado:
    """Mueve los archivos del plan y guarda un registro para poder deshacer.

    Si un archivo no se puede mover (por ejemplo, porque está abierto en otro
    programa), se anota el error y se continúa con los demás. Nunca se
    sobrescribe un archivo, aunque aparezca entre la planificación y el movimiento.
    """
    resultado = Resultado()
    if not plan:
        return resultado
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    diario = carpeta / CARPETA_REGISTROS / f"{PREFIJO_DIARIO}{marca}.jsonl"
    for mov in plan:
        try:
            mov.destino.parent.mkdir(parents=True, exist_ok=True)
            mover_sin_sobrescribir(mov.origen, mov.destino)
        except OSError as e:
            resultado.errores.append((mov.origen, str(e)))
        else:
            resultado.movidos.append((mov.origen, mov.destino))
            _anotar_en_diario(carpeta, diario, mov.origen, mov.destino)

    if resultado.movidos:
        resultado.registro = _guardar_registro(carpeta, resultado.movidos, marca)
    diario.unlink(missing_ok=True)
    return resultado


def mover_sin_sobrescribir(origen: Path, destino: Path) -> None:
    """Mueve ``origen`` a ``destino`` sin sobrescribir nunca un archivo existente.

    En el mismo disco se usa un enlace duro, que el sistema crea de forma atómica
    y falla si el destino ya existe (no hay ventana entre comprobar y mover). Si
    el sistema de archivos no admite enlaces (FAT, exFAT, otro disco), se
    comprueba y se mueve.
    """
    try:
        os.link(origen, destino)
    except FileExistsError:
        raise FileExistsError(errno.EEXIST, f"ya existe {destino.name}") from None
    except OSError as e:
        if not origen.exists():
            raise
        # Enlaces no admitidos: comprobación explícita y movimiento normal.
        if destino.exists():
            raise FileExistsError(errno.EEXIST, f"ya existe {destino.name}") from e
        shutil.move(origen, destino)
    else:
        try:
            origen.unlink()
        except OSError:
            # Por ejemplo, el archivo está abierto en otro programa (Windows): se deshace
            # el enlace para no dejar el archivo duplicado y se informa del error.
            destino.unlink()
            raise


def _anotar_en_diario(carpeta: Path, diario: Path, origen: Path, destino: Path) -> None:
    diario.parent.mkdir(exist_ok=True)
    linea = {
        "origen": origen.relative_to(carpeta).as_posix(),
        "destino": destino.relative_to(carpeta).as_posix(),
    }
    with diario.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _guardar_registro(carpeta: Path, movidos: list[tuple[Path, Path]], marca: str) -> Path:
    carpeta_registros = carpeta / CARPETA_REGISTROS
    carpeta_registros.mkdir(exist_ok=True)
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
    temporal = registro.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(registro)  # el registro aparece completo o no aparece
    return registro


def ultimo_registro(carpeta: Path) -> Path | None:
    """El registro más reciente de la carpeta, o ``None`` si no hay ninguno.

    Incluye los diarios de ejecuciones interrumpidas, que se ordenan por la
    misma marca de tiempo que los registros.
    """
    carpeta_registros = carpeta / CARPETA_REGISTROS
    if not carpeta_registros.is_dir():
        return None
    candidatos = [
        *carpeta_registros.glob("registro-*.json"),
        *carpeta_registros.glob(f"{PREFIJO_DIARIO}*.jsonl"),
    ]
    candidatos = [r for r in candidatos if r.stat().st_size > 0]
    return max(candidatos, key=_marca_de, default=None)


def _marca_de(registro: Path) -> str:
    return registro.stem.removeprefix("registro-").removeprefix(PREFIJO_DIARIO)


def leer_movimientos(carpeta: Path, registro: Path) -> list[tuple[Path, Path]]:
    """Lee un registro (o un diario interrumpido) y valida cada ruta.

    :raises RegistroInvalido: si el archivo está dañado o alguna ruta sale de ``carpeta``.
    """
    try:
        texto = registro.read_text(encoding="utf-8")
        if registro.suffix == ".jsonl":
            movimientos = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
        else:
            datos = json.loads(texto)
            if datos.get("version") != VERSION_REGISTRO:
                raise RegistroInvalido(f"versión de registro no admitida: {datos.get('version')!r}")
            movimientos = datos["movimientos"]
        pares = [(m["origen"], m["destino"]) for m in movimientos]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        if isinstance(e, RegistroInvalido):
            raise
        raise RegistroInvalido(f"registro dañado: {registro.name}") from e
    return [(_ruta_dentro(carpeta, o), _ruta_dentro(carpeta, d)) for o, d in pares]


def _ruta_dentro(carpeta: Path, relativa: object) -> Path:
    """Convierte una ruta relativa del registro, sin permitir salir de ``carpeta``."""
    if not isinstance(relativa, str) or not relativa:
        raise RegistroInvalido("ruta vacía o no válida en el registro")
    parte = Path(relativa)
    if parte.is_absolute() or parte.drive or ".." in parte.parts:
        raise RegistroInvalido(f"ruta fuera de la carpeta en el registro: {relativa}")
    ruta = carpeta / parte
    if not ruta.resolve().is_relative_to(carpeta.resolve()):
        raise RegistroInvalido(f"ruta fuera de la carpeta en el registro: {relativa}")
    return ruta


def deshacer(carpeta: Path, registro: Path) -> Resultado:
    """Devuelve los archivos a su sitio original según el registro.

    Solo acepta rutas dentro de ``carpeta`` (un registro manipulado no puede mover
    archivos fuera de ella) y no sobrescribe nada: si el sitio original vuelve a estar ocupado, o el
    archivo ya no está donde se dejó, se anota el error. Las carpetas de
    categoría que queden vacías se eliminan. El registro se borra si todo
    se ha deshecho correctamente.
    """
    movimientos = leer_movimientos(carpeta, registro)
    resultado = Resultado(registro=registro)
    carpetas_tocadas: set[Path] = set()

    for origen, destino in reversed(movimientos):
        if not destino.exists():
            resultado.errores.append((destino, "ya no está en la carpeta de destino"))
            continue
        if origen.exists():
            resultado.errores.append((origen, "el sitio original está ocupado"))
            continue
        try:
            mover_sin_sobrescribir(destino, origen)
        except FileExistsError:  # apareció justo ahora
            resultado.errores.append((origen, "el sitio original está ocupado"))
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
