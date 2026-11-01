# DuckDB y su servidor MCP: guía técnica

Esta guía explica qué muestran las demos de este repositorio y por qué funcionan. Está escrita para una ingeniera o un ingeniero que conoce SQL y Python y no ha usado DuckDB. La [guía de las demos](Guia_Demos_ES.md) recorre el código. La [guía del presentador](Guia_Presentador_ES.md) sigue la presentación diapositiva a diapositiva. Hay versión en inglés: [Technical_Guide_EN.md](Technical_Guide_EN.md).

Las cifras salen de los informes de `demo/output/`. Los datos son la muestra sintética de `data/sample.sqlite3`, salvo que una sección diga otra cosa.

## 1. Qué es DuckDB

DuckDB es una base de datos SQL analítica que se ejecuta dentro de tu proceso. Se añade con `uv add duckdb` y se abre con `duckdb.connect()`. No hay servidor que arrancar ni puerto que proteger. La base de datos es un único fichero, o memoria.

Es el mismo formato de uso que SQLite. Lo que cambia es el motor:

| | SQLite | DuckDB |
| --- | --- | --- |
| Almacenamiento | Por filas: los valores de una fila van juntos | Por columnas: los valores de una columna van juntos |
| Ejecución | Fila a fila | Vectores de valores, en todos los núcleos |
| Pensado para | Muchas lecturas y escrituras pequeñas (una aplicación) | Recorridos, joins y agregados sobre muchas filas (análisis) |
| Escritores | Uno cada vez | Un proceso cada vez |

Encajan juntos. La app Django de youtube_ML sigue escribiendo en SQLite, que es lo que le conviene. DuckDB lee ese mismo fichero para analizarlo.

### 1.1 DuckDB 2.0

Las demos usan la línea 2.0 LTS: `pyproject.toml` fija `duckdb>=2.0,<3` y la CI ejecuta todas las demos en 2.0.0. Dos cambios de la API de Python afectaron a este código (sección 6).

## 2. Los datos

### 2.1 De la API de YouTube a SQLite

`manage.py sync_youtube` de youtube_ML lee el canal con una clave de API. Nunca escribe en YouTube. Inserta o actualiza seis tablas en `db.sqlite3`:

| Tabla | Una fila por | Notas |
| --- | --- | --- |
| `catalog_channel` | canal | |
| `catalog_channelsnapshot` | canal y día | suscriptores, visualizaciones, número de vídeos |
| `catalog_video` | vídeo público | `tags` y `topics` son texto JSON |
| `catalog_videostats` | vídeo y día | visualizaciones, me gusta, comentarios |
| `catalog_playlist` | lista de reproducción | |
| `catalog_playlistitem` | vídeo en una lista | `video_id` es texto, no clave foránea |

Si se ejecuta dos veces el mismo día, se sobrescribe ese día. Un día nuevo añade filas. Con una ejecución diaria, las dos tablas de estadísticas se convierten en series temporales.

### 2.2 La muestra

`data/sample.sqlite3` usa el mismo DDL (`data/schema.sql`, copiado de la migración de Django) con datos inventados. Tiene 120 vídeos, 90 días de estadísticas (10.800 filas) y 8 listas, con semilla 7. `data/make_sample.py` la reconstruye con las mismas filas, y un test compara los volcados SQL. Las visualizaciones siguen una curva que se satura, con ruido, para que las consultas de ventana encuentren algo. Nada de la muestra son datos reales del canal.

Para el canal real, pasa `--db ../youtube_ML/db.sqlite3` o define `YOUTUBE_DB`.

## 3. Leer SQLite sin copiarlo (demo 1)

```sql
INSTALL sqlite; LOAD sqlite;
ATTACH 'db.sqlite3' AS yt (TYPE sqlite, READ_ONLY);
SELECT count(*) FROM yt.catalog_video;
```

`INSTALL` descarga la extensión una vez, desde el repositorio de DuckDB. `ATTACH` convierte el fichero en un catálogo llamado `yt`. No se copia nada: cada consulta lee las páginas de SQLite que necesita. `READ_ONLY` impide que esta conexión cambie el fichero, lo que importa cuando el dueño es la app Django o la sincronización.

DuckDB asigna tipos a partir del esquema declarado en SQLite:

| Tipo declarado en SQLite | Tipo en DuckDB | Consecuencia |
| --- | --- | --- |
| `varchar`, `text` | `VARCHAR` | |
| `datetime` | `TIMESTAMP` | `year()` y `date_trunc()` funcionan directamente |
| `integer`, `bigint` | `BIGINT` | |
| `bool` | `BIGINT` | compara con `= 1`, o convierte el tipo |
| JSON en `text` | `VARCHAR` | se convierte con `from_json` (sección 4.3) |

En SQLite los tipos declarados son orientativos, así que un valor que no encaja con su tipo puede fallar al leerlo. Django escribe tipos coherentes, de modo que con este esquema no pasa.

## 4. SQL analítico (demo 2)

Todas las consultas de `demo/run_02_analytics.py` se ejecutan directamente sobre el fichero adjuntado.

### 4.1 QUALIFY

QUALIFY filtra sobre una función de ventana igual que HAVING filtra sobre un agregado. Una fila por vídeo, la más reciente:

```sql
SELECT v.title, s.taken_on, s.view_count
FROM yt.catalog_video v
JOIN yt.catalog_videostats s ON s.video_id = v.id
QUALIFY row_number() OVER (PARTITION BY v.id ORDER BY s.taken_on DESC) = 1
```

SQLite tiene funciones de ventana, pero necesita meter esto en una subconsulta con un `WHERE rn = 1` exterior.

### 4.2 Cambio dentro de una ventana

`view_count - lag(view_count, 29) OVER (PARTITION BY video_id ORDER BY taken_on)` da las visualizaciones ganadas en 30 días. Supone una fila por día. Un hueco en la sincronización diaria haría que el desplazamiento abarcara más días, así que con datos reales comprueba primero los huecos, o une por fechas.

### 4.3 De texto JSON a listas

```sql
SELECT unnest(from_json(tags, '["VARCHAR"]')) AS tag FROM yt.catalog_video
```

`from_json` con la estructura `["VARCHAR"]` devuelve una lista `VARCHAR[]`. `unnest` la convierte en una fila por elemento. A partir de ahí es un `GROUP BY` normal. En SQLite haría falta `json_each` en un join.

### 4.4 PIVOT

```sql
PIVOT (SELECT year(published) AS year, <tramo de duración> AS length FROM yt.catalog_video)
ON length IN ('short', 'under_10m', '10m_plus')
USING count(*)
GROUP BY year
```

`IN (...)` fija qué columnas salen y en qué orden. Sin él, DuckDB crea una columna por cada valor que encuentre, ordenadas.

### 4.5 GROUP BY ALL, FILTER, arg_max y listas ordenadas

- `GROUP BY ALL` agrupa por todas las columnas seleccionadas que no son agregados.
- `count(*) FILTER (WHERE caption = 1)` cuenta un subconjunto dentro del mismo grupo.
- `arg_max(title, views)` devuelve el título con el máximo de visualizaciones. Sobre el histórico, `arg_max(view_count, taken_on)` da la última cifra sin ventana.
- `list(v.id ORDER BY i.position)[1:3]` construye una lista en el orden de la lista de reproducción y la corta. Las listas empiezan en 1.

### 4.6 Salida determinista

Los tests comparan byte a byte los informes de las demos 1 y 2. Por eso cada `ORDER BY` acaba en una clave única, como `v.id`, `tag` o `playlist`: en un motor paralelo, los empates salen en cualquier orden. La primera ejecución de la CI falló justo por eso.

## 5. Formatos, tamaño y velocidad (demo 3)

La demo 3 escribe una tabla de estadísticas de 2.000.000 de filas en un SQLite temporal, a través de la extensión sqlite de DuckDB en modo escritura. Copia la tabla a un fichero DuckDB y a Parquet (zstd), y hace la misma pregunta de cuatro maneras: visualizaciones y me gusta por año.

| Formato | Tamaño (MiB) |
| --- | --- |
| SQLite (por filas) | 83,4 |
| Fichero DuckDB (por columnas) | 18,3 |
| Parquet, zstd (por columnas) | 13,5 |

| Motor | Tiempo (ms) |
| --- | --- |
| Módulo `sqlite3` de Python sobre el SQLite | 1.267 |
| DuckDB sobre el SQLite adjuntado | 176 |
| DuckDB sobre su propia tabla | 39 |
| DuckDB sobre Parquet | 55 |

Los tiempos son el mejor de tres, con DuckDB 2.0.0 en un runner de GitHub Actions. Dependen de la máquina, así que los tests solo comprueban que los cuatro motores coinciden.

Aquí se ven dos efectos distintos:

1. **El motor.** DuckDB recorriendo el fichero SQLite es unas 7 veces más rápido que el propio SQLite. Lee las mismas páginas, pero agrega vectores en paralelo.
2. **El almacenamiento.** La tabla de DuckDB y Parquet leen solo las cuatro columnas que necesita la consulta, y esas columnas van comprimidas. Eso suma otras 3 o 4 veces.

En la práctica, adjunta el SQLite de la app para preguntas puntuales. Para trabajo pesado y repetido, copia una vez con `COPY ... TO 'x.parquet'` o `CREATE TABLE ... AS`.

## 6. DuckDB 2.0 en Python

Dos cambios rompieron código escrito para 1.x. La CI detectó los dos.

1. **Las relaciones ya no tienen `fetchone()`.** `con.sql(...)` devuelve una relación, que es una consulta perezosa. No guarda resultado, así que cada lectura vuelve a ejecutar la consulta, y la 2.0 le quitó `fetchone()`. Usa `fetchall()` o `limit(1).fetchall()`.
2. **Un resultado abierto bloquea la conexión.** `con.execute(...).fetchone()` lee una fila y deja abierto el resto del resultado. La siguiente consulta en esa conexión lanza `ResourceInUseException`. Lee todo con `fetchall()`, o usa `con.cursor()` para un segundo flujo.

`con.execute("SELECT count(*) ...").fetchall()[0][0]` funciona en las dos versiones.

## 7. MCP

El Model Context Protocol conecta un modelo con herramientas. Un **cliente** (Claude Code, Claude Desktop, un agente) se conecta a un **servidor**, lista sus herramientas y las llama con argumentos JSON. El servidor ejecuta cada llamada y devuelve el resultado. Con el transporte **stdio**, el cliente arranca el servidor como proceso hijo y habla con él por stdin y stdout, así que no hay ningún puerto escuchando.

El modelo ve el nombre, la descripción y el esquema de argumentos de cada herramienta, y decide cuándo llamarla. Esas descripciones forman parte del prompt, así que escríbelas con el mismo cuidado que el código.

## 8. DuckDB como servidor MCP (demo 4)

[duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp) es una extensión de la comunidad: `INSTALL duckdb_mcp FROM community`. En modo servidor expone una sesión de DuckDB a un cliente MCP.

`.mcp.json`, en la raíz del repositorio, registra el servidor para Claude Code:

```json
{"mcpServers": {"youtube-duckdb": {"command": "duckdb", "args": ["-init", "demo/mcp/init-server.sql"]}}}
```

La CLI de DuckDB ejecuta el fichero de inicio y después `mcp_server_start` toma stdin y stdout. El fichero hace cinco cosas:

1. Carga `duckdb_mcp` y `sqlite`, y adjunta la base de datos en solo lectura.
2. Crea vistas con nombres claros (`videos`, `video_stats`, `playlists`). También arreglan los tipos: `caption = 1 AS has_captions`, y `from_json(tags, ...)` como lista de verdad. El modelo ve nombres y tipos limpios en lugar de los de Django.
3. Publica tres herramientas con `mcp_publish_tool(nombre, descripción, sql, propiedades_json, obligatorios_json)`. El SQL es fijo. El modelo solo aporta los parámetros (`$n`, `$since`, `$video_id`, `$text`), que la extensión enlaza.
4. Bloquea la sesión (sección 9).
5. Arranca el servidor: `PRAGMA mcp_server_start('stdio', 'localhost', 0, '{"enable_export_tool": false}')`.

La extensión trae además herramientas propias. `query`, `describe`, `list_tables` y `database_info` son de solo lectura. `execute` (DDL y DML) viene desactivada por defecto, y `export` se desactiva aquí. Cada una se activa o desactiva en la configuración del servidor con `enable_<herramienta>_tool`, o todas a la vez con `builtin_tools`.

`tests/test_mcp.py` ejecuta en la CI todas las sentencias del fichero de inicio salvo la última. Eso cubre la instalación, las vistas, las tres herramientas y el bloqueo. Arrancar el servidor y llamar a las herramientas es la parte en directo de la demo. Necesita un cliente, así que la CI no la cubre.

## 9. Cerrarlo bien

Todo lo que lee el modelo, incluidos los datos de la base, puede intentar dirigir qué herramientas llama. Por eso el servidor no debe darle más de lo que pide la tarea:

| Capa | Ajuste | Qué impide |
| --- | --- | --- |
| 1 | `ATTACH ... (READ_ONLY)` | Escribir en el SQLite desde esta sesión |
| 2 | Herramientas con SQL fijo | Que el modelo cambie lo que hace una herramienta |
| 3 | `execute` desactivada (por defecto), `"enable_export_tool": false` | DDL, DML y exportar ficheros con las herramientas propias |
| 4 | `SET enable_external_access = false` | Leer o escribir otros ficheros desde SQL, como `read_csv('/etc/passwd')` |
| 5 | `SET lock_configuration = true` | Que un `SET` posterior deshaga 1-4; el test comprueba que el rechazo menciona el bloqueo |

El orden importa. Haz el `ATTACH` y carga las extensiones antes de desactivar el acceso externo, y bloquea lo último.

## 10. DuckDB como cliente MCP (demo 5, opcional)

La misma extensión puede llamar a otros servidores MCP desde SQL. `demo/mcp/client.sql` adjunta por stdio el servidor `youtube_mcp` de youtube_ML (Node), lista sus herramientas y guarda una respuesta de `get_channel_info` como tabla. Los comandos que arrancan servidores se rechazan salvo que estén en `allowed_mcp_commands` (para URLs, `allowed_mcp_urls`). El modo cliente no funciona en Windows. La CI no ejecuta esta demo, porque necesita el servidor Node compilado y una clave de API.

## 11. Límites y siguientes pasos

- **Un solo escritor.** DuckDB admite un proceso escritor por fichero. Leer el SQLite de la app en solo lectura evita conflictos con Django. Una copia en DuckDB o Parquet evita leer mientras escribe la sincronización.
- **El histórico diario necesita ejecuciones diarias.** `lag(..., 29)` supone que no hay huecos (sección 4.2).
- **Datos reales.** Todas las cifras de la presentación vienen de la muestra sintética. Los mismos scripts funcionan sobre el fichero real cuando `sync_youtube` lo ha rellenado.

## Fuentes

- [Documentación de DuckDB 2.0](https://duckdb.org/docs/2.0/sql/introduction)
- [duckdb/duckdb](https://github.com/duckdb/duckdb)
- [Extensión duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp) y su [repositorio](https://github.com/teaguesterling/duckdb_mcp)
- [youtube_ML](https://github.com/olonok69/youtube_ML): `docs/database.md` para las tablas y la sincronización
