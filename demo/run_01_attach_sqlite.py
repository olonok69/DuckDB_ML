"""Demo 1: query youtube_ML's SQLite file in place.

DuckDB is a library (`uv add duckdb`): no server, no import step. The sqlite
extension attaches db.sqlite3 read-only and DuckDB plans the queries itself.

    uv run python demo/run_01_attach_sqlite.py [--db ../youtube_ML/db.sqlite3]
"""

from common import Report, connect, parse_args

CATALOG = ["catalog_channel", "catalog_channelsnapshot", "catalog_video", "catalog_videostats",
           "catalog_playlist", "catalog_playlistitem"]


def main() -> None:
    args = parse_args(__doc__.splitlines()[0])
    con = connect(args.db)
    r = Report("01_attach_sqlite", "Demo 1: DuckDB reads the SQLite file in place")

    r.section("1. Attach")
    r.sql("INSTALL sqlite; LOAD sqlite;\nATTACH 'db.sqlite3' AS yt (TYPE sqlite, READ_ONLY);")
    r.table(con.sql("SELECT database_name, type, readonly FROM duckdb_databases() "
                    "WHERE NOT internal ORDER BY database_name"))

    r.section("2. The tables youtube_ML writes")
    counts = [(t, con.execute(f"SELECT count(*) FROM yt.{t}").fetchall()[0][0]) for t in CATALOG]
    r.table(counts, ["table", "rows"])

    r.section("3. How DuckDB types the SQLite columns")
    r.say("SQLite stores almost everything as text or integer. The scanner maps the declared types:")
    r.table(con.sql("SELECT column_name, column_type FROM (DESCRIBE yt.catalog_video) "
                    "WHERE column_name IN ('id','published','duration_seconds','caption','tags')"))

    r.section("4. Plain SQL over the attached file")
    query = """
SELECT title,
       published::DATE                    AS published,
       duration_seconds // 60             AS minutes,
       from_json(tags, '["VARCHAR"]')     AS tags
FROM yt.catalog_video
ORDER BY published DESC
LIMIT 5"""
    r.sql(query)
    r.table(con.sql(query))

    r.section("5. Join across tables")
    query = """
SELECT p.title AS playlist, count(*) AS videos,
       min(v.published)::DATE AS first, max(v.published)::DATE AS last
FROM yt.catalog_playlist p
JOIN yt.catalog_playlistitem i ON i.playlist_id = p.id
JOIN yt.catalog_video v ON v.id = i.video_id
GROUP BY ALL
ORDER BY videos DESC, playlist"""
    r.sql(query)
    r.table(con.sql(query))

    r.save(args.out)


if __name__ == "__main__":
    main()
