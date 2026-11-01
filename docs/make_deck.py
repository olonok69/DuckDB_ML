"""Build the deck (docs/DuckDB_MCP.pptx).

Run from the repository root, after the demos:

    uv run --group docs python docs/make_deck.py

Same look as the graimatter_ML deck: 16:9, cream and navy, a mono kicker over each
title, speaker notes on every slide. Numbers come from the reports in demo/output/
through docs/report_tables.py, so rerunning a demo and this script keeps the slides
in step with the code.
"""

from __future__ import annotations

import os

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from report_tables import line_with, table

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "DuckDB_MCP.pptx")


def rgb(h):
    return RGBColor.from_string(h.lstrip("#"))


NAVY, INK, MUTED, BODY = "#0F1B2D", "#1B2433", "#5F6979", "#3A4556"
ORANGE, PEACH, PEACHBG = "#B4521A", "#F2A35E", "#FBE9DC"
CREAM, CARD, BORDER = "#F6F5F0", "#FDFCF9", "#E2DFD6"
BLUE, BLUEBG = "#2F6DB5", "#DCE7F5"
GREEN, GREENBG, RED, REDBG = "#2E7D4F", "#DDEFE3", "#B23A3A", "#F6DEDE"
SANS, MONO = "IBM Plex Sans", "Consolas"
LEFT, WIDTH = 0.89, 11.55


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.layout = self.prs.slide_layouts[5]  # "Title Only": keeps a real title for the outline
        self.prefix = ""

    # -- primitives (as in graimatter_ML/docs/make_deck.py) ----------------------------
    def slide(self, kicker, title, dark=False, title_size=None):
        if title_size is None:
            title_size = 30 if len(title) <= 56 else 27
        s = self.prs.slides.add_slide(self.layout)
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(NAVY if dark else CREAM)
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(LEFT), Inches(1.32), Inches(WIDTH), Inches(0.95)
        tf = t.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.text = title
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        for r in p.runs:
            r.font.name, r.font.size, r.font.bold = SANS, Pt(title_size), True
            r.font.color.rgb = rgb(CREAM if dark else NAVY)
        if kicker:
            self.text(s, LEFT, 0.89, WIDTH, 0.3, self.prefix + kicker, 12, PEACH if dark else ORANGE, font=MONO)
        return s

    def text(self, s, x, y, w, h, text, size=15, color=BODY, bold=False, font=SANS, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, italic=False):
        """Text box. `text` may be a string or a list of paragraphs; a paragraph may be a list of (text, bold) runs."""
        box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        paras = text if isinstance(text, list) else [text]
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if i:
                p.space_before = Pt(6)
            runs = para if isinstance(para, list) else [(para, bold)]
            for chunk, b in runs:
                r = p.add_run()
                r.text = chunk
                r.font.name, r.font.size, r.font.bold, r.font.italic = font, Pt(size), b, italic
                r.font.color.rgb = rgb(color)
        return box

    def rect(self, s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
        r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        r.fill.solid()
        r.fill.fore_color.rgb = rgb(fill)
        if line:
            r.line.color.rgb = rgb(line)
            r.line.width = Pt(1)
        else:
            r.line.fill.background()
        r.shadow.inherit = False
        style = r._element.find("{http://schemas.openxmlformats.org/presentationml/2006/main}style")
        if style is not None:  # drop the theme style so no renderer adds its shadow
            r._element.remove(style)
        if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            r.adjustments[0] = min(0.08, 0.12 / min(w, h))
        return r

    def card(self, s, x, y, w, h, title, body, dark=False, fill=None, tcolor=None, tsize=16, bsize=13):
        self.rect(s, x, y, w, h, fill or (NAVY if dark else CARD), None if (dark or fill) else BORDER)
        self.text(s, x + 0.22, y + 0.2, w - 0.44, 0.4, title, tsize, tcolor or (PEACH if dark else NAVY), True)
        self.text(s, x + 0.22, y + 0.2 + 0.3 * (1 + (len(title) * tsize * 0.0075 > w - 0.44)), w - 0.44, h - 0.6,
                  body, bsize, "#D9DEE6" if dark else BODY)

    def footer(self, s, text, dark=False):
        self.text(s, LEFT, 6.82, WIDTH, 0.3, text, 12, "#9AA7B8" if dark else MUTED)

    def notes(self, s, text):
        s.notes_slide.notes_text_frame.text = text

    def table(self, s, x, y, w, rows, col_w, size=13, header_fill=NAVY, row_h=0.4, highlight=None):
        shape = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
        tbl = shape.table
        tbl.first_row = True
        for j, cw in enumerate(col_w):
            tbl.columns[j].width = Inches(cw)
        for i, row in enumerate(rows):
            tbl.rows[i].height = Inches(row_h)
            for j, val in enumerate(row):
                c = tbl.cell(i, j)
                c.margin_left = c.margin_right = Inches(0.1)
                c.margin_top = c.margin_bottom = Inches(0.04)
                c.vertical_anchor = MSO_ANCHOR.MIDDLE
                c.fill.solid()
                if i == 0:
                    c.fill.fore_color.rgb = rgb(header_fill)
                elif highlight and (i, j) in highlight:
                    c.fill.fore_color.rgb = rgb(highlight[(i, j)])
                else:
                    c.fill.fore_color.rgb = rgb(CARD if i % 2 else "#F1EFE8")
                tf = c.text_frame
                tf.word_wrap = True
                tf.text = str(val)
                for p in tf.paragraphs:
                    for r in p.runs:
                        r.font.name, r.font.size = SANS, Pt(size)
                        r.font.bold = i == 0 or j == 0
                        r.font.color.rgb = rgb(CREAM if i == 0 else (NAVY if j == 0 else BODY))
        return tbl

    def chips(self, s, x, y, labels, dark=True):
        for lab in labels:
            w = 0.3 + len(lab) * 0.095
            self.rect(s, x, y, w, 0.44, "#1E2B40" if dark else PEACHBG)
            self.text(s, x, y, w, 0.44, lab, 14, CREAM if dark else NAVY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            x += w + 0.16

    # -- additions for this deck ---------------------------------------------------------
    def code(self, s, x, y, w, h, sql, size=13):
        """SQL on a dark panel, monospaced."""
        self.rect(s, x, y, w, h, NAVY)
        self.text(s, x + 0.25, y + 0.2, w - 0.5, h - 0.4, sql.strip().splitlines(), size, "#E8ECF2", font=MONO)

    def box(self, s, x, y, w, h, title, sub="", fill=CARD, line=BORDER, tcolor=NAVY):
        """A labelled box for the flow diagrams."""
        self.rect(s, x, y, w, h, fill, line)
        self.text(s, x + 0.12, y + 0.12, w - 0.24, 0.35, title, 15, tcolor, True, align=PP_ALIGN.CENTER)
        if sub:
            self.text(s, x + 0.12, y + 0.5, w - 0.24, h - 0.6, sub, 12, BODY if fill != NAVY else "#D9DEE6",
                      align=PP_ALIGN.CENTER)

    def arrow(self, s, x1, y1, x2, y2, label="", color=MUTED):
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = rgb(color)
        c.line.width = Pt(1.75)
        end = c.line._get_or_add_ln()
        tail = end.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"})
        end.append(tail)
        if label:
            self.text(s, min(x1, x2) - 0.3, min(y1, y2) - 0.38, abs(x2 - x1) + 0.6, 0.3, label, 11, MUTED,
                      font=MONO, align=PP_ALIGN.CENTER)

    def bars(self, s, x, y, w, h, categories, values, unit, color=BLUE, highlight=None, fmt='#,##0.0'):
        """Horizontal bar chart, one series, values labelled at the bar end."""
        data = CategoryChartData()
        data.categories = categories
        data.add_series(unit, values)
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), data)
        ch = gf.chart
        ch.has_legend = False
        ch.has_title = False
        ch.font.name, ch.font.size = SANS, Pt(13)
        ch.font.color.rgb = rgb(BODY)
        plot = ch.plots[0]
        plot.gap_width = 60
        plot.has_data_labels = True
        labels = plot.data_labels
        labels.number_format, labels.number_format_is_linked = fmt + (f' "{unit}"' if unit else ""), False
        labels.position = XL_LABEL_POSITION.OUTSIDE_END
        labels.font.size, labels.font.bold = Pt(13), True
        series = plot.series[0]
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = rgb(color)
        for i in highlight or []:
            pt = series.points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(ORANGE)
        cat = ch.category_axis
        cat.reverse_order = True
        cat.format.line.color.rgb = rgb(BORDER)
        cat.has_major_gridlines = False
        val = ch.value_axis
        val.visible = False
        val.has_major_gridlines = False
        return ch

    def save(self):
        props = self.prs.core_properties
        props.title, props.author, props.last_modified_by, props.comments = "DuckDB and MCP", "", "", ""
        self.prs.save(OUT)


def build():
    d = Deck()
    tables = {r["table"]: r["rows"] for r in table("01_attach_sqlite.txt", "2. The tables")}
    types = {r["column_name"]: r["column_type"] for r in table("01_attach_sqlite.txt", "3. How DuckDB")}
    latest = table("02_analytics.txt", "1. Latest counts")
    tags = table("02_analytics.txt", "3. Which tags")
    pivot = table("02_analytics.txt", "4. Uploads per year")
    sizes = table("03_parquet.txt", "3. Sizes")
    timings = table("03_parquet.txt", "4. Timings")
    version = line_with("03_parquet.txt", "[timing] DuckDB").removeprefix("[timing] ")
    t = {r["engine"]: r["ms"] for r in timings}
    t_sqlite, t_scan = t["sqlite3 module on the SQLite file"], t["DuckDB over the attached SQLite file"]
    t_parquet = t["DuckDB on Parquet"]
    mib = {r["format"]: r["MiB"] for r in sizes}
    big_rows = next(w for w in open(os.path.join(HERE, "..", "demo", "output", "03_parquet.txt"), encoding="utf-8")
                    if w.endswith("Seed fixed.\n")).split(" ")[0]

    # 1 ----------------------------------------------------------------------------------
    s = d.slide("DUCKDB 2.0 · SQLITE · PARQUET · MODEL CONTEXT PROTOCOL",
                "DuckDB and its MCP server, on a YouTube channel", dark=True, title_size=40)
    s.shapes.title.top, s.shapes.title.height = Inches(1.95), Inches(2.2)
    s.shapes[1].top = Inches(1.45)
    d.rect(s, 0, 0, 0.17, 7.5, ORANGE, shape=MSO_SHAPE.RECTANGLE)
    d.text(s, LEFT, 3.75, 10.8, 0.9, "An analytical database that runs inside your Python process, reads the channel's "
           "SQLite file where it lies, and answers Claude's questions through MCP", 21, "#D9DEE6")
    d.chips(s, LEFT, 5.05, ["uv add duckdb", "ATTACH db.sqlite3", "duckdb_mcp server", "5 demos"])
    d.footer(s, "Code, sample data and reports: github.com/olonok69/DuckDB_ML. The YouTube app: github.com/olonok69/youtube_ML",
             dark=True)
    d.notes(s, "This video follows the one on the YouTube Data API and the channel app. That app now stores the channel in "
            "a SQLite file: videos, daily statistics and playlists. Here we take that file and put DuckDB on it. First we "
            "query it in place, then we run the kind of analytics SQLite makes awkward, then we compare SQLite, DuckDB "
            "and Parquet on a bigger table, and finally we serve the database to Claude through the duckdb_mcp extension, "
            "so we can ask questions about the channel in plain language.")

    # 2 ----------------------------------------------------------------------------------
    s = d.slide("AGENDA", "From a SQLite file to questions in plain language")
    agenda = [
        ("1 · Why DuckDB", "In-process, columnar, vectorised. What it is for, and what SQLite is for.", True),
        ("2 · The data", "YouTube API, sync_youtube, six tables in db.sqlite3, and a synthetic sample.", False),
        ("3 · SQL tour", "Attach, QUALIFY, JSON lists, PIVOT, GROUP BY ALL. Demos 1 and 2.", False),
        ("4 · Formats", "SQLite against DuckDB and Parquet on 2M rows: size and speed. Demo 3.", False),
        ("5 · MCP", "duckdb_mcp as a server for Claude, locked down; and as a client. Demos 4 and 5.", False),
    ]
    for i, (a, b, dark) in enumerate(agenda):
        d.card(s, LEFT + i * 2.35, 2.25, 2.15, 2.75, a, b, dark=dark, tsize=16, bsize=13)
    d.rect(s, LEFT, 5.3, WIDTH, 0.95, PEACHBG)
    d.text(s, LEFT + 0.25, 5.3, WIDTH - 0.5, 0.95, [[("Everything runs on the sample: ", True), (
           "data/sample.sqlite3 has the same tables as the real database, with invented videos, so you can follow along "
           "without an API key. Pass --db ../youtube_ML/db.sqlite3 to run the same SQL on the real channel.", False)]],
           14, INK, anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s, "In demo/: run_01_attach_sqlite.py, run_02_analytics.py, run_03_parquet.py, mcp/init-server.sql, mcp/client.sql.")
    d.notes(s, "Five parts. Why DuckDB exists and where it fits next to SQLite. Where the data comes from. A tour of the SQL "
            "on the channel data. A size and speed comparison between formats. And MCP, which is the reason we are here: "
            "DuckDB can act as an MCP server, so Claude can query the database with tools we define, and as an MCP client, "
            "so DuckDB can call other MCP servers from SQL.")

    # Part 1 -----------------------------------------------------------------------------
    d.prefix = "PART 1 · "
    s = d.slide("WHAT IT IS", "DuckDB is SQLite's shape with an analyst's engine")
    cards = [
        ("In-process", "A library, not a server: uv add duckdb, import duckdb. The database is a file or memory. "
                       "Nothing to install, start or secure on a port."),
        ("Columnar and vectorised", "Reads only the columns a query uses, in batches of values, on every core. "
                                    "Aggregates over millions of rows take milliseconds."),
        ("Reads files in place", "SQLite, Parquet, CSV and JSON through extensions and table functions, with no "
                                 "import step. One query can join all of them."),
    ]
    for i, (a, b) in enumerate(cards):
        d.card(s, LEFT + i * 3.95, 2.2, 3.65, 2.5, a, b, tsize=19, bsize=15)
    d.rect(s, LEFT, 5.0, WIDTH, 1.35, NAVY)
    d.text(s, LEFT + 0.3, 5.0, WIDTH - 0.6, 1.35, [[("2.0 LTS: ", True), (
           "the long-term support line these demos target (pyproject pins duckdb>=2.0,<3). CI runs every demo on it. "
           "Two changes in the Python API mattered here; they are on slide 13.", False)]], 15, CREAM, anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s, "duckdb.org/docs/2.0 · github.com/duckdb/duckdb")
    d.notes(s, "Think of DuckDB as SQLite's packaging with a different engine. Like SQLite it lives inside your process and "
            "keeps the database in one file, or in memory. Unlike SQLite it stores and processes data by column, in "
            "vectors of values, using all cores. That is what analytics needs: few columns, many rows, aggregates. The "
            "third point is what makes this demo work: DuckDB reads other formats in place, including SQLite files.")

    s = d.slide("WHEN TO USE WHICH", "SQLite for the app, DuckDB for the questions")
    d.table(s, LEFT, 2.2, WIDTH, [
        ["", "SQLite", "DuckDB", "PostgreSQL"],
        ["Runs", "In your process", "In your process", "A server you operate"],
        ["Storage", "Rows", "Columns", "Rows"],
        ["Good at", "Many small reads and writes: an app's data", "Scans and aggregates over many rows",
         "Many concurrent users and writers"],
        ["Writers", "One at a time", "One process at a time", "Many"],
        ["In this demo", "Django writes db.sqlite3", "Attaches it read-only and analyses it", "Not used"],
    ], [1.75, 3.3, 3.3, 3.2], size=14, row_h=0.62)
    d.footer(s, "The two work together: the Django app keeps writing SQLite; DuckDB reads the same file.")
    d.notes(s, "This is not a replacement story. SQLite is excellent at what the Django app does: small transactions, one "
            "row at a time. DuckDB is built for the opposite workload. The nice part is that you do not have to choose or "
            "copy: DuckDB attaches the SQLite file read-only and runs its own engine over it. PostgreSQL is in the table "
            "only to place the other two; nothing here needs a server.")

    # Part 2 -----------------------------------------------------------------------------
    d.prefix = "PART 2 · "
    s = d.slide("WHERE THE ROWS COME FROM", "One SQLite file, written by Django, read by DuckDB")
    y = 2.55
    d.box(s, LEFT, y, 2.2, 1.35, "YouTube Data API", "read-only, API key")
    d.box(s, LEFT + 2.85, y, 2.4, 1.35, "sync_youtube", "manage.py command in youtube_ML, daily")
    d.box(s, LEFT + 5.9, y, 2.2, 1.35, "db.sqlite3", "6 catalog_* tables", fill=PEACHBG, line=PEACH)
    d.box(s, LEFT + 8.75, y, 2.8, 1.35, "DuckDB", "ATTACH ... (TYPE sqlite, READ_ONLY)", fill=NAVY, line=None, tcolor=PEACH)
    d.arrow(s, LEFT + 2.2, y + 0.68, LEFT + 2.85, y + 0.68, "list")
    d.arrow(s, LEFT + 5.25, y + 0.68, LEFT + 5.9, y + 0.68, "upsert")
    d.arrow(s, LEFT + 8.1, y + 0.68, LEFT + 8.75, y + 0.68, "scan")
    d.box(s, LEFT + 5.9, y + 2.1, 2.2, 1.1, "Django site", "Home, Find, Video")
    d.arrow(s, LEFT + 7.0, y + 1.35, LEFT + 7.0, y + 2.1)
    d.box(s, LEFT + 8.75, y + 2.1, 2.8, 1.1, "Claude", "through duckdb_mcp", fill=BLUEBG, line=BLUE)
    d.arrow(s, LEFT + 10.15, y + 1.35, LEFT + 10.15, y + 2.1)
    d.text(s, LEFT + 10.3, y + 1.55, 1.0, 0.3, "MCP", 11, MUTED, font=MONO)
    d.footer(s, "youtube_ML: catalog/models.py and catalog/sync.py. About 20 quota units a run for 200 uploads.")
    d.notes(s, "The YouTube API is read-only with an API key. A management command in youtube_ML, sync_youtube, lists the "
            "channel, its uploads and playlists, and upserts them into db.sqlite3. Run it daily and every run adds one "
            "statistics row per video, so you build a history of views. The Django site keeps working as before. DuckDB "
            "attaches that same file read-only, and through the MCP extension Claude gets to ask questions of it.")

    s = d.slide("THE SCHEMA", "Six tables, two of them daily histories")
    d.table(s, LEFT, 2.2, WIDTH, [
        ["Table", "One row per", "Columns used in the demos", "Sample rows"],
        ["catalog_video", "public upload", "title, published, duration_seconds, caption, tags (JSON text)",
         f"{tables['catalog_video']:,}"],
        ["catalog_videostats", "video and day", "taken_on, view_count, like_count, comment_count",
         f"{tables['catalog_videostats']:,}"],
        ["catalog_channelsnapshot", "channel and day", "taken_on, subscriber_count, view_count",
         f"{tables['catalog_channelsnapshot']:,}"],
        ["catalog_playlist", "playlist", "title, item_count", f"{tables['catalog_playlist']:,}"],
        ["catalog_playlistitem", "video in a playlist", "playlist_id, video_id, position",
         f"{tables['catalog_playlistitem']:,}"],
        ["catalog_channel", "channel", "title, uploads_playlist_id", f"{tables['catalog_channel']:,}"],
    ], [2.75, 2.0, 5.4, 1.4], size=13.5, row_h=0.55)
    d.footer(s, "Sample: data/sample.sqlite3, synthetic, seed 7; data/make_sample.py rebuilds it identically.")
    d.notes(s, "The two tables that make this interesting are the daily histories: one row per video per day, and one per "
            "channel per day. That is where window functions earn their keep. Tags are a list, and SQLite has no list "
            "type, so Django stores them as JSON text. The sample file has the same schema with invented videos: 120 "
            "uploads, 90 days of statistics, 8 playlists. It is what CI runs on.")

    # Part 3 -----------------------------------------------------------------------------
    d.prefix = "PART 3 · DEMO 1 · "
    s = d.slide("ATTACH", "Query the SQLite file in place: nothing is copied")
    d.code(s, LEFT, 2.2, 6.4, 2.6, """
import duckdb
con = duckdb.connect()
con.sql("INSTALL sqlite; LOAD sqlite")
con.sql(\"\"\"ATTACH 'db.sqlite3' AS yt
          (TYPE sqlite, READ_ONLY)\"\"\")
con.sql("SELECT count(*) FROM yt.catalog_video")
""", size=14)
    d.table(s, LEFT + 6.75, 2.2, 4.8, [["Column", "DuckDB type"]] + [[k, v] for k, v in types.items()],
            [2.4, 2.4], size=14, row_h=0.43)
    d.rect(s, LEFT, 5.15, WIDTH, 1.1, PEACHBG)
    d.text(s, LEFT + 0.25, 5.15, WIDTH - 0.5, 1.1, [[("Typed from the declared schema: ", True), (
           "published arrives as TIMESTAMP, so date functions work directly. Booleans arrive as BIGINT and tags as "
           "JSON text: SQLite stores them that way, and the views in demo 4 tidy both.", False)]], 14, INK,
           anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s, "demo/run_01_attach_sqlite.py · report: demo/output/01_attach_sqlite.txt")
    d.notes(s, "Three lines. Connect to an in-memory DuckDB, load the sqlite extension, attach the file read-only. From then "
            "on yt.catalog_video is a table like any other. The scanner reads the declared column types, which is why the "
            "published column is a real timestamp. SQLite has no boolean or list type, so those come through as integers "
            "and text, and we will convert them where it matters.")

    d.prefix = "PART 3 · DEMO 2 · "
    s = d.slide("QUALIFY", "Latest counts per video: filter on the window directly")
    d.code(s, LEFT, 2.2, 6.2, 2.75, """
SELECT v.title, s.view_count
FROM yt.catalog_video v
JOIN yt.catalog_videostats s
  ON s.video_id = v.id
QUALIFY row_number() OVER (
  PARTITION BY v.id ORDER BY s.taken_on DESC) = 1
ORDER BY s.view_count DESC
""", size=13.5)
    d.table(s, LEFT + 6.5, 2.2, 5.05, [["Title", "Views"]] + [[r["title"], f"{r['view_count']:,}"] for r in latest[:5]],
            [3.75, 1.3], size=13, row_h=0.45)
    d.text(s, LEFT, 5.25, WIDTH, 0.9, "In SQLite the same needs a CTE with row_number() and an outer WHERE. QUALIFY is to "
           "window functions what HAVING is to aggregates.", 15, BODY)
    d.footer(s, "Sample data: invented titles and counts. demo/output/02_analytics.txt, section 1.")
    d.notes(s, "The statistics table has one row per video per day. To get the latest row per video you number the rows in "
            "each video, newest first, and keep number one. QUALIFY lets you filter on that window result in the same "
            "query. The section after it in the report uses lag over 29 rows to get views gained in the last 30 days.")

    s = d.slide("JSON TEXT TO LISTS", "Which tags carry the views")
    d.code(s, LEFT, 2.2, 5.7, 2.4, """
SELECT tag, count(*) AS videos,
       avg(views)::BIGINT AS avg_views
FROM (SELECT unnest(from_json(
        tags, '["VARCHAR"]')) AS tag, views
      FROM ...)
GROUP BY ALL ORDER BY avg_views DESC
""", size=13.5)
    top = tags[:6]
    d.text(s, LEFT + 6.0, 2.05, 5.55, 0.35, "Average views per video, by tag", 14, NAVY, True)
    d.bars(s, LEFT + 6.0, 2.4, 5.55, 3.3, [r["tag"] for r in top], [r["avg_views"] for r in top], "", fmt="#,##0")
    d.text(s, LEFT, 4.9, 5.7, 1.3, "from_json turns the JSON text into a VARCHAR[] list; unnest gives one row per tag. "
           "GROUP BY ALL groups by every column that is not an aggregate.", 15, BODY)
    d.footer(s, "Sample data. demo/output/02_analytics.txt, section 3 (tags on at least 5 videos).")
    d.notes(s, "Tags are where SQLite and DuckDB differ most. SQLite has JSON functions, but no list type, so you end up "
            "with json_each and a join. DuckDB parses the text into a real list and unnests it. Then it is a normal group "
            "by. On the sample the agent and MCP tags lead because the generator gives those topics more views; on the "
            "real channel this is the question you would actually want answered.")

    s = d.slide("PIVOT", "Uploads per year and length, without a CASE per column")
    d.code(s, LEFT, 2.2, 6.0, 3.6, """
PIVOT (
  SELECT year(published) AS year,
    CASE WHEN duration_seconds < 60
           THEN 'short'
         WHEN duration_seconds < 600
           THEN 'under_10m'
         ELSE '10m_plus' END AS length
  FROM yt.catalog_video)
ON length IN ('short', 'under_10m',
              '10m_plus')
USING count(*) GROUP BY year
""", size=13)
    d.table(s, LEFT + 6.35, 2.2, 5.2, [["Year", "Short", "Under 10m", "10m+"]] +
            [[str(r["year"]), r["short"], r["under_10m"], r["10m_plus"]] for r in pivot], [1.3, 1.3, 1.3, 1.3],
            size=14, row_h=0.5)
    d.footer(s, "Sample data. demo/output/02_analytics.txt, section 4. Sections 5-7: FILTER, arg_max, list(... ORDER BY).")
    d.notes(s, "PIVOT turns the length categories into columns. In SQLite you would write one sum of a CASE expression per "
            "column. The rest of the report shows FILTER inside count, arg_max to pick the title with the most views in "
            "each playlist, and list with an ORDER BY to keep the playlist order.")

    # Part 4 -----------------------------------------------------------------------------
    d.prefix = "PART 4 · DEMO 3 · "
    s = d.slide("SIZE ON DISK", f"The same {big_rows} rows: {mib['SQLite (row store)'] / mib['Parquet, zstd (columnar)']:.0f}x "
                "smaller as Parquet")
    d.bars(s, LEFT, 2.15, 7.2, 3.6, [r["format"] for r in sizes], [r["MiB"] for r in sizes], "MiB", highlight=[2])
    d.card(s, LEFT + 7.6, 2.3, 3.95, 3.3, "Why", "Columns of one type compress well: dates repeat, counts are small "
           "integers. A row store keeps each row's values together, so it compresses far less. DuckDB's own file and "
           "Parquet both store columns.", tsize=18, bsize=14.5)
    d.footer(s, f"demo/run_03_parquet.py: a synthetic stats table written to SQLite by DuckDB, then copied. {version}.")
    d.notes(s, "To make sizes and timings mean something, demo 3 writes a larger statistics table, two million rows, into a "
            "scratch SQLite file, using DuckDB's sqlite extension in write mode. Then it copies the same table into a "
            "DuckDB file and into Parquet with zstd compression. Same data, three formats.")

    s = d.slide("SPEED", f"One aggregate: {t_sqlite / t_parquet:.0f}x faster on Parquet than in SQLite")
    d.bars(s, LEFT, 2.15, 7.6, 3.7, [r["engine"] for r in timings], [r["ms"] for r in timings], "ms", highlight=[2, 3])
    d.card(s, LEFT + 8.0, 2.3, 3.55, 3.4, "Read it this way", f"DuckDB over the SQLite file is already {t_sqlite / t_scan:.0f}x "
           "faster than SQLite itself: same file, better engine. Columnar storage adds the rest.", tsize=18, bsize=14.5)
    d.footer(s, f"Best of 3 on a GitHub Actions runner; machine-dependent, so the tests ignore them. {version}.")
    d.notes(s, "The question is views and likes per year over the two million rows. The Python sqlite3 module is the "
            "baseline. DuckDB scanning the same SQLite file is the second bar: same storage, DuckDB's engine. The last two "
            "read only the four columns the query needs, from DuckDB's own table and from Parquet. All four engines return "
            "the same numbers; the report checks that.")

    d.prefix = "PART 4 · "
    s = d.slide("DUCKDB 2.0 IN PYTHON", "Two API changes the tests caught")
    d.card(s, LEFT, 2.2, 5.6, 2.4, "Relations have no fetchone()", "con.sql(...) is a relation. It keeps no result, so "
           "each call runs the query again, and 2.0 removed fetchone() from it. Use fetchall(), or limit(1).",
           tsize=18, bsize=15)
    d.card(s, LEFT + 5.95, 2.2, 5.6, 2.4, "An open result blocks the connection", "con.execute(...).fetchone() leaves the "
           "rest of the result open. The next query on that connection raises ResourceInUseException. Fetch everything, "
           "or use a cursor().", tsize=18, bsize=15)
    d.code(s, LEFT, 4.95, WIDTH, 0.85, """
n = con.execute("SELECT count(*) FROM yt.catalog_video").fetchall()[0][0]  # 1.x and 2.0
""", size=14)
    d.footer(s, "Both showed up only when CI ran on 2.0. The fix is in the repository's first pull request.")
    d.notes(s, "If you are moving code from DuckDB 1.x, these are the two things that bit here. Both make sense: a relation "
            "is a lazy query, not a result set, and an unfinished result holds the connection. The fix is the same line on "
            "both versions.")

    # Part 5 -----------------------------------------------------------------------------
    d.prefix = "PART 5 · "
    s = d.slide("MCP", "MCP lets a model call tools that someone else defines")
    d.box(s, LEFT, 2.5, 3.0, 1.6, "MCP client", "Claude Code, Claude Desktop, any agent", fill=BLUEBG, line=BLUE)
    d.box(s, LEFT + 4.3, 2.5, 3.0, 1.6, "MCP server", "lists tools and resources, runs them", fill=NAVY, line=None,
          tcolor=PEACH)
    d.box(s, LEFT + 8.6, 2.5, 2.95, 1.6, "The data", "here: DuckDB over db.sqlite3", fill=PEACHBG, line=PEACH)
    d.arrow(s, LEFT + 3.0, 3.1, LEFT + 4.3, 3.1, "tools/call")
    d.arrow(s, LEFT + 7.3, 3.1, LEFT + 8.6, 3.1, "SQL")
    d.text(s, LEFT, 4.55, WIDTH, 1.7, [
        [("The model sees tool names, descriptions and a JSON schema for the arguments. ", True),
         ("It decides when to call one; the server runs it and returns rows.", False)],
        [("stdio transport: ", True), ("the client starts the server as a child process and talks over its "
                                       "stdin and stdout. Nothing listens on a port.", False)]], 15, BODY)
    d.footer(s, "modelcontextprotocol.io · youtube_ML has its own MCP server, youtube_mcp, for the live API.")
    d.notes(s, "The Model Context Protocol is the plug between a model and tools. A client, here Claude Code, connects to a "
            "server, asks what tools it has, and calls them with JSON arguments. The server can be anything. In the "
            "previous video it was youtube_mcp talking to the live API. Here it is DuckDB itself, through the duckdb_mcp "
            "community extension.")

    d.prefix = "PART 5 · DEMO 4 · "
    s = d.slide("DUCKDB AS AN MCP SERVER", "One SQL file turns DuckDB into a server for Claude")
    d.code(s, LEFT, 2.2, 6.5, 3.95, """
-- .mcp.json: duckdb -init demo/mcp/init-server.sql
INSTALL duckdb_mcp FROM community; LOAD duckdb_mcp;
ATTACH 'data/sample.sqlite3' AS yt
       (TYPE sqlite, READ_ONLY);
CREATE VIEW videos AS ...;  -- clear names
PRAGMA mcp_publish_tool('top_videos', ...);
SET enable_external_access = false;
SET lock_configuration = true;
PRAGMA mcp_server_start('stdio', 'localhost', 0,
       '{"enable_export_tool": false}');
""", size=13)
    d.table(s, LEFT + 6.85, 2.2, 4.7, [
        ["Tool", "Kind"],
        ["top_videos(n, since)", "ours, fixed SQL"],
        ["video_history(video_id)", "ours, fixed SQL"],
        ["search_videos(text)", "ours, fixed SQL"],
        ["query, describe", "built in, read-only"],
        ["list_tables, database_info", "built in"],
        ["execute, export", "off"],
    ], [2.65, 2.05], size=13, row_h=0.52)
    d.footer(s, "demo/mcp/init-server.sql and .mcp.json. CI runs the script up to the server start (tests/test_mcp.py).")
    d.notes(s, "Claude Code reads .mcp.json at the project root and starts the DuckDB CLI with an init file. The file loads "
            "the extension, attaches the database read-only, creates three views with friendly names, publishes three "
            "tools whose SQL is fixed, locks the session down, and starts serving on stdio. The built-in query tool is still "
            "there for open questions, but it is read-only, and execute and export are off.")

    s = d.slide("LOCKED DOWN", "Five layers between the model and your data")
    layers = [
        ("Read-only attach", "The SQLite file cannot be written through this connection."),
        ("Fixed-SQL tools", "The model fills parameters, it cannot change the query."),
        ("No execute, no export", "DDL, DML and file export are switched off in the server config."),
        ("No external access", "enable_external_access = false: no new files read or written from SQL."),
        ("Locked configuration", "lock_configuration = true: no SET can undo the above. The test checks it."),
    ]
    for i, (a, b) in enumerate(layers):
        y = 2.15 + i * 0.86
        d.rect(s, LEFT, y, 0.62, 0.7, ORANGE if i == 4 else NAVY)
        d.text(s, LEFT, y, 0.62, 0.7, str(i + 1), 20, CREAM, True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        d.rect(s, LEFT + 0.75, y, WIDTH - 0.75, 0.7, CARD, BORDER)
        d.text(s, LEFT + 1.0, y, 3.2, 0.7, a, 16, NAVY, True, anchor=MSO_ANCHOR.MIDDLE)
        d.text(s, LEFT + 4.2, y, WIDTH - 4.5, 0.7, b, 15, BODY, anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s, "Client mode has its own allowlists: allowed_mcp_commands and allowed_mcp_urls, deny by default.")
    d.notes(s, "An MCP server is an attack surface: whatever the model reads can try to steer it into calling tools. So the "
            "server gives it as little as possible. The attach is read-only. Our tools have fixed SQL. The tools that "
            "change data or write files are off. External access is off, so the query tool cannot read arbitrary files. "
            "And the configuration is locked, so none of this can be switched back from inside the session.")

    s = d.slide("LIVE", "Questions to ask Claude about the channel")
    asks = [
        ("Which five videos gained the most views in the last month?", "query with lag over video_stats"),
        ("Show the daily history of the top DuckDB video.", "search_videos, then video_history"),
        ("What do the agent videos have in common?", "top_videos, then query on tags"),
        ("Which playlist has the longest videos on average?", "describe, then query"),
    ]
    for i, (q, how) in enumerate(asks):
        y = 2.2 + i * 1.0
        d.rect(s, LEFT, y, 7.6, 0.82, BLUEBG)
        d.text(s, LEFT + 0.25, y, 7.2, 0.82, f"“{q}”", 16, NAVY, True, anchor=MSO_ANCHOR.MIDDLE)
        d.text(s, LEFT + 7.85, y, 3.7, 0.82, how, 14, MUTED, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s, "On the sample the answers are invented; switch the ATTACH path to youtube_ML's db.sqlite3 for the real ones.")
    d.notes(s, "This is the live part. Open Claude Code in the repository, approve the youtube-duckdb server, and ask. Watch "
            "which tool it picks: our fixed tools for the common questions, the read-only query tool for the rest. If it "
            "writes SQL, the panel shows it, which is a good way to learn DuckDB's dialect.")

    d.prefix = "PART 5 · DEMO 5 · "
    s = d.slide("DUCKDB AS AN MCP CLIENT", "DuckDB can call MCP servers too, from SQL")
    d.code(s, LEFT, 2.2, 7.0, 3.4, """
SET allowed_mcp_commands = 'node';
ATTACH 'node' AS youtube (TYPE mcp, TRANSPORT 'stdio',
  ARGS '["../youtube_ML/youtube_mcp/dist/index.js"]');
SELECT mcp_list_tools('youtube');
CREATE TABLE channel_live AS
SELECT mcp_call_tool('youtube', 'get_channel_info',
  '{"url": "@themachinelearningengineer"}') AS answer;
""", size=13)
    d.card(s, LEFT + 7.35, 2.2, 4.2, 3.4, "Closing the loop", "The previous video's MCP server reads the live API. "
           "Here DuckDB calls it and stores the answer as a table, next to the SQLite history. Optional: needs the Node "
           "server built and a key; not on Windows.", tsize=18, bsize=14.5)
    d.footer(s, "demo/mcp/client.sql. Not run in CI: it needs the API key.")
    d.notes(s, "The extension works in the other direction as well. DuckDB attaches an MCP server like a database, lists its "
            "tools and calls them from SQL. Here it calls youtube_mcp, the server from the previous video, for live channel "
            "info, and keeps the JSON answer as a table. Commands are denied unless allowlisted, which is the first line.")

    # Close -----------------------------------------------------------------------------
    d.prefix = ""
    s = d.slide("TAKEAWAYS", "Keep SQLite for the app; point DuckDB at it for the questions")
    take = [
        ("Use DuckDB when", "the work is scans, joins and aggregates; data sits in files; you want SQL in a notebook or "
                            "a script with no server."),
        ("Watch out for", "one writer at a time. Attach the app's SQLite read-only, and copy to Parquet or a DuckDB file "
                          "for heavy work."),
        ("With MCP", "publish narrow tools with fixed SQL, keep the attach read-only, switch off what you do not need, "
                     "and lock the configuration."),
    ]
    for i, (a, b) in enumerate(take):
        d.card(s, LEFT + i * 3.95, 2.2, 3.65, 2.6, a, b, dark=i == 2, tsize=19, bsize=15)
    d.rect(s, LEFT, 5.1, WIDTH, 1.2, PEACHBG)
    d.text(s, LEFT + 0.3, 5.1, WIDTH - 0.6, 1.2, [[("Try it: ", True), ("git clone github.com/olonok69/DuckDB_ML, "
           "uv sync, uv run python demo/run_02_analytics.py. Then open Claude Code in the folder.", False)]], 15, INK,
           anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s, "duckdb.org/docs/2.0 · duckdb.org/community_extensions/extensions/duckdb_mcp · github.com/olonok69/youtube_ML")
    d.notes(s, "Three things to keep. DuckDB is the right tool when the work is analytical and the data lives in files, "
            "including your app's SQLite database. It is single-writer, so attach the app's database read-only and copy "
            "out for heavy work. And when you give a model access through MCP, make the surface small and lock it.")

    d.save()
    return len(d.prs.slides)


if __name__ == "__main__":
    n = build()
    print(f"wrote {os.path.relpath(OUT)} ({n} slides)")
