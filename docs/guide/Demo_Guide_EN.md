# Demo guide

This guide walks through each demo: how to run it, what each section of its report shows, and where that is in the code. Concepts are in the [technical guide](Technical_Guide_EN.md).

Run everything from the repository root after `uv sync`. Every Python demo takes `--db PATH` (default `data/sample.sqlite3`) and `--out DIR` (default `demo/output/`), and prints its report as well as saving it.

## Shared code: `demo/common.py`

- `connect(db)` opens an in-memory DuckDB, loads the sqlite extension (installing it the first time), and attaches the file as `yt`, read-only.
- `Report` writes plain-text reports: `section()`, `say()`, `sql()` (indented SQL) and `table()`, which formats query results with fixed column widths, so reports compare line by line across DuckDB versions. Integers get thousands separators, except columns named `year`, `position` or `minutes`.

## Demo 1: attach SQLite (`demo/run_01_attach_sqlite.py`)

```text
uv run python demo/run_01_attach_sqlite.py
```

| Report section | What it shows | Code |
| --- | --- | --- |
| 1. Attach | `duckdb_databases()`: `memory` (DuckDB) and `yt` (sqlite, read-only) | `connect()` |
| 2. The tables | Row counts of the six `catalog_*` tables (120 videos, 10,800 stats rows) | `CATALOG` list |
| 3. Types | `DESCRIBE` on five columns: `published` is `TIMESTAMP`, `caption` `BIGINT`, `tags` `VARCHAR` | |
| 4. Plain SQL | Five newest videos, with `from_json` turning tags into lists | |
| 5. Join | Videos per playlist with first and last upload, across three tables | |

## Demo 2: analytics (`demo/run_02_analytics.py`)

```text
uv run python demo/run_02_analytics.py
```

The queries are in the `QUERIES` list, each with a title and a one-line note. The report prints the SQL and then the result.

| # | Query | Feature | Read the result |
| --- | --- | --- | --- |
| 1 | Latest counts per video | `QUALIFY row_number()` | The top video on the sample has 65,111 views |
| 2 | Views gained in 30 days | `lag(view_count, 29)` | Recent uploads gain most; old ones have flattened |
| 3 | Tags that carry the views | `from_json` + `unnest`, `HAVING count(*) >= 5` | `mcp` and `tools` lead at 7,288 average views |
| 4 | Uploads per year and length | `PIVOT ... ON length IN (...)` | Videos over 10 minutes dominate every year |
| 5 | Language and year | `GROUP BY ALL`, `FILTER`, `median` | Captions on about 60% of videos |
| 6 | Best video per playlist | `arg_max`, `list(... ORDER BY)[1:3]` | First three ids in playlist order |
| 7 | Channel growth by week | `date_trunc` in a CTE, then `lag` | Weekly growth slows as the catalog ages |

Every `ORDER BY` ends with a unique key, so the report is identical on every run. `tests/test_demos.py` compares it with `demo/output/02_analytics.txt` and prints a unified diff if it changes. When you change a query on purpose, rerun the demo and commit the new report.

## Demo 3: formats (`demo/run_03_parquet.py`)

```text
uv run python demo/run_03_parquet.py              # 2,000,000 rows, about 10 s
uv run python demo/run_03_parquet.py --rows 20000 # what the test runs
```

Scratch files go to `demo/output/scratch/`, which git ignores.

| Report section | What happens |
| --- | --- |
| 1. A larger table | `ATTACH ... AS big (TYPE sqlite)` without `READ_ONLY`, then `CREATE TABLE big.videostats AS SELECT ... FROM range(N)`. DuckDB writes into SQLite. Values come from `hash()`, so they are fixed for a given DuckDB version. |
| 2. The question | Views and likes per year, asked four ways: the `sqlite3` module, DuckDB over the SQLite file, a DuckDB table (`CREATE TABLE bigduck.videostats AS FROM big.videostats`), and `read_parquet` after `COPY ... TO (FORMAT parquet, COMPRESSION zstd)`. The report states whether all four agree. |
| 3. Sizes | File sizes in MiB |
| 4. Timings | Best of 3 per engine. Lines tagged `[timing]` depend on the machine. |

`taken_on` is cast with `::DATE` in the question, because a DATE written into SQLite comes back as text.

## Demo 4: MCP server (`demo/mcp/init-server.sql`)

Prerequisites: the [DuckDB CLI](https://duckdb.org/docs/installation/) on your PATH, and Claude Code.

1. Open Claude Code in the repository root. It reads `.mcp.json` and offers the `youtube-duckdb` server. Approve it.
2. Check that the server is connected (`/mcp` in Claude Code). It should list `top_videos`, `video_history` and `search_videos`, plus the built-in `query`, `describe`, `list_tables` and `database_info`.
3. Ask the questions on the "Live" slide. Expand each tool call to show the SQL or the parameters.

To serve the real channel, change the `ATTACH` path in `init-server.sql` to `'../youtube_ML/db.sqlite3'`.

If the server does not start, run `duckdb -init demo/mcp/init-server.sql` in a terminal. It should load quietly and then wait on stdin. An error in the init file shows up there. `uv run pytest tests/test_mcp.py` runs the same file up to the server start.

## Demo 5: MCP client (`demo/mcp/client.sql`, optional)

1. In youtube_ML: `cd youtube_mcp && npm install && npm run build`, with the API key available as that server expects (`youtube_ML/docs/mcp-server.md`).
2. From this repository's root: `duckdb -init demo/mcp/client.sql`.
3. The output lists youtube_mcp's tools and prints the `get_channel_info` answer stored in `channel_live`.

## Tests and CI

| Test | What it checks |
| --- | --- |
| `test_report_matches_committed_output` | Demos 1 and 2 reproduce `demo/output/` byte for byte |
| `test_parquet_demo_engines_agree` | Demo 3 at 20,000 rows: all four engines agree |
| `test_sample_is_reproducible` | `make_sample.py` rebuilds the same rows (SQL dump compare) |
| `test_server_script_until_start` | The MCP init file runs up to `mcp_server_start`; the views answer; a later `SET` is refused by the lock |

CI (`.github/workflows/ci.yml`) runs ruff and pytest with `REQUIRE_MCP=1`, so a missing duckdb_mcp fails instead of skipping. It then runs demo 3 at full size and builds the deck.
