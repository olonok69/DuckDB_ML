"""Build data/sample.sqlite3: a seeded, synthetic channel with youtube_ML's schema.

The demos and the tests run on this file, so nobody needs a YouTube API key. The
rows are invented: titles are put together from topic words, and views follow a
decay curve with noise. Seed 7. Point the demos at the real file with
--db ../youtube_ML/db.sqlite3 once `manage.py sync_youtube` has run.

    uv run python data/make_sample.py
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "sample.sqlite3"
SEED = 7
CHANNEL_ID = "UCsample0000000000000000"
VIDEOS = 120
FIRST_UPLOAD = datetime(2023, 1, 9, 17, 0, 0)
LAST_DAY = date(2026, 10, 31)
STATS_DAYS = 90  # one stats row per video per day for the last 90 days

TOPICS = {
    "LLM": ["llm", "rag", "embeddings"],
    "Agents": ["agents", "mcp", "tools"],
    "Claude Code": ["claude-code", "agents", "coding"],
    "DuckDB": ["duckdb", "sql", "analytics"],
    "Python": ["python", "uv", "packaging"],
    "MLOps": ["mlops", "docker", "ci"],
    "Computer Vision": ["vision", "pytorch", "yolo"],
    "Security": ["security", "adversarial-ml", "privacy"],
}
FORMATS = ["Intro to {t}", "{t} in 10 minutes", "Building with {t}", "{t}: a deep dive", "{t} tips", "{t} demo"]
CATEGORIES = [("28", "Science & Technology", 0.7), ("27", "Education", 0.3)]


def _video_id(rng: random.Random) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    return "".join(rng.choice(alphabet) for _ in range(11))


def build(path: Path = OUT) -> Path:
    rng = random.Random(SEED)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
    synced = datetime.combine(LAST_DAY, datetime.min.time()).replace(hour=6)

    con.execute(
        "INSERT INTO catalog_channel VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (CHANNEL_ID, "Sample ML Channel", "A synthetic channel for the DuckDB demo.", "@samplemlchannel",
         "GB", "2022-11-01 09:00:00", "", "UUsample0000000000000000", synced.isoformat(sep=" ")),
    )

    videos = []
    published = FIRST_UPLOAD
    topic_names = list(TOPICS)
    for n in range(VIDEOS):
        # Later topics show up later in the channel's life, as a real channel drifts.
        topic = topic_names[min(len(topic_names) - 1, int(rng.triangular(0, len(topic_names), n / VIDEOS * 8)))]
        title = rng.choice(FORMATS).format(t=topic)
        tags = TOPICS[topic] + rng.sample(["tutorial", "python", "open-source", "demo", "ai"], k=rng.randint(0, 2))
        tags = list(dict.fromkeys(tags))
        short = rng.random() < 0.15
        duration = rng.randint(30, 59) if short else int(rng.lognormvariate(6.6, 0.5))
        cat_id, cat, _ = CATEGORIES[0] if rng.random() < CATEGORIES[0][2] else CATEGORIES[1]
        audio = "es" if rng.random() < 0.25 else "en"
        # Potential: how many views the video would reach eventually.
        potential = rng.lognormvariate(7.4, 1.0) * (1.8 if topic in ("Claude Code", "Agents") else 1.0)
        vid = _video_id(rng)
        videos.append((vid, published, potential, topic))
        con.execute(
            "INSERT INTO catalog_video VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, f"{title} #{n + 1}" if short else title, f"Synthetic video about {topic}. Tags: {', '.join(tags)}.",
             published.isoformat(sep=" "), duration, cat_id, cat, "", audio, "hd", rng.random() < 0.6, False,
             "public", "youtube", True, False, "", json.dumps(tags),
             json.dumps(["https://en.wikipedia.org/wiki/Technology"]), synced.isoformat(sep=" "), CHANNEL_ID),
        )
        published += timedelta(days=rng.randint(4, 18), hours=rng.randint(-3, 3))
        if published.date() > LAST_DAY - timedelta(days=2):
            break

    first_stats = LAST_DAY - timedelta(days=STATS_DAYS - 1)
    stats_rows = []
    for vid, pub, potential, _ in videos:
        for d in range(STATS_DAYS):
            day = first_stats + timedelta(days=d)
            age = (day - pub.date()).days
            if age < 0:
                continue
            views = int(potential * (1 - math.exp(-age / 45)) * rng.uniform(0.995, 1.0)) + 1
            stats_rows.append((day.isoformat(), views, int(views * 0.04), int(views * 0.006), vid))
    # Counts never go down from one day to the next.
    stats_rows.sort(key=lambda r: (r[4], r[0]))
    fixed, last = [], {}
    for day, v, likes, comments, vid in stats_rows:
        v = max(v, last.get(vid, 0))
        last[vid] = v
        fixed.append((day, v, max(likes, 0), max(comments, 0), vid))
    con.executemany(
        "INSERT INTO catalog_videostats (taken_on, view_count, like_count, comment_count, video_id) VALUES (?,?,?,?,?)",
        fixed,
    )

    for d in range(STATS_DAYS):
        day = first_stats + timedelta(days=d)
        total = sum(r[1] for r in fixed if r[0] == day.isoformat())
        count = sum(1 for _, pub, _, _ in videos if pub.date() <= day)
        con.execute(
            "INSERT INTO catalog_channelsnapshot (taken_on, subscriber_count, view_count, video_count, channel_id) "
            "VALUES (?,?,?,?,?)",
            (day.isoformat(), int(total * 0.021) + 300, total, count, CHANNEL_ID),
        )

    for p, topic in enumerate(topic_names):
        pid = f"PLsample{p:02d}"
        members = [v for v in videos if v[3] == topic]
        con.execute(
            "INSERT INTO catalog_playlist VALUES (?,?,?,?,?,?,?,?)",
            (pid, topic, f"Every video about {topic}.", "2023-01-01 00:00:00", len(members), "public",
             synced.isoformat(sep=" "), CHANNEL_ID),
        )
        con.executemany(
            "INSERT INTO catalog_playlistitem (video_id, position, added, playlist_id) VALUES (?,?,?,?)",
            [(v[0], i, v[1].isoformat(sep=" "), pid) for i, v in enumerate(members)],
        )
    con.commit()
    con.execute("VACUUM")
    con.close()
    return path


if __name__ == "__main__":
    out = build()
    con = sqlite3.connect(out)
    for table in ("catalog_video", "catalog_videostats", "catalog_playlist", "catalog_playlistitem"):
        print(f"{table}: {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]} rows")
    print(f"wrote {out.relative_to(HERE.parent)} ({out.stat().st_size / 1024:.0f} KiB)")
