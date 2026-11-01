# Guía de las demos

Esta guía recorre cada demo: cómo ejecutarla, qué muestra cada sección de su informe y dónde está eso en el código. Los conceptos están en la [guía técnica](Guia_Tecnica_ES.md). Hay versión en inglés: [Demo_Guide_EN.md](Demo_Guide_EN.md).

Ejecuta todo desde la raíz del repositorio después de `uv sync`. Cada demo en Python acepta `--db RUTA` (por defecto `data/sample.sqlite3`) y `--out CARPETA` (por defecto `demo/output/`). El informe se imprime y además se guarda.

## Código compartido: `demo/common.py`

- `connect(db)` abre un DuckDB en memoria, carga la extensión sqlite (la instala la primera vez) y adjunta el fichero como `yt`, en solo lectura.
- `Report` escribe informes de texto plano: `section()`, `say()`, `sql()` (SQL sangrado) y `table()`, que da formato a los resultados con columnas de ancho fijo para que los informes se comparen línea a línea entre versiones de DuckDB. Los enteros llevan separador de miles, salvo las columnas `year`, `position` y `minutes`.

## Demo 1: adjuntar SQLite (`demo/run_01_attach_sqlite.py`)

```text
uv run python demo/run_01_attach_sqlite.py
```

| Sección del informe | Qué muestra | Código |
| --- | --- | --- |
| 1. Attach | `duckdb_databases()`: `memory` (DuckDB) y `yt` (sqlite, solo lectura) | `connect()` |
| 2. The tables | Filas de las seis tablas `catalog_*` (120 vídeos, 10.800 filas de estadísticas) | lista `CATALOG` |
| 3. Types | `DESCRIBE` de cinco columnas: `published` es `TIMESTAMP`, `caption` `BIGINT`, `tags` `VARCHAR` | |
| 4. Plain SQL | Los cinco vídeos más recientes, con `from_json` convirtiendo las etiquetas en listas | |
| 5. Join | Vídeos por lista, con la primera y la última subida, cruzando tres tablas | |

## Demo 2: analítica (`demo/run_02_analytics.py`)

```text
uv run python demo/run_02_analytics.py
```

Las consultas están en la lista `QUERIES`, cada una con un título y una nota. El informe imprime el SQL y después el resultado.

| # | Consulta | Característica | Cómo leer el resultado |
| --- | --- | --- | --- |
| 1 | Última cifra por vídeo | `QUALIFY row_number()` | El vídeo más visto de la muestra tiene 65.111 visualizaciones |
| 2 | Visualizaciones ganadas en 30 días | `lag(view_count, 29)` | Ganan más los vídeos recientes; los antiguos se han estancado |
| 3 | Etiquetas que atraen visualizaciones | `from_json` + `unnest`, `HAVING count(*) >= 5` | `mcp` y `tools` encabezan con 7.288 de media |
| 4 | Subidas por año y duración | `PIVOT ... ON length IN (...)` | Los vídeos de más de 10 minutos dominan todos los años |
| 5 | Idioma y año | `GROUP BY ALL`, `FILTER`, `median` | Subtítulos en cerca del 60 % de los vídeos |
| 6 | Mejor vídeo por lista | `arg_max`, `list(... ORDER BY)[1:3]` | Los tres primeros ids en el orden de la lista |
| 7 | Crecimiento semanal del canal | `date_trunc` en una CTE, después `lag` | El crecimiento semanal se frena a medida que el catálogo envejece |

Cada `ORDER BY` acaba en una clave única, así que el informe sale idéntico en cada ejecución. `tests/test_demos.py` lo compara con `demo/output/02_analytics.txt` e imprime un diff si cambia. Si cambias una consulta a propósito, vuelve a ejecutar la demo y haz commit del informe nuevo.

## Demo 3: formatos (`demo/run_03_parquet.py`)

```text
uv run python demo/run_03_parquet.py              # 2.000.000 de filas, unos 10 s
uv run python demo/run_03_parquet.py --rows 20000 # lo que ejecuta el test
```

Los ficheros temporales van a `demo/output/scratch/`, que git ignora.

| Sección del informe | Qué ocurre |
| --- | --- |
| 1. A larger table | `ATTACH ... AS big (TYPE sqlite)` sin `READ_ONLY`, y después `CREATE TABLE big.videostats AS SELECT ... FROM range(N)`. DuckDB escribe en SQLite. Los valores salen de `hash()`, así que son fijos para una versión de DuckDB. |
| 2. The question | Visualizaciones y me gusta por año, de cuatro maneras: el módulo `sqlite3`, DuckDB sobre el SQLite, una tabla DuckDB (`CREATE TABLE bigduck.videostats AS FROM big.videostats`) y `read_parquet` después de `COPY ... TO (FORMAT parquet, COMPRESSION zstd)`. El informe dice si los cuatro coinciden. |
| 3. Sizes | Tamaño de los ficheros en MiB |
| 4. Timings | El mejor de 3 por motor. Las líneas marcadas `[timing]` dependen de la máquina. |

En la pregunta, `taken_on` se convierte con `::DATE`, porque un DATE escrito en SQLite vuelve como texto.

## Demo 4: servidor MCP (`demo/mcp/init-server.sql`)

Requisitos: la [CLI de DuckDB](https://duckdb.org/docs/installation/) en el PATH, y Claude Code.

1. Abre Claude Code en la raíz del repositorio. Lee `.mcp.json` y ofrece el servidor `youtube-duckdb`. Apruébalo.
2. Comprueba que está conectado (`/mcp` en Claude Code). Debe listar `top_videos`, `video_history` y `search_videos`, más las propias `query`, `describe`, `list_tables` y `database_info`.
3. Haz las preguntas de la diapositiva "Live". Despliega cada llamada para enseñar el SQL o los parámetros.

Para servir el canal real, cambia la ruta del `ATTACH` en `init-server.sql` por `'../youtube_ML/db.sqlite3'`.

Si el servidor no arranca, ejecuta `duckdb -init demo/mcp/init-server.sql` en un terminal. Debe cargar sin mensajes y quedarse esperando en stdin. Un error en el fichero de inicio aparece ahí. `uv run pytest tests/test_mcp.py` ejecuta el mismo fichero hasta el arranque del servidor.

## Demo 5: cliente MCP (`demo/mcp/client.sql`, opcional)

1. En youtube_ML: `cd youtube_mcp && npm install && npm run build`, con la clave de API disponible como espera ese servidor (`youtube_ML/docs/mcp-server.md`).
2. Desde la raíz de este repositorio: `duckdb -init demo/mcp/client.sql`.
3. La salida lista las herramientas de youtube_mcp e imprime la respuesta de `get_channel_info` guardada en `channel_live`.

## Tests y CI

| Test | Qué comprueba |
| --- | --- |
| `test_report_matches_committed_output` | Las demos 1 y 2 reproducen `demo/output/` byte a byte |
| `test_parquet_demo_engines_agree` | La demo 3 con 20.000 filas: los cuatro motores coinciden |
| `test_sample_is_reproducible` | `make_sample.py` reconstruye las mismas filas (compara volcados SQL) |
| `test_server_script_until_start` | El fichero de inicio MCP se ejecuta hasta `mcp_server_start`; las vistas responden; el bloqueo rechaza un `SET` posterior |

La CI (`.github/workflows/ci.yml`) ejecuta ruff y pytest con `REQUIRE_MCP=1`, de modo que si falta duckdb_mcp el test falla en lugar de saltarse. Después ejecuta la demo 3 a tamaño completo y genera la presentación.
