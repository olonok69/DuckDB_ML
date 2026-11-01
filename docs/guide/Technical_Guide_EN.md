# DuckDB and its MCP server: technical guide

This guide explains what the demos in this repository show and why it works. It is written for an engineer who knows SQL and Python and has not used DuckDB. The [demo guide](Demo_Guide_EN.md) walks through the code. The [presenter guide](Presenter_Guide_EN.md) follows the deck slide by slide.

Numbers come from the reports in `demo/output/`. The data is the synthetic sample in `data/sample.sqlite3` unless a section says otherwise.

## 1. What DuckDB is

DuckDB is an analytical SQL database that runs inside your process. You add it with `uv add duckdb` and open it with `duckdb.connect()`. There is no server to start and no port to secure. The database is a single file, or memory.

That is the same packaging as SQLite. The engine is different:

| | SQLite | DuckDB |
| --- | --- | --- |
| Storage | Rows: a row's values sit together | Columns: a column's values sit together |
| Execution | One row at a time | Vectors of values, on every core |
| Built for | Many small reads and writes (an application) | Scans, joins and aggregates over many rows (analysis) |
| Writers | One at a time | One process at a time |

The two fit together. The Django app in youtube_ML keeps writing SQLite, which suits it. DuckDB reads the same file for analysis.

### 1.1 DuckDB 2.0

The demos target the 2.0 LTS line: `pyproject.toml` pins `duckdb>=2.0,<3`, and CI runs every demo on 2.0.0. Two changes in the Python API affected this code (section 6).

## 2. The data

### 2.1 From the YouTube API to SQLite

youtube_ML's `manage.py sync_youtube` reads the channel with an API key. It never writes to YouTube. It upserts six tables into `db.sqlite3`:

| Table | One row per | Notes |
| --- | --- | --- |
| `catalog_channel` | channel | |
| `catalog_channelsnapshot` | channel and day | subscribers, views, video count |
| `catalog_video` | public upload | `tags` and `topics` are JSON text |
| `catalog_videostats` | video and day | views, likes, comments |
| `catalog_playlist` | playlist | |
| `catalog_playlistitem` | video in a playlist | `video_id` is text, not a foreign key |

A run on a day that already has rows overwrites that day. A run on a new day adds rows. Run it daily and the two `*stats`/`*snapshot` tables become time series.

### 2.2 The sample

`data/sample.sqlite3` uses the same DDL (`data/schema.sql`, copied from the Django migration), filled with invented data. It holds 120 videos, 90 days of statistics (10,800 rows) and 8 playlists, from seed 7. `data/make_sample.py` rebuilds it with the same rows, and a test compares the SQL dumps. Views follow a saturating curve with noise, so the window queries have something to find. Nothing in the sample is real channel data.

To run on the real channel, pass `--db ../youtube_ML/db.sqlite3` or set `YOUTUBE_DB`.

## 3. Reading SQLite in place (demo 1)

```sql
INSTALL sqlite; LOAD sqlite;
ATTACH 'db.sqlite3' AS yt (TYPE sqlite, READ_ONLY);
SELECT count(*) FROM yt.catalog_video;
```

`INSTALL` downloads the extension once, from the DuckDB repository. `ATTACH` makes the file a catalog called `yt`. Nothing is copied: each query reads the SQLite pages it needs. `READ_ONLY` means this connection cannot change the file, which matters when the Django app or the sync owns it.

DuckDB types the columns from the declared SQLite schema:

| SQLite declared type | DuckDB type | Consequence |
| --- | --- | --- |
| `varchar`, `text` | `VARCHAR` | |
| `datetime` | `TIMESTAMP` | `year()`, `date_trunc()` work directly |
| `integer`, `bigint` | `BIGINT` | |
| `bool` | `BIGINT` | compare with `= 1`, or cast |
| JSON in `text` | `VARCHAR` | parse with `from_json` (section 4.3) |

Declared types in SQLite are hints, so a value that does not fit its declared type can still fail at read time. Django writes consistent types, so that does not happen with this schema.

## 4. Analytics SQL (demo 2)

Every query in `demo/run_02_analytics.py` runs directly against the attached file.

### 4.1 QUALIFY

QUALIFY filters on a window function the way HAVING filters on an aggregate. One row per video, the newest:

```sql
SELECT v.title, s.taken_on, s.view_count
FROM yt.catalog_video v
JOIN yt.catalog_videostats s ON s.video_id = v.id
QUALIFY row_number() OVER (PARTITION BY v.id ORDER BY s.taken_on DESC) = 1
```

SQLite supports window functions, but needs this inside a subquery with an outer `WHERE rn = 1`.

### 4.2 Change over a window

`view_count - lag(view_count, 29) OVER (PARTITION BY video_id ORDER BY taken_on)` gives views gained over 30 days. It assumes one row per day. A gap in the daily sync would make the offset span more days, so on real data check for gaps first, or join on dates instead.

### 4.3 JSON text to lists

```sql
SELECT unnest(from_json(tags, '["VARCHAR"]')) AS tag FROM yt.catalog_video
```

`from_json` with the structure `["VARCHAR"]` returns a `VARCHAR[]` list. `unnest` turns it into one row per element. From there it is an ordinary `GROUP BY`. SQLite would need `json_each` in a join.

### 4.4 PIVOT

```sql
PIVOT (SELECT year(published) AS year, <length bucket> AS length FROM yt.catalog_video)
ON length IN ('short', 'under_10m', '10m_plus')
USING count(*)
GROUP BY year
```

`IN (...)` fixes the column order and set. Without it, DuckDB makes a column for each value it finds, in sorted order.

### 4.5 GROUP BY ALL, FILTER, arg_max, ordered lists

- `GROUP BY ALL` groups by every selected column that is not an aggregate.
- `count(*) FILTER (WHERE caption = 1)` counts a subset inside the same group.
- `arg_max(title, views)` returns the title at the maximum views. With the history table, `arg_max(view_count, taken_on)` gives the latest count without a window.
- `list(v.id ORDER BY i.position)[1:3]` builds a list in playlist order and slices it. Lists are 1-indexed.

### 4.6 Deterministic output

The tests compare the demo 1 and 2 reports byte for byte. Every `ORDER BY` therefore ends with a unique key, such as `v.id`, `tag` or `playlist`, because ties come back in any order on a parallel engine. The first CI run failed on exactly that.

## 5. Formats, size and speed (demo 3)

Demo 3 writes a 2,000,000-row statistics table into a scratch SQLite file, through DuckDB's sqlite extension in write mode. It copies the table into a DuckDB file and into Parquet (zstd), and asks one question four ways: views and likes per year.

| Format | Size (MiB) |
| --- | --- |
| SQLite (row store) | 83.4 |
| DuckDB file (columnar) | 18.3 |
| Parquet, zstd (columnar) | 13.5 |

| Engine | Time (ms) |
| --- | --- |
| Python `sqlite3` on the SQLite file | 1,267 |
| DuckDB over the attached SQLite file | 176 |
| DuckDB on its own table | 39 |
| DuckDB on Parquet | 55 |

Timings are the best of three runs, from DuckDB 2.0.0 on a GitHub Actions runner. They depend on the machine, so the tests check only that all four engines agree.

Two separate effects show here:

1. **Engine.** DuckDB scanning the SQLite file is about 7x faster than SQLite itself. It reads the same pages but aggregates vectors in parallel.
2. **Storage.** DuckDB's own table and Parquet read only the four columns the query needs, and those columns are compressed. That adds another 3-4x.

The practical rule: attach the app's SQLite for ad-hoc questions. For repeated heavy work, copy once with `COPY ... TO 'x.parquet'` or `CREATE TABLE ... AS`.

## 6. DuckDB 2.0 in Python

Two changes broke code written against 1.x. CI caught both.

1. **Relations have no `fetchone()`.** `con.sql(...)` returns a relation, which is a lazy query. It keeps no result, so each fetch runs the query again, and 2.0 removed `fetchone()` from it. Use `fetchall()` or `limit(1).fetchall()`.
2. **An open result blocks the connection.** `con.execute(...).fetchone()` reads one row and leaves the rest of the result open. The next query on that connection raises `ResourceInUseException`. Read everything with `fetchall()`, or use `con.cursor()` for a second stream.

`con.execute("SELECT count(*) ...").fetchall()[0][0]` works on both versions.

## 7. MCP

The Model Context Protocol connects a model to tools. A **client** (Claude Code, Claude Desktop, an agent) connects to a **server**, lists its tools, and calls them with JSON arguments. The server runs each call and returns the result. With the **stdio** transport the client starts the server as a child process and talks over stdin and stdout, so nothing listens on a port.

The model sees each tool's name, description and argument schema, and decides when to call it. Those descriptions are part of the prompt, so write them as carefully as code.

## 8. DuckDB as an MCP server (demo 4)

[duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp) is a community extension: `INSTALL duckdb_mcp FROM community`. In server mode it exposes a DuckDB session to an MCP client.

`.mcp.json` at the repository root registers the server for Claude Code:

```json
{"mcpServers": {"youtube-duckdb": {"command": "duckdb", "args": ["-init", "demo/mcp/init-server.sql"]}}}
```

The DuckDB CLI runs the init file and then `mcp_server_start` takes over stdin and stdout. The file does five things:

1. Loads `duckdb_mcp` and `sqlite`, and attaches the database read-only.
2. Creates views with plain names (`videos`, `video_stats`, `playlists`). They also fix the types: `caption = 1 AS has_captions`, and `from_json(tags, ...)` as a real list. The model sees clean names and types instead of Django's.
3. Publishes three tools with `mcp_publish_tool(name, description, sql, properties_json, required_json)`. The SQL is fixed. The model supplies only the parameters (`$n`, `$since`, `$video_id`, `$text`), which the extension binds.
4. Locks the session (section 9).
5. Starts the server: `PRAGMA mcp_server_start('stdio', 'localhost', 0, '{"enable_export_tool": false}')`.

The extension also offers built-in tools. `query`, `describe`, `list_tables` and `database_info` are read-only. `execute` (DDL and DML) is off by default, and `export` is switched off here. Each built-in can be turned on or off in the server config with `enable_<tool>_tool`, or all at once with `builtin_tools`.

`tests/test_mcp.py` runs every statement of the init file except the last one in CI. That covers the install, the views, the three tool definitions and the lock. Starting the server and calling the tools is the live part of the demo. It needs a client, so CI does not cover it.

## 9. Locking it down

Anything the model reads, including data in the database, can try to steer which tools it calls. So the server should give it no more than the task needs:

| Layer | Setting | What it prevents |
| --- | --- | --- |
| 1 | `ATTACH ... (READ_ONLY)` | Writes to the SQLite file through this session |
| 2 | Fixed-SQL tools | The model changing what a tool does |
| 3 | `execute` off (default), `"enable_export_tool": false` | DDL, DML and file export through built-in tools |
| 4 | `SET enable_external_access = false` | Reading or writing other files from SQL, such as `read_csv('/etc/passwd')` |
| 5 | `SET lock_configuration = true` | Any later `SET` undoing 1-4; the test checks the refusal mentions the lock |

The order matters. Run the `ATTACH` and the extension loads before you disable external access, and lock last.

## 10. DuckDB as an MCP client (demo 5, optional)

The same extension can call other MCP servers from SQL. `demo/mcp/client.sql` attaches youtube_ML's own `youtube_mcp` server (Node) over stdio, lists its tools, and stores one `get_channel_info` answer as a table. Commands that start servers are denied unless they are in `allowed_mcp_commands` (URLs: `allowed_mcp_urls`). Client mode does not run on Windows. CI does not run this demo, because it needs the Node server built and an API key.

## 11. Limits and next steps

- **One writer.** DuckDB allows one writing process per database file. Reading the app's SQLite read-only avoids conflicts with Django. A copy in DuckDB or Parquet avoids reading while the sync writes.
- **Daily history needs daily runs.** `lag(..., 29)` assumes no gaps (section 4.2).
- **Real data.** Every number in the deck comes from the synthetic sample. The same scripts run on the real file once `sync_youtube` has filled it.

## Sources

- [DuckDB 2.0 documentation](https://duckdb.org/docs/2.0/sql/introduction)
- [duckdb/duckdb](https://github.com/duckdb/duckdb)
- [duckdb_mcp community extension](https://duckdb.org/community_extensions/extensions/duckdb_mcp) and its [repository](https://github.com/teaguesterling/duckdb_mcp)
- [youtube_ML](https://github.com/olonok69/youtube_ML): `docs/database.md` for the tables and the sync
