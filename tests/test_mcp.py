"""Smoke test for demo 4: the server script runs up to the line that starts serving.

Needs the duckdb_mcp community extension. Where it cannot be downloaded the test
skips, unless REQUIRE_MCP=1 (set in CI), where a missing extension is a failure.
"""

import os
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "demo" / "mcp" / "init-server.sql"


def _statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in body.split(";\n") if s.strip()]


def test_server_script_until_start(monkeypatch):
    monkeypatch.chdir(ROOT)
    con = duckdb.connect()
    try:
        con.execute("INSTALL duckdb_mcp FROM community")
        con.execute("LOAD duckdb_mcp")
    except duckdb.Error as exc:
        if os.environ.get("REQUIRE_MCP") == "1":
            raise
        pytest.skip(f"duckdb_mcp not available here: {exc}")

    statements = _statements(INIT.read_text(encoding="utf-8"))
    assert statements[-1].startswith("PRAGMA mcp_server_start")
    for statement in statements[:-1]:
        con.execute(statement)

    assert con.sql("SELECT count(*) FROM videos").fetchone()[0] > 0
    # The configuration is locked: a later SET is refused.
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")
