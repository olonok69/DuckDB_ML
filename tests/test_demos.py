"""Rerun the demos on the committed sample and compare with demo/output/.

Demos 1 and 2 are deterministic, so their reports must match byte for byte. Demo 3
runs small and only checks that every engine agrees; its sizes and timings depend
on the machine and the DuckDB version.
"""

import difflib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
EXPECTED = DEMO / "output"


def run(script: str, tmp_path: Path, *extra: str) -> str:
    done = subprocess.run([sys.executable, str(DEMO / script), "--out", str(tmp_path), *extra],
                          cwd=DEMO, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    name = script.removeprefix("run_").removesuffix(".py") + ".txt"
    return (tmp_path / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("script", ["run_01_attach_sqlite.py", "run_02_analytics.py"])
def test_report_matches_committed_output(script, tmp_path):
    name = script.removeprefix("run_").removesuffix(".py") + ".txt"
    got, want = run(script, tmp_path), (EXPECTED / name).read_text(encoding="utf-8")
    diff = "".join(difflib.unified_diff(want.splitlines(True), got.splitlines(True), "committed", "this run"))
    assert got == want, diff


def test_parquet_demo_engines_agree(tmp_path):
    report = run("run_03_parquet.py", tmp_path, "--rows", "20000")
    assert "return the same years, row counts and view sums: yes" in report
    assert "Parquet, zstd (columnar)" in report


def test_sample_is_reproducible(tmp_path):
    sys.path.insert(0, str(ROOT / "data"))
    import make_sample

    rebuilt = make_sample.build(tmp_path / "sample.sqlite3")

    # Compare the SQL dump, not the bytes: the file layout depends on the SQLite version.
    def dump(path):
        con = sqlite3.connect(path)
        try:
            return list(con.iterdump())
        finally:
            con.close()

    assert dump(rebuilt) == dump(ROOT / "data" / "sample.sqlite3")
