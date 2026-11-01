# Presenter guide

This guide follows `docs/DuckDB_MCP.pptx` slide by slide, for recording the video. Each slide's speaker notes hold the spoken text. This guide adds what to show on screen, the cues for the live parts, and how long to spend. Total: about 25 minutes, or two videos split after slide 13.

## Before recording

- [ ] `uv sync`, then run demos 1-3 once so the extensions are installed and the reports are fresh.
- [ ] `uv run --group docs python docs/make_deck.py` if a report changed.
- [ ] DuckDB CLI on the PATH. `duckdb -init demo/mcp/init-server.sql` loads with no error (Ctrl+C to leave).
- [ ] Claude Code open in the repository, `youtube-duckdb` approved, `/mcp` shows it connected.
- [ ] Decide which data you show. The sample is safe to show. For the real channel, run `sync_youtube` in youtube_ML that morning and switch the `ATTACH` path (demo guide, demo 4).
- [ ] A terminal with a large font, and an editor with `demo/run_02_analytics.py` and `demo/mcp/init-server.sql` open.

## Slides

| # | Slide | Time | On screen and cues |
| --- | --- | --- | --- |
| 1 | DuckDB and its MCP server, on a YouTube channel | 0:30 | Link back to the YouTube API video |
| 2 | From a SQLite file to questions in plain language | 0:45 | Mention that everything runs on the sample without a key |
| 3 | DuckDB is SQLite's shape with an analyst's engine | 1:30 | |
| 4 | SQLite for the app, DuckDB for the questions | 1:00 | Stress "not a replacement" |
| 5 | One SQLite file, written by Django, read by DuckDB | 1:30 | Optional: show `catalog/sync.py` in youtube_ML for 20 seconds |
| 6 | Six tables, two of them daily histories | 1:00 | |
| 7 | Query the SQLite file in place | 2:00 | **Live:** `uv run python demo/run_01_attach_sqlite.py`, scroll to sections 2 and 3 |
| 8 | Latest counts per video (QUALIFY) | 1:30 | **Live:** `uv run python demo/run_02_analytics.py`, stay on section 1 |
| 9 | Which tags carry the views | 1:30 | Section 3 of the same report |
| 10 | Uploads per year and length (PIVOT) | 1:00 | Section 4; mention sections 5-7 in one sentence |
| 11 | 6x smaller as Parquet | 1:00 | **Live (optional):** `uv run python demo/run_03_parquet.py`, about 10 seconds |
| 12 | 23x faster on Parquet than in SQLite | 1:30 | Your timings will differ from the slide; say so |
| 13 | Two API changes the tests caught | 1:00 | Natural split point for a two-part video |
| 14 | MCP lets a model call tools | 1:30 | Link back to youtube_mcp from the earlier video |
| 15 | One SQL file turns DuckDB into a server | 2:00 | **Show** `init-server.sql` in the editor, top to bottom |
| 16 | Five layers between the model and your data | 1:30 | |
| 17 | Questions to ask Claude about the channel | 4:00 | **Live:** see below |
| 18 | DuckDB can call MCP servers too | 1:00 | Show `client.sql`; run it only if youtube_mcp is built |
| 19 | Keep SQLite for the app; point DuckDB at it | 0:45 | |

## The live MCP part (slide 17)

Switch to Claude Code and ask, one at a time:

1. "Which five videos gained the most views in the last month?" Expect the built-in `query` tool with a `lag` over `video_stats`. Expand the call to show the SQL Claude wrote.
2. "Show the daily history of the top DuckDB video." Expect `search_videos` with `duckdb`, then `video_history`. These are our fixed tools: point out that only the parameters change.
3. "What do the agent videos have in common?" Open-ended. It shows the model choosing between tools.
4. To demonstrate the lock-down: "Change the configuration to allow external access." The call should fail. The `query` tool is read-only, and behind it the configuration is locked. Read the error aloud, and try this once before recording, because the exact message comes from the extension.

If a call fails, keep going. The refusal is part of the story on slide 16.

## After recording

- Put the repository link and the youtube_ML link in the video description.
- If you showed the real channel, say so in the description, and that the slides use the synthetic sample.
