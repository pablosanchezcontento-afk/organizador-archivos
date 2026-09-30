from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest
from conftest import crear

from organizador import ejecucion
from organizador.categorias import Configuracion
from organizador.ejecucion import (
    RegistroInvalido,
    aplicar,
    deshacer,
    mover_sin_sobrescribir,
    ultimo_registro,
)
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


# --- movimientos atómicos --------------------------------------------------------------


def test_mover_sin_enlaces_duros_usa_el_camino_alternativo(tmp_path: Path, monkeypatch) -> None:
    def sin_enlaces(*_args, **_kwargs):
        raise OSError(errno.EPERM, "enlaces no admitidos")

    monkeypatch.setattr("organizador.ejecucion.os.link", sin_enlaces)
    origen = crear(tmp_path, "a.pdf", "datos")
    mover_sin_sobrescribir(origen, tmp_path / "b.pdf")
    assert (tmp_path / "b.pdf").read_text(encoding="utf-8") == "datos"
    assert not origen.exists()

    otro = crear(tmp_path, "c.pdf")
    with pytest.raises(FileExistsError, match="ya existe"):
        mover_sin_sobrescribir(otro, tmp_path / "b.pdf")
    assert (tmp_path / "b.pdf").read_text(encoding="utf-8") == "datos"


def _sin_enlaces(monkeypatch) -> None:
    def sin_enlaces(*_args, **_kwargs):
        raise OSError(errno.EPERM, "enlaces no admitidos")

    monkeypatch.setattr("organizador.ejecucion.os.link", sin_enlaces)


def test_sin_enlaces_no_pisa_un_destino_creado_en_la_ventana(tmp_path: Path, monkeypatch) -> None:
    # Otro programa crea el destino justo después de cualquier comprobación previa: se
    # simula haciendo que exists() diga que no está. La reserva exclusiva lo detecta igual.
    _sin_enlaces(monkeypatch)
    origen = crear(tmp_path, "a.pdf", "mío")
    ajeno = crear(tmp_path, "b.pdf", "de otro programa")
    real = Path.exists

    def exists(self: Path, *args: object, **kwargs: object) -> bool:
        return False if self == ajeno else real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", exists)
    with pytest.raises(FileExistsError, match="ya existe"):
        mover_sin_sobrescribir(origen, ajeno)
    assert ajeno.read_text(encoding="utf-8") == "de otro programa"
    assert origen.read_text(encoding="utf-8") == "mío"


def test_sin_enlaces_entre_discos_copia_y_borra_el_original(tmp_path: Path, monkeypatch) -> None:
    _sin_enlaces(monkeypatch)

    def otro_disco(*_args, **_kwargs):
        raise OSError(errno.EXDEV, "otro disco")

    monkeypatch.setattr("organizador.ejecucion.os.replace", otro_disco)
    origen = crear(tmp_path, "a.pdf", "datos")
    mover_sin_sobrescribir(origen, tmp_path / "b.pdf")
    assert (tmp_path / "b.pdf").read_text(encoding="utf-8") == "datos"
    assert not origen.exists()


def test_si_la_copia_falla_se_deshace_la_reserva(tmp_path: Path, monkeypatch) -> None:
    _sin_enlaces(monkeypatch)

    def otro_disco(*_args, **_kwargs):
        raise OSError(errno.EXDEV, "otro disco")

    def disco_lleno(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "sin espacio")

    monkeypatch.setattr("organizador.ejecucion.os.replace", otro_disco)
    monkeypatch.setattr("organizador.ejecucion.shutil.copy2", disco_lleno)
    origen = crear(tmp_path, "a.pdf", "datos")
    with pytest.raises(OSError, match="sin espacio"):
        mover_sin_sobrescribir(origen, tmp_path / "b.pdf")
    assert not (tmp_path / "b.pdf").exists()
    assert origen.read_text(encoding="utf-8") == "datos"


def test_mover_un_origen_inexistente_falla(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        mover_sin_sobrescribir(tmp_path / "no.pdf", tmp_path / "si.pdf")


def test_archivo_bloqueado_no_queda_duplicado(tmp_path: Path, monkeypatch) -> None:
    origen = crear(tmp_path, "abierto.pdf")
    real = Path.unlink

    def bloqueado(self, *args, **kwargs):
        if self == origen:
            raise PermissionError("el archivo está abierto en otro programa")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", bloqueado)
    resultado = aplicar(tmp_path, planificar(tmp_path, Configuracion()))
    assert resultado.movidos == []
    assert "abierto" in resultado.errores[0][1]
    assert origen.exists()
    assert not (tmp_path / "PDF" / "abierto.pdf").exists()


# --- ejecución interrumpida ------------------------------------------------------------


def test_una_ejecucion_interrumpida_se_puede_deshacer(tmp_path: Path, monkeypatch) -> None:
    for nombre in ("a.pdf", "b.png", "c.zip"):
        crear(tmp_path, nombre)
    plan = planificar(tmp_path, Configuracion())
    original = ejecucion.mover_sin_sobrescribir
    llamadas = 0

    def se_corta(origen, destino):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 3:
            raise KeyboardInterrupt  # el usuario pulsa Ctrl+C a mitad
        original(origen, destino)

    monkeypatch.setattr("organizador.ejecucion.mover_sin_sobrescribir", se_corta)
    with pytest.raises(KeyboardInterrupt):
        aplicar(tmp_path, plan)
    monkeypatch.undo()

    registro = ultimo_registro(tmp_path)
    assert registro is not None and registro.suffix == ".jsonl"
    resultado = deshacer(tmp_path, registro)
    assert resultado.errores == []
    assert len(resultado.movidos) == 2
    assert {p.name for p in tmp_path.iterdir() if p.is_file()} == {"a.pdf", "b.png", "c.zip"}


def test_tras_una_ejecucion_completa_no_queda_diario(tmp_path: Path) -> None:
    crear(tmp_path, "a.pdf")
    aplicar(tmp_path, planificar(tmp_path, Configuracion()))
    assert list((tmp_path / CARPETA_REGISTROS).glob("en-curso-*")) == []


# --- registros manipulados o dañados ----------------------------------------------------


@pytest.mark.parametrize(
    "movimiento",
    [
        {"origen": "../fuera.pdf", "destino": "PDF/a.pdf"},
        {"origen": "a.pdf", "destino": "../../etc/passwd"},
        {"origen": "/tmp/absoluta.pdf", "destino": "PDF/a.pdf"},
        {"origen": "", "destino": "PDF/a.pdf"},
        {"origen": 3, "destino": "PDF/a.pdf"},
    ],
)
def test_un_registro_con_rutas_fuera_de_la_carpeta_se_rechaza(tmp_path: Path, movimiento) -> None:
    carpeta = tmp_path / "Descargas"
    crear(carpeta / "PDF", "a.pdf")
    (carpeta / CARPETA_REGISTROS).mkdir()
    registro = carpeta / CARPETA_REGISTROS / "registro-20260101-000000-000000.json"
    registro.write_text(json.dumps({"version": 1, "movimientos": [movimiento]}), encoding="utf-8")

    with pytest.raises(RegistroInvalido):
        deshacer(carpeta, registro)
    assert (carpeta / "PDF" / "a.pdf").exists()
    assert not (tmp_path / "fuera.pdf").exists()


@pytest.mark.parametrize(
    "contenido",
    ["{no es json", '{"version": 99, "movimientos": []}', '{"version": 1}', "[1, 2]"],
)
def test_un_registro_danado_se_rechaza(tmp_path: Path, contenido: str) -> None:
    (tmp_path / CARPETA_REGISTROS).mkdir()
    registro = tmp_path / CARPETA_REGISTROS / "registro-20260101-000000-000000.json"
    registro.write_text(contenido, encoding="utf-8")
    with pytest.raises(RegistroInvalido):
        deshacer(tmp_path, registro)


def test_un_enlace_simbolico_no_permite_salir_de_la_carpeta(tmp_path: Path) -> None:
    carpeta = tmp_path / "Descargas"
    carpeta.mkdir()
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    try:
        (carpeta / "atajo").symlink_to(fuera, target_is_directory=True)
    except OSError:
        pytest.skip("este sistema no permite crear enlaces simbólicos")
    (carpeta / CARPETA_REGISTROS).mkdir()
    registro = carpeta / CARPETA_REGISTROS / "registro-20260101-000000-000000.json"
    movimiento = {"origen": "atajo/robado.pdf", "destino": "PDF/a.pdf"}
    registro.write_text(json.dumps({"version": 1, "movimientos": [movimiento]}), encoding="utf-8")
    with pytest.raises(RegistroInvalido):
        deshacer(carpeta, registro)
