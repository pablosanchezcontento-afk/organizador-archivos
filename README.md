# organizador-archivos

[![CI](https://github.com/pablosanchezcontento-afk/organizador-archivos/actions/workflows/ci.yml/badge.svg)](https://github.com/pablosanchezcontento-afk/organizador-archivos/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Sin dependencias](https://img.shields.io/badge/dependencias-0-brightgreen)
![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue)

Herramienta de línea de comandos que **ordena tu carpeta de Descargas** (o
cualquier otra) en subcarpetas según el tipo de archivo: `Imágenes`, `PDF`,
`Instaladores`, `Comprimidos`…

Está pensada para ser **segura**:

- 🔍 Por defecto **solo muestra** lo que haría. Nada se mueve sin `--aplicar`.
- ↩️ Cada ejecución se puede **deshacer** con `--deshacer`.
- 🛡️ **Nunca sobrescribe**: si ya existe `foto.jpg`, guarda `foto (1).jpg`.
- ⏳ No toca **descargas a medias** (`.crdownload`, `.part`…), archivos ocultos ni `desktop.ini`.
- 📁 Solo ordena los archivos sueltos. Las subcarpetas que ya tenías se respetan.

```text
Descargas/                          Descargas/
├── apuntes-tema3.pdf               ├── Imágenes/
├── captura.png          organizar  │   ├── captura.png
├── node-v24.msi        ─────────►  │   └── vacaciones.jpg
├── proyecto.zip                    ├── Instaladores/
├── vacaciones.jpg                  │   └── node-v24.msi
└── peli.mkv.crdownload             ├── PDF/
                                    │   └── apuntes-tema3.pdf
                                    ├── Comprimidos/
                                    │   └── proyecto.zip
                                    └── peli.mkv.crdownload   ← descarga a medias: no se toca
```

## Instalación

Requiere Python 3.11 o superior. Con [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/pablosanchezcontento-afk/organizador-archivos
```

O con pip:

```bash
pip install git+https://github.com/pablosanchezcontento-afk/organizador-archivos
```

Tras instalarlo tendrás el comando `organizar`.

## Uso

```bash
organizar                      # simula el orden de tu carpeta de Descargas
organizar --aplicar            # lo aplica
organizar --deshacer           # deshace la última vez

organizar "D:\Fotos del móvil" --por-fecha --aplicar   # Imágenes/2026-09/...
organizar --detalle            # muestra cada archivo y su destino
organizar --config mi-config.toml
```

Ejemplo de salida:

```text
$ organizar
Carpeta: C:\Users\pablo\Downloads
  PDF                     2 archivos
  Imágenes                2 archivos
  Comprimidos             1 archivo
  Instaladores            1 archivo

Simulación: 6 archivos se moverían. Usa --aplicar para hacerlo.
```

| Opción | Qué hace |
|---|---|
| `CARPETA` | Carpeta a ordenar. Por defecto, `~/Downloads`. |
| `--aplicar` | Mueve los archivos de verdad. |
| `--deshacer` | Devuelve a su sitio los archivos de la última ejecución. |
| `--por-fecha` | Crea subcarpetas `AAAA-MM` según la fecha de modificación. |
| `--incluir-ocultos` | Mueve también archivos que empiezan por `.` |
| `--config ARCHIVO` | Usa categorías propias (ver abajo). |
| `-v`, `--detalle` | Lista cada archivo con su destino. |

Códigos de salida: `0` todo bien · `1` algún archivo no se pudo mover · `2` error en los argumentos o la configuración.

## Categorías

| Categoría | Extensiones |
|---|---|
| Imágenes | jpg, jpeg, png, gif, webp, bmp, svg, heic, ico, tif, tiff |
| Vídeos | mp4, mkv, mov, avi, webm, wmv, m4v |
| Música | mp3, wav, flac, ogg, m4a, aac, opus |
| PDF | pdf |
| Documentos | doc, docx, odt, rtf, txt, md, epub |
| Hojas de cálculo | xls, xlsx, ods, csv |
| Presentaciones | ppt, pptx, odp, key |
| Comprimidos | zip, rar, 7z, tar, gz, bz2, xz, tgz |
| Instaladores | exe, msi, msix, appx, dmg, pkg, deb, rpm, apk, iso |
| Código | py, java, js, ts, html, css, json, xml, sql, sh, ps1, c, cpp |
| Fuentes | ttf, otf, woff, woff2 |
| Otros | todo lo demás |

### Categorías propias

Crea un archivo TOML (tienes uno completo en [`config.ejemplo.toml`](config.ejemplo.toml)):

```toml
mover_otros = false          # lo que no encaje se queda donde está
ignorar = ["LEEME.txt"]

[categorias]
"Apuntes DAW" = ["pdf", "docx"]   # nueva categoría (tiene prioridad)
"Fuentes" = []                    # eliminar una categoría
```

## Cómo funciona el "deshacer"

Al aplicar, se guarda un registro en `CARPETA/.organizador/registro-FECHA.json`
con cada movimiento. `--deshacer` lee el último registro y devuelve cada
archivo a su sitio, **sin sobrescribir** nada que hayas creado después. Las
carpetas de categoría que quedan vacías se borran. Si algo no se puede
deshacer, el registro se conserva para volver a intentarlo.

## Desarrollo

```bash
git clone https://github.com/pablosanchezcontento-afk/organizador-archivos
cd organizador-archivos
uv run pytest           # 54 tests con cobertura (mínimo 95 %)
uv run ruff check .     # análisis estático
uv run organizar --help
```

```text
src/organizador/
├── categorias.py   # categorías y lectura del TOML
├── plan.py         # calcula qué mover y adónde (sin tocar el disco)
├── ejecucion.py    # aplica el plan, guarda el registro y deshace
└── cli.py          # argumentos y salida por pantalla
```

Separar **planificar** (función pura) de **ejecutar** permite que la simulación
sea exactamente lo que después se aplica, y que casi todo se pruebe sin mover
archivos reales. La integración continua ejecuta los tests en **Windows, Linux y
macOS** con Python 3.11 y 3.14.

## Autor

**Pablo Sánchez Contento** · [GitHub](https://github.com/pablosanchezcontento-afk)
