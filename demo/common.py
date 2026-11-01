"""Shared pieces for the demos: open DuckDB, attach the SQLite file, write a report.

Every demo takes --db (default: data/sample.sqlite3). Point it at youtube_ML's
db.sqlite3 after `manage.py sync_youtube` to run the same SQL on the real channel.
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample.sqlite3"
OUTPUT = ROOT / "demo" / "output"


def parse_args(description: str, **extra) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("YOUTUBE_DB", SAMPLE)),
                        help="SQLite file with youtube_ML's catalog_* tables (default: data/sample.sqlite3)")
    parser.add_argument("--out", type=Path, default=OUTPUT, help="Folder for the text report")
    for flag, kwargs in extra.items():
        parser.add_argument(flag, **kwargs)
    return parser.parse_args()


def _quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def load_sqlite(con: duckdb.DuckDBPyConnection) -> None:
    """LOAD the sqlite extension, installing it from the DuckDB repository the first time."""
    try:
        con.execute("LOAD sqlite")
    except duckdb.Error:
        con.execute("INSTALL sqlite")
        con.execute("LOAD sqlite")


def connect(db: Path, alias: str = "yt") -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB with the SQLite file attached read-only. Nothing is copied."""
    if not db.exists():
        raise SystemExit(f"{db} not found. Run data/make_sample.py, or pass --db.")
    con = duckdb.connect()
    load_sqlite(con)
    con.execute(f"ATTACH {_quote(db)} AS {alias} (TYPE sqlite, READ_ONLY)")
    return con


PLAIN_INTS = {"year", "position", "minutes"}  # columns printed without thousands separators


def _cell(value, column: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value) if column in PLAIN_INTS else f"{value:,}"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_cell(v) for v in value) + "]"
    return str(value)


class Report:
    """Plain-text report, printed and saved, so runs can be compared line by line."""

    def __init__(self, name: str, title: str):
        self.name = name
        self.lines: list[str] = [title, "=" * len(title)]

    def say(self, text: str = "") -> None:
        self.lines.append(text)

    def section(self, title: str) -> None:
        self.lines += ["", title, "-" * len(title)]

    def sql(self, text: str) -> None:
        self.lines += ["", *("    " + line for line in text.strip().splitlines()), ""]

    def table(self, rel_or_rows, columns: list[str] | None = None, max_width: int = 48) -> None:
        if columns is None:
            columns = rel_or_rows.columns
            rows = rel_or_rows.fetchall()
        else:
            rows = rel_or_rows
        cells = [[_cell(v, columns[i]) for i, v in enumerate(row)] for row in rows]
        cells = [[c if len(c) <= max_width else c[: max_width - 3] + "..." for c in row] for row in cells]
        widths = [max([len(col)] + [len(row[i]) for row in cells]) for i, col in enumerate(columns)]
        numeric = [all(isinstance(r[i], (int, float, Decimal)) and not isinstance(r[i], bool)
                       for r in rows if r[i] is not None) and rows for i in range(len(columns))]

        def fmt(row):
            return "  ".join(c.rjust(w) if numeric[i] else c.ljust(w)
                             for i, (c, w) in enumerate(zip(row, widths))).rstrip()

        self.lines.append(fmt(columns))
        self.lines.append("  ".join("-" * w for w in widths))
        self.lines += [fmt(row) for row in cells]
        self.lines.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")

    def save(self, out: Path) -> Path:
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.name}.txt"
        text = "\n".join(self.lines).rstrip() + "\n"
        path.write_text(text, encoding="utf-8")
        print(text)
        return path
