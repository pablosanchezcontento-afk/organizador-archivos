from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import crear

from organizador import cli


def test_simulacion_por_defecto_no_mueve_nada(
    descargas: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main([str(descargas)]) == 0
    salida = capsys.readouterr().out
    assert "Simulación: 11 archivos se moverían" in salida
    assert "Imágenes" in salida
    assert (descargas / "foto.JPG").exists()


def test_detalle_muestra_cada_archivo(descargas: Path, capsys: pytest.CaptureFixture) -> None:
    cli.main([str(descargas), "--detalle"])
    assert "foto.JPG  ->  Imágenes" in capsys.readouterr().out


def test_aplicar_y_deshacer(descargas: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main([str(descargas), "--aplicar"]) == 0
    salida = capsys.readouterr().out
    assert "Movidos 11 archivos" in salida
    assert "organizar --deshacer" in salida
    assert (descargas / "Instaladores" / "setup.exe").exists()

    assert cli.main([str(descargas), "--deshacer"]) == 0
    assert "Devueltos 11 archivos" in capsys.readouterr().out
    assert (descargas / "setup.exe").exists()


def test_aplicar_con_errores_devuelve_1(tmp_path: Path, monkeypatch, capsys) -> None:
    crear(tmp_path, "a.pdf")

    def falla(*_args, **_kwargs):
        raise PermissionError("el archivo está abierto en otro programa")

    monkeypatch.setattr("organizador.ejecucion.shutil.move", falla)
    assert cli.main([str(tmp_path), "--aplicar"]) == 1
    assert "abierto en otro programa" in capsys.readouterr().err


def test_deshacer_sin_registro(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main([str(tmp_path), "--deshacer"]) == 0
    assert "No hay nada que deshacer" in capsys.readouterr().out


def test_deshacer_con_errores_devuelve_1(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    crear(tmp_path, "a.pdf")
    cli.main([str(tmp_path), "--aplicar"])
    (tmp_path / "PDF" / "a.pdf").unlink()
    assert cli.main([str(tmp_path), "--deshacer"]) == 1
    assert "ya no está" in capsys.readouterr().err


def test_carpeta_vacia(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main([str(tmp_path)]) == 0
    assert "Nada que ordenar" in capsys.readouterr().out


def test_carpeta_inexistente(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main([str(tmp_path / "no")]) == 2
    assert "no es una carpeta" in capsys.readouterr().err


def test_configuracion_invalida(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    mala = tmp_path / "mala.toml"
    mala.write_text("x = = 1", encoding="utf-8")
    assert cli.main([str(tmp_path), "--config", str(mala)]) == 2
    assert "no es TOML válido" in capsys.readouterr().err


def test_configuracion_propia(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    crear(tmp_path, "tema1.pdf")
    config = tmp_path / "config.toml"
    config.write_text('[categorias]\n"Apuntes" = ["pdf"]\n', encoding="utf-8")
    cli.main([str(tmp_path), "--config", str(config), "--aplicar"])
    assert (tmp_path / "Apuntes" / "tema1.pdf").exists()


def test_carpeta_por_defecto_es_descargas(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "Downloads").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert cli.main([]) == 0
    assert "Nada que ordenar" in capsys.readouterr().out


def test_aplicar_y_deshacer_son_incompatibles(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main([str(tmp_path), "--aplicar", "--deshacer"])


def test_version(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert "organizar 1.0.0" in capsys.readouterr().out


def test_ejecutable_como_modulo(tmp_path: Path) -> None:
    salida = subprocess.run(
        [sys.executable, "-m", "organizador", str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "Nada que ordenar" in salida.stdout
