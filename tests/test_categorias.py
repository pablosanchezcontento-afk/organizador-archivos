from __future__ import annotations

from pathlib import Path

import pytest

from organizador.categorias import (
    CATEGORIAS_POR_DEFECTO,
    Configuracion,
    ErrorConfiguracion,
    cargar_configuracion,
    extension,
)


@pytest.mark.parametrize(
    ("nombre", "esperada"),
    [("foto.JPG", "jpg"), ("copia.tar.gz", "gz"), ("sin_extension", ""), (".bashrc", "")],
)
def test_extension(nombre: str, esperada: str) -> None:
    assert extension(Path(nombre)) == esperada


@pytest.mark.parametrize(
    ("nombre", "categoria"),
    [
        ("foto.jpeg", "Imágenes"),
        ("FOTO.PNG", "Imágenes"),
        ("apuntes.pdf", "PDF"),
        ("setup.msi", "Instaladores"),
        ("backup.7z", "Comprimidos"),
        ("tabla.xlsx", "Hojas de cálculo"),
        ("raro.xyz", "Otros"),
        ("sin_extension", "Otros"),
    ],
)
def test_categoria_por_defecto(nombre: str, categoria: str) -> None:
    assert Configuracion().categoria_de(Path(nombre)) == categoria


def test_sin_mover_otros_devuelve_none() -> None:
    assert Configuracion(mover_otros=False).categoria_de(Path("raro.xyz")) is None


def test_ninguna_extension_esta_en_dos_categorias_por_defecto() -> None:
    todas = [e for extensiones in CATEGORIAS_POR_DEFECTO.values() for e in extensiones]
    assert len(todas) == len(set(todas))


def test_sin_archivo_usa_valores_por_defecto() -> None:
    assert cargar_configuracion(None) == Configuracion()


def test_categoria_propia_tiene_prioridad(tmp_path: Path) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(
        """
        mover_otros = false
        ignorar = ["Notas.TXT"]

        [categorias]
        "Apuntes" = [".PDF", "docx"]
        "Vídeos" = []
        """,
        encoding="utf-8",
    )
    config = cargar_configuracion(config_toml)

    assert config.categoria_de(Path("tema1.pdf")) == "Apuntes"
    assert config.categoria_de(Path("trabajo.docx")) == "Apuntes"
    assert "PDF" not in config.categorias  # se quedó sin extensiones
    assert "Vídeos" not in config.categorias
    assert config.categoria_de(Path("peli.mp4")) is None
    assert config.ignorar == frozenset({"notas.txt"})


def test_sustituir_categoria_existente(tmp_path: Path) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text('[categorias]\n"Imágenes" = ["png"]\n', encoding="utf-8")
    config = cargar_configuracion(config_toml)
    assert config.categorias["Imágenes"] == ["png"]
    assert config.categoria_de(Path("foto.jpg")) == "Otros"


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        ("esto no es toml = = =", "no es TOML válido"),
        ("categorias = 3", "debe ser una tabla"),
        ('[categorias]\n"Fotos" = "jpg"', "debe ser una lista"),
        ('mover_otros = "sí"', "true o false"),
        ("ignorar = 5", "lista de nombres"),
    ],
)
def test_configuracion_invalida(tmp_path: Path, contenido: str, mensaje: str) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(contenido, encoding="utf-8")
    with pytest.raises(ErrorConfiguracion, match=mensaje):
        cargar_configuracion(config_toml)


def test_configuracion_inexistente(tmp_path: Path) -> None:
    with pytest.raises(ErrorConfiguracion, match="No existe"):
        cargar_configuracion(tmp_path / "no.toml")
