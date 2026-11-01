"""Demo 3: the same question on SQLite, DuckDB and Parquet, with sizes and timings.

The sample is too small for timings to mean anything, so this demo first writes a
larger synthetic stats table (--rows, default 2,000,000) into a scratch SQLite
file, through DuckDB's sqlite extension. Then it asks one aggregate question four
ways and copies the table to a DuckDB file and to Parquet.

    uv run python demo/run_03_parquet.py [--rows 2000000]

Timings depend on the machine; the report marks them so the tests ignore them.
"""

import sqlite3
import time

import duckdb

from common import Report, _quote, connect, parse_args

QUESTION = """
SELECT year(taken_on::DATE) AS year, count(*) AS rows, sum(view_count) AS views, avg(like_count) AS avg_likes
FROM {table}
GROUP BY ALL
ORDER BY year"""


def timed(fn, repeat: int = 3) -> tuple[float, object]:
    best, result = float("inf"), None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        best = min(best, time.perf_counter() - start)
    return best, result


def main() -> None:
    args = parse_args(__doc__.splitlines()[0], **{"--rows": {"type": int, "default": 2_000_000}})
    scratch = args.out / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    big_sqlite, big_duckdb, big_parquet = scratch / "big.sqlite3", scratch / "big.duckdb", scratch / "big.parquet"
    for f in (big_sqlite, big_duckdb, big_parquet):
        f.unlink(missing_ok=True)

    r = Report("03_parquet", "Demo 3: SQLite, DuckDB and Parquet on the same table")
    con = connect(args.db)

    r.section("1. A larger stats table, written to SQLite by DuckDB")
    r.say(f"{args.rows:,} daily rows, spread over the sample's videos and the years 2023 to 2026. Seed fixed.")
    con.execute(f"ATTACH {_quote(big_sqlite)} AS big (TYPE sqlite)")
    build = f"""
CREATE TABLE big.videostats AS
SELECT row_number() OVER () AS id,
       DATE '2023-01-01' + (i % 1400)::INTEGER AS taken_on,
       (hash(i) % 100000)::BIGINT AS view_count,
       (hash(i * 7) % 4000)::BIGINT AS like_count,
       (hash(i * 13) % 600)::BIGINT AS comment_count,
       v.id AS video_id
FROM range({args.rows}) t(i)
JOIN (SELECT id, row_number() OVER (ORDER BY id) - 1 AS n FROM yt.catalog_video) v
  ON v.n = i % (SELECT count(*) FROM yt.catalog_video)"""
    r.sql(build)
    con.execute(build)
    con.execute("DETACH big")

    r.section("2. The question")
    r.sql(QUESTION.format(table="videostats"))

    lite = sqlite3.connect(big_sqlite)
    sqlite_sql = """
SELECT CAST(strftime('%Y', taken_on) AS INTEGER) AS year, count(*), sum(view_count), avg(like_count)
FROM videostats GROUP BY 1 ORDER BY 1"""
    t_sqlite, rows_sqlite = timed(lambda: lite.execute(sqlite_sql).fetchall())
    lite.close()

    con.execute(f"ATTACH {_quote(big_sqlite)} AS big (TYPE sqlite, READ_ONLY)")
    t_scan, rows_scan = timed(lambda: con.sql(QUESTION.format(table="big.videostats")).fetchall())

    con.execute(f"ATTACH {_quote(big_duckdb)} AS bigduck")
    con.execute("CREATE TABLE bigduck.videostats AS FROM big.videostats")
    t_native, rows_native = timed(lambda: con.sql(QUESTION.format(table="bigduck.videostats")).fetchall())

    con.execute(f"COPY big.videostats TO {_quote(big_parquet)} (FORMAT parquet, COMPRESSION zstd)")
    t_parquet, rows_parquet = timed(lambda: con.sql(QUESTION.format(table=f"read_parquet({_quote(big_parquet)})")).fetchall())
    con.execute("DETACH bigduck")

    same = all([tuple(a)[:3] == tuple(b)[:3] for a, b in zip(rows_sqlite, other)]
               and len(rows_sqlite) == len(other) for other in (rows_scan, rows_native, rows_parquet))
    r.say(f"All four engines return the same years, row counts and view sums: {'yes' if same else 'NO'}")
    r.table(con.sql(QUESTION.format(table=f"read_parquet({_quote(big_parquet)})")))

    r.section("3. Sizes on disk")
    sizes = [("SQLite (row store)", big_sqlite.stat().st_size), ("DuckDB file (columnar)", big_duckdb.stat().st_size),
             ("Parquet, zstd (columnar)", big_parquet.stat().st_size)]
    r.table([(name, round(size / 2**20, 1)) for name, size in sizes], ["format", "MiB"])

    r.section("4. Timings, best of 3 (machine-dependent) [timing]")
    r.say(f"[timing] DuckDB {duckdb.__version__}, Python sqlite3 {sqlite3.sqlite_version}")
    r.table([("sqlite3 module on the SQLite file", round(t_sqlite * 1000, 1)),
             ("DuckDB over the attached SQLite file", round(t_scan * 1000, 1)),
             ("DuckDB on its own table", round(t_native * 1000, 1)),
             ("DuckDB on Parquet", round(t_parquet * 1000, 1))], ["engine", "ms"])
    r.say("[timing] The SQLite scanner reads rows; DuckDB's own table and Parquet read only the four columns used.")

    r.save(args.out)


if __name__ == "__main__":
    main()
