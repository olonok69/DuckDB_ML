# Guía del presentador

Esta guía sigue `docs/DuckDB_MCP.pptx` diapositiva a diapositiva, para grabar el vídeo. Las notas de cada diapositiva tienen el texto hablado, en inglés. Esta guía añade qué enseñar en pantalla, las señales para las partes en directo y cuánto tiempo dedicar. Total: unos 25 minutos, o dos vídeos con el corte después de la diapositiva 13. Hay versión en inglés: [Presenter_Guide_EN.md](Presenter_Guide_EN.md).

## Antes de grabar

- [ ] `uv sync`, y ejecuta las demos 1-3 una vez para que las extensiones estén instaladas y los informes al día.
- [ ] `uv run --group docs python docs/make_deck.py` si ha cambiado algún informe.
- [ ] La CLI de DuckDB en el PATH. `duckdb -init demo/mcp/init-server.sql` carga sin errores (Ctrl+C para salir).
- [ ] Claude Code abierto en el repositorio, `youtube-duckdb` aprobado, y `/mcp` lo muestra conectado.
- [ ] Decide qué datos enseñas. La muestra se puede enseñar sin problema. Para el canal real, ejecuta `sync_youtube` en youtube_ML esa mañana y cambia la ruta del `ATTACH` (guía de las demos, demo 4).
- [ ] Un terminal con letra grande, y un editor con `demo/run_02_analytics.py` y `demo/mcp/init-server.sql` abiertos.

## Diapositivas

| # | Diapositiva | Tiempo | En pantalla y señales |
| --- | --- | --- | --- |
| 1 | DuckDB and its MCP server, on a YouTube channel | 0:30 | Enlaza con el vídeo de la API de YouTube |
| 2 | From a SQLite file to questions in plain language | 0:45 | Menciona que todo funciona con la muestra, sin clave |
| 3 | DuckDB is SQLite's shape with an analyst's engine | 1:30 | |
| 4 | SQLite for the app, DuckDB for the questions | 1:00 | Insiste en que no lo sustituye |
| 5 | One SQLite file, written by Django, read by DuckDB | 1:30 | Opcional: enseña `catalog/sync.py` de youtube_ML durante 20 segundos |
| 6 | Six tables, two of them daily histories | 1:00 | |
| 7 | Query the SQLite file in place | 2:00 | **En directo:** `uv run python demo/run_01_attach_sqlite.py`, baja a las secciones 2 y 3 |
| 8 | Latest counts per video (QUALIFY) | 1:30 | **En directo:** `uv run python demo/run_02_analytics.py`, quédate en la sección 1 |
| 9 | Which tags carry the views | 1:30 | Sección 3 del mismo informe |
| 10 | Uploads per year and length (PIVOT) | 1:00 | Sección 4; cita las secciones 5-7 en una frase |
| 11 | 6x smaller as Parquet | 1:00 | **En directo (opcional):** `uv run python demo/run_03_parquet.py`, unos 10 segundos |
| 12 | 23x faster on Parquet than in SQLite | 1:30 | Tus tiempos no serán los de la diapositiva; dilo |
| 13 | Two API changes the tests caught | 1:00 | Punto natural de corte si son dos vídeos |
| 14 | MCP lets a model call tools | 1:30 | Enlaza con youtube_mcp del vídeo anterior |
| 15 | One SQL file turns DuckDB into a server | 2:00 | **Enseña** `init-server.sql` en el editor, de arriba abajo |
| 16 | Five layers between the model and your data | 1:30 | |
| 17 | Questions to ask Claude about the channel | 4:00 | **En directo:** ver abajo |
| 18 | DuckDB can call MCP servers too | 1:00 | Enseña `client.sql`; ejecútalo solo si youtube_mcp está compilado |
| 19 | Keep SQLite for the app; point DuckDB at it | 0:45 | |

## La parte MCP en directo (diapositiva 17)

Cambia a Claude Code y pregunta, de una en una. Las preguntas pueden ir en español:

1. "¿Qué cinco vídeos han ganado más visualizaciones en el último mes?" Lo esperable es la herramienta propia `query` con un `lag` sobre `video_stats`. Despliega la llamada para enseñar el SQL que escribe Claude.
2. "Enséñame el histórico diario del vídeo de DuckDB más visto." Lo esperable es `search_videos` con `duckdb` y después `video_history`. Son nuestras herramientas fijas: señala que solo cambian los parámetros.
3. "¿Qué tienen en común los vídeos sobre agentes?" Pregunta abierta. Enseña cómo el modelo elige entre herramientas.
4. Para enseñar el cierre: "Cambia la configuración para permitir el acceso externo." La llamada debería fallar: `query` es de solo lectura y, detrás, la configuración está bloqueada. Lee el error en voz alta, y pruébalo una vez antes de grabar, porque el mensaje exacto lo da la extensión.

Si una llamada falla, sigue. El rechazo forma parte de la historia de la diapositiva 16.

## Después de grabar

- Pon el enlace del repositorio y el de youtube_ML en la descripción del vídeo.
- Si enseñaste el canal real, dilo en la descripción, y también que las diapositivas usan la muestra sintética.
