-- Demo 4: DuckDB as an MCP server over the channel database.
--
-- Claude Code starts this through .mcp.json at the repository root:
--     duckdb -init demo/mcp/init-server.sql
-- The DuckDB CLI runs this file, then the last line hands stdin/stdout to MCP.
-- Paths are relative to the repository root. Change the ATTACH path to
-- '../youtube_ML/db.sqlite3' to serve the real channel.

INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;
INSTALL sqlite;
LOAD sqlite;

-- 1. The data: the SQLite file, read-only. Nothing is copied.
ATTACH 'data/sample.sqlite3' AS yt (TYPE sqlite, READ_ONLY);

-- 2. Friendly views, so the model sees three clear tables instead of Django's names.
CREATE VIEW videos AS
SELECT id, title, description, published, duration_seconds, category, audio_language AS language,
       caption = 1 AS has_captions, from_json(tags, '["VARCHAR"]') AS tags,
       'https://www.youtube.com/watch?v=' || id AS url
FROM yt.catalog_video;

CREATE VIEW video_stats AS
SELECT video_id, taken_on::DATE AS taken_on, view_count, like_count, comment_count
FROM yt.catalog_videostats;

CREATE VIEW playlists AS
SELECT p.title AS playlist, i.position, i.video_id
FROM yt.catalog_playlist p JOIN yt.catalog_playlistitem i ON i.playlist_id = p.id;

-- 3. Tools with fixed SQL. The model fills the parameters; it cannot change the query.
PRAGMA mcp_publish_tool(
    'top_videos',
    'Most viewed videos on the channel, newest counts. Optional: only videos published on or after since (YYYY-MM-DD).',
    'SELECT v.title, v.published::DATE AS published, s.view_count, s.like_count, v.url
     FROM videos v
     JOIN (SELECT video_id, arg_max(view_count, taken_on) AS view_count, arg_max(like_count, taken_on) AS like_count
           FROM video_stats GROUP BY video_id) s ON s.video_id = v.id
     WHERE v.published >= coalesce($since::DATE, DATE ''1900-01-01'')
     ORDER BY s.view_count DESC
     LIMIT coalesce($n, 10)',
    '{"n": {"type": "integer", "description": "How many videos (default 10)"}, "since": {"type": "string", "description": "YYYY-MM-DD"}}',
    '[]'
);

PRAGMA mcp_publish_tool(
    'video_history',
    'Daily views, likes and comments for one video id.',
    'SELECT taken_on, view_count, like_count, comment_count FROM video_stats WHERE video_id = $video_id ORDER BY taken_on',
    '{"video_id": {"type": "string", "description": "The 11-character YouTube id"}}',
    '["video_id"]'
);

PRAGMA mcp_publish_tool(
    'search_videos',
    'Videos whose title, description or tags contain the text, newest first.',
    'SELECT id, title, published::DATE AS published, tags, url FROM videos
     WHERE title ILIKE ''%'' || $text || ''%'' OR description ILIKE ''%'' || $text || ''%''
        OR list_contains(tags, lower($text))
     ORDER BY published DESC LIMIT 20',
    '{"text": {"type": "string"}}',
    '["text"]'
);

-- 4. Lock it down before serving. No new files can be read or written from SQL,
--    and the configuration cannot be changed from inside the session.
SET enable_external_access = false;
SET lock_configuration = true;

-- 5. Serve. Built-in tools: query, describe, list_tables, database_info (read-only).
--    execute (DDL/DML) is off by default; export is switched off here as well.
PRAGMA mcp_server_start('stdio', 'localhost', 0, '{"enable_export_tool": false}');
