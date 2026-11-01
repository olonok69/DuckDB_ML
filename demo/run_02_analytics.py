"""Demo 2: the analytics SQL that is awkward in SQLite and short in DuckDB.

Window functions with QUALIFY, JSON lists unnested, PIVOT, GROUP BY ALL, list
aggregates and arg_max, all straight over the attached SQLite file.

    uv run python demo/run_02_analytics.py [--db ../youtube_ML/db.sqlite3]
"""

from common import Report, connect, parse_args

QUERIES = [
    (
        "1. Latest counts per video (QUALIFY)",
        "One row per video from a daily history. SQLite needs a subquery or a CTE with "
        "row_number() and an outer WHERE; DuckDB filters on the window directly.",
        """
SELECT v.title, s.taken_on, s.view_count, s.like_count
FROM yt.catalog_video v
JOIN yt.catalog_videostats s ON s.video_id = v.id
QUALIFY row_number() OVER (PARTITION BY v.id ORDER BY s.taken_on DESC) = 1
ORDER BY s.view_count DESC, v.id
LIMIT 8""",
    ),
    (
        "2. Views gained in the last 30 days (window over the history)",
        "The difference between the newest row and the row 30 days earlier, per video.",
        """
WITH s AS (
    SELECT video_id, taken_on, view_count,
           view_count - lag(view_count, 29) OVER (PARTITION BY video_id ORDER BY taken_on) AS gained_30d
    FROM yt.catalog_videostats
)
SELECT v.title, v.published::DATE AS published, s.view_count, s.gained_30d
FROM s JOIN yt.catalog_video v ON v.id = s.video_id
WHERE s.taken_on = (SELECT max(taken_on) FROM yt.catalog_videostats)
ORDER BY s.gained_30d DESC NULLS LAST, v.id
LIMIT 8""",
    ),
    (
        "3. Which tags carry the views (JSON text to a list, then unnest)",
        "tags is JSON text in SQLite. from_json turns it into VARCHAR[]; unnest gives one row per tag.",
        """
WITH latest AS (
    SELECT video_id, arg_max(view_count, taken_on) AS views
    FROM yt.catalog_videostats GROUP BY ALL
)
SELECT tag, count(*) AS videos, avg(views)::BIGINT AS avg_views, sum(views) AS total_views
FROM (
    SELECT unnest(from_json(v.tags, '["VARCHAR"]')) AS tag, l.views
    FROM yt.catalog_video v JOIN latest l ON l.video_id = v.id
)
GROUP BY ALL
HAVING count(*) >= 5
ORDER BY avg_views DESC, tag
LIMIT 10""",
    ),
    (
        "4. Uploads per year and length (PIVOT)",
        "SQLite has no PIVOT; it needs one CASE expression per column.",
        """
PIVOT (
    SELECT year(published) AS year,
           CASE WHEN duration_seconds < 60 THEN 'short'
                WHEN duration_seconds < 600 THEN 'under_10m'
                ELSE '10m_plus' END AS length
    FROM yt.catalog_video
)
ON length IN ('short', 'under_10m', '10m_plus')
USING count(*)
GROUP BY year
ORDER BY year""",
    ),
    (
        "5. One summary row per language and year (GROUP BY ALL, FILTER)",
        "GROUP BY ALL groups by every column that is not an aggregate. FILTER counts a subset.",
        """
SELECT audio_language AS language, year(published) AS year,
       count(*) AS videos,
       count(*) FILTER (WHERE caption = 1) AS with_captions,
       round(median(duration_seconds) / 60, 1) AS median_minutes
FROM yt.catalog_video
GROUP BY ALL
ORDER BY language, year""",
    ),
    (
        "6. Each playlist's best video and its order (list and arg_max aggregates)",
        "arg_max picks the title at the highest view count; list(... ORDER BY) keeps the playlist order.",
        """
WITH latest AS (
    SELECT video_id, arg_max(view_count, taken_on) AS views
    FROM yt.catalog_videostats GROUP BY ALL
)
SELECT p.title AS playlist,
       arg_max(v.title, l.views) AS best_video,
       max(l.views) AS best_views,
       list(v.id ORDER BY i.position)[1:3] AS first_three_ids
FROM yt.catalog_playlist p
JOIN yt.catalog_playlistitem i ON i.playlist_id = p.id
JOIN yt.catalog_video v ON v.id = i.video_id
JOIN latest l ON l.video_id = v.id
GROUP BY ALL
ORDER BY best_views DESC, playlist""",
    ),
    (
        "7. Channel growth by week (date_trunc, window running change)",
        "Weekly last value of the channel snapshot and the change from the previous week.",
        """
WITH weekly AS (
    SELECT date_trunc('week', taken_on)::DATE AS week, arg_max(view_count, taken_on) AS views
    FROM yt.catalog_channelsnapshot
    GROUP BY ALL
)
SELECT week, views, views - lag(views) OVER (ORDER BY week) AS change
FROM weekly
ORDER BY week DESC
LIMIT 6""",
    ),
]


def main() -> None:
    args = parse_args(__doc__.splitlines()[0])
    con = connect(args.db)
    r = Report("02_analytics", "Demo 2: analytics over the attached SQLite file")
    for title, note, query in QUERIES:
        r.section(title)
        r.say(note)
        r.sql(query)
        r.table(con.sql(query))
    r.save(args.out)


if __name__ == "__main__":
    main()
