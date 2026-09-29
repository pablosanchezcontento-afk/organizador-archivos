"""Interfaz de línea de comandos: ``organizar [CARPETA] [opciones]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from organizador import __version__
from organizador.categorias import ErrorConfiguracion, cargar_configuracion
from organizador.ejecucion import RegistroInvalido, aplicar, deshacer, ultimo_registro
from organizador.plan import planificar, resumen

DESCRIPCION = """\
Ordena los archivos de una carpeta en subcarpetas según su tipo
(Imágenes, PDF, Instaladores...).

Por defecto solo MUESTRA lo que haría. Añade --aplicar para mover los archivos.
Cada ejecución se puede deshacer con --deshacer.
"""


def carpeta_descargas() -> Path:
    """Carpeta de descargas del usuario (``~/Downloads``)."""
    return Path.home() / "Downloads"


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organizar",
        description=DESCRIPCION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "carpeta",
        nargs="?",
        type=Path,
        help="carpeta a ordenar (por defecto, tu carpeta de Descargas)",
    )
    accion = parser.add_mutually_exclusive_group()
    accion.add_argument("--aplicar", action="store_true", help="mover de verdad los archivos")
    accion.add_argument("--deshacer", action="store_true", help="deshacer la última ejecución")
    parser.add_argument(
        "--por-fecha",
        action="store_true",
        help="crear subcarpetas AAAA-MM dentro de cada categoría",
    )
    parser.add_argument(
        "--incluir-ocultos", action="store_true", help="mover también archivos que empiezan por '.'"
    )
    parser.add_argument("--config", type=Path, help="archivo TOML con categorías propias")
    parser.add_argument("-v", "--detalle", action="store_true", help="mostrar cada archivo")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve el código de salida (0 = todo bien)."""
    args = crear_parser().parse_args(argv)
    carpeta = (args.carpeta or carpeta_descargas()).expanduser().resolve()
    if not carpeta.is_dir():
        print(f"Error: '{carpeta}' no es una carpeta.", file=sys.stderr)
        return 2

    if args.deshacer:
        return _deshacer(carpeta)

    try:
        config = cargar_configuracion(args.config)
    except ErrorConfiguracion as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    plan = planificar(
        carpeta, config, por_fecha=args.por_fecha, incluir_ocultos=args.incluir_ocultos
    )
    if not plan:
        print(f"Nada que ordenar en {carpeta}.")
        return 0

    print(f"Carpeta: {carpeta}")
    for categoria, n in sorted(resumen(plan).items(), key=lambda par: (-par[1], par[0])):
        print(f"  {categoria:<20} {n:>4} archivo{'s' if n != 1 else ''}")
    if args.detalle:
        for mov in plan:
            print(f"    {mov.origen.name}  ->  {mov.destino.relative_to(carpeta)}")

    if not args.aplicar:
        print(f"\nSimulación: {len(plan)} archivos se moverían. Usa --aplicar para hacerlo.")
        return 0

    resultado = aplicar(carpeta, plan)
    print(f"\nMovidos {len(resultado.movidos)} archivos.")
    for ruta, error in resultado.errores:
        print(f"  No se pudo mover {ruta.name}: {error}", file=sys.stderr)
    if resultado.registro:
        print("Para deshacerlo: organizar --deshacer" + (f' "{carpeta}"' if args.carpeta else ""))
    return 1 if resultado.errores else 0


def _deshacer(carpeta: Path) -> int:
    registro = ultimo_registro(carpeta)
    if registro is None:
        print(f"No hay nada que deshacer en {carpeta}.")
        return 0
    try:
        resultado = deshacer(carpeta, registro)
    except RegistroInvalido as e:
        print(f"No se puede deshacer: {e}", file=sys.stderr)
        return 2
    print(f"Devueltos {len(resultado.movidos)} archivos a su sitio.")
    for ruta, error in resultado.errores:
        print(f"  {ruta.name}: {error}", file=sys.stderr)
    return 1 if resultado.errores else 0
