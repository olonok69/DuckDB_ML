# DuckDB and its MCP server, on a YouTube channel

[DuckDB](https://github.com/duckdb/duckdb) is an analytical SQL database that runs inside your process: `uv add duckdb`, no server. This repository shows it on real-shaped data: the YouTube channel that [youtube_ML](https://github.com/olonok69/youtube_ML) stores in `db.sqlite3`. Then the same database is served to Claude through the [duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp) community extension, so you can ask questions about the channel in plain language.

| Demo | What it shows | Report |
| --- | --- | --- |
| 1. Attach SQLite | `ATTACH 'db.sqlite3' (TYPE sqlite, READ_ONLY)`, typed columns, joins, nothing copied | `demo/output/01_attach_sqlite.txt` |
| 2. Analytics | `QUALIFY`, `lag`, JSON tags to lists with `unnest`, `PIVOT`, `GROUP BY ALL`, `FILTER`, `arg_max`, `list(... ORDER BY)` | `demo/output/02_analytics.txt` |
| 3. Parquet | One question on SQLite, DuckDB over SQLite, a DuckDB table and Parquet, with sizes and timings | `demo/output/03_parquet.txt` |
| 4. MCP server | Views and three fixed-SQL tools over the channel, read-only, configuration locked, served on stdio to Claude Code | `demo/mcp/init-server.sql`, `.mcp.json` |
| 5. MCP client (optional) | DuckDB calls youtube_ML's own MCP server and stores the answer as a table | `demo/mcp/client.sql` |

## Run it

With Python 3.12 and [uv](https://docs.astral.sh/uv/):

```text
uv sync
uv run python demo/run_01_attach_sqlite.py
uv run python demo/run_02_analytics.py
uv run python demo/run_03_parquet.py
uv run pytest -q
```

The first run downloads the `sqlite` extension from the DuckDB repository.

## The data

`data/sample.sqlite3` is synthetic: 120 invented videos with 90 days of daily stats, 8 playlists, seed 7, and the same tables as youtube_ML (`data/schema.sql`). `uv run python data/make_sample.py` rebuilds it byte for byte. The demos and the tests use it, so nobody needs an API key.

For the real channel, fill youtube_ML's database and point the demos at it:

```text
cd ../youtube_ML && uv run python manage.py migrate && uv run python manage.py sync_youtube
cd ../duckdb_ML && uv run python demo/run_02_analytics.py --db ../youtube_ML/db.sqlite3
```

`YOUTUBE_DB=../youtube_ML/db.sqlite3` does the same for every demo. Real data stays in youtube_ML: `db.sqlite3` is ignored here.

## The MCP server (demo 4)

Install the [DuckDB CLI](https://duckdb.org/docs/installation/) so `duckdb` is on your PATH. `.mcp.json` registers the server for Claude Code in this folder; Claude Desktop takes the same `command` and `args`. Claude Code runs the server from the repository root, and the DuckDB CLI runs `demo/mcp/init-server.sql`:

1. Loads `duckdb_mcp` and `sqlite`, and attaches the database read-only.
2. Creates three views, `videos`, `video_stats` and `playlists`, so the model sees clear names.
3. Publishes three tools with fixed SQL: `top_videos(n, since)`, `video_history(video_id)`, `search_videos(text)`.
4. Turns off external file access and locks the configuration.
5. Starts the server on stdio. Built-in tools `query`, `describe`, `list_tables` and `database_info` are read-only; `execute` is off by default and `export` is switched off.

Try: "Which five videos gained the most views last month?" or "Show me the daily history of the top DuckDB video."

## The deck

```text
uv run --group docs python docs/make_deck.py
```

The slides quote the numbers in `demo/output/`, through `docs/report_tables.py`, so rerunning a demo and then the deck keeps them in step.

## Layout

| Path | Role |
| --- | --- |
| `data/` | Schema copied from youtube_ML, the sample builder and the sample |
| `demo/` | Demos 1-3 (`common.py` attaches the file and writes the reports), `mcp/` for demos 4-5, `output/` for the reports |
| `tests/` | Reruns demos 1-2 against `demo/output/`, checks demo 3 agrees across engines, rebuilds the sample, smoke-tests the MCP script |
| `.github/workflows/ci.yml` | ruff and pytest with uv. In CI the MCP smoke test must run, not skip |
| `docs/` | `make_deck.py` builds `DuckDB_MCP.pptx` (19 slides, speaker notes) from the reports in `demo/output/`; guides to come |
