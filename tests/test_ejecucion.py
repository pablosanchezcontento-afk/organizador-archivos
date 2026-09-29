from __future__ import annotations

import json
from pathlib import Path

from conftest import crear

from organizador.categorias import Configuracion
from organizador.ejecucion import aplicar, deshacer, ultimo_registro
from organizador.plan import CARPETA_REGISTROS, Movimiento, planificar


def contenido_arbol(carpeta: Path) -> set[str]:
    return {
        p.relative_to(carpeta).as_posix()
        for p in carpeta.rglob("*")
        if p.is_file() and CARPETA_REGISTROS not in p.parts
    }


def test_aplicar_mueve_y_guarda_registro(descargas: Path) -> None:
    plan = planificar(descargas, Configuracion())
    resultado = aplicar(descargas, plan)

    assert len(resultado.movidos) == 11
    assert resultado.errores == []
    assert (descargas / "PDF" / "apuntes.pdf").exists()
    assert not (descargas / "apuntes.pdf").exists()

    datos = json.loads(resultado.registro.read_text(encoding="utf-8"))
    assert datos["version"] == 1
    assert {"origen": "apuntes.pdf", "destino": "PDF/apuntes.pdf"} in datos["movimientos"]


def test_aplicar_y_deshacer_deja_todo_como_estaba(descargas: Path) -> None:
    antes = contenido_arbol(descargas)
    aplicar(descargas, planificar(descargas, Configuracion(), por_fecha=True))
    assert contenido_arbol(descargas) != antes

    registro = ultimo_registro(descargas)
    resultado = deshacer(descargas, registro)

    assert resultado.errores == []
    assert contenido_arbol(descargas) == antes
    assert not (descargas / "Imágenes").exists()  # las carpetas vacías se borran
    assert (descargas / "Subcarpeta").exists()  # las que ya existían se respetan
    assert not registro.exists()


def test_error_al_mover_no_detiene_el_resto(tmp_path: Path) -> None:
    ok = crear(tmp_path, "bien.pdf")
    plan = [
        Movimiento(tmp_path / "no_existe.pdf", tmp_path / "PDF" / "no_existe.pdf", "PDF"),
        Movimiento(ok, tmp_path / "PDF" / "bien.pdf", "PDF"),
    ]
    resultado = aplicar(tmp_path, plan)
    assert [o.name for o, _ in resultado.movidos] == ["bien.pdf"]
    assert [o.name for o, _ in resultado.errores] == ["no_existe.pdf"]


def test_destino_ocupado_despues_de_planificar(tmp_path: Path) -> None:
    crear(tmp_path, "a.pdf")
    plan = planificar(tmp_path, Configuracion())
    crear(tmp_path / "PDF", "a.pdf", "otro contenido")  # aparece entre plan y ejecución

    resultado = aplicar(tmp_path, plan)

    assert resultado.movidos == []
    assert "ya existe" in resultado.errores[0][1]
    assert resultado.registro is None
    assert (tmp_path / "PDF" / "a.pdf").read_text(encoding="utf-8") == "otro contenido"


def test_deshacer_no_sobrescribe(tmp_path: Path) -> None:
    crear(tmp_path, "a.pdf", "original")
    aplicar(tmp_path, planificar(tmp_path, Configuracion()))
    crear(tmp_path, "a.pdf", "nuevo")  # alguien crea otro archivo con el mismo nombre

    registro = ultimo_registro(tmp_path)
    resultado = deshacer(tmp_path, registro)

    assert "ocupado" in resultado.errores[0][1]
    assert (tmp_path / "a.pdf").read_text(encoding="utf-8") == "nuevo"
    assert (tmp_path / "PDF" / "a.pdf").read_text(encoding="utf-8") == "original"
    assert registro.exists()  # se conserva para reintentarlo


def test_deshacer_con_archivo_desaparecido(tmp_path: Path) -> None:
    crear(tmp_path, "a.pdf")
    aplicar(tmp_path, planificar(tmp_path, Configuracion()))
    (tmp_path / "PDF" / "a.pdf").unlink()

    resultado = deshacer(tmp_path, ultimo_registro(tmp_path))
    assert "ya no está" in resultado.errores[0][1]


def test_ultimo_registro(tmp_path: Path) -> None:
    assert ultimo_registro(tmp_path) is None
    (tmp_path / CARPETA_REGISTROS).mkdir()
    assert ultimo_registro(tmp_path) is None

    crear(tmp_path, "a.pdf")
    primero = aplicar(tmp_path, planificar(tmp_path, Configuracion())).registro
    crear(tmp_path, "b.pdf")
    segundo = aplicar(tmp_path, planificar(tmp_path, Configuracion())).registro

    assert primero != segundo
    assert ultimo_registro(tmp_path) == segundo


def test_plan_vacio_no_crea_registro(tmp_path: Path) -> None:
    resultado = aplicar(tmp_path, [])
    assert resultado.registro is None
    assert not (tmp_path / CARPETA_REGISTROS).exists()
