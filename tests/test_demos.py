"""Rerun the demos on the committed sample and compare with demo/output/.

Demos 1 and 2 are deterministic, so their reports must match byte for byte. Demo 3
runs small and only checks that every engine agrees; its sizes and timings depend
on the machine and the DuckDB version.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
EXPECTED = DEMO / "output"


def run(script: str, tmp_path: Path, *extra: str) -> str:
    subprocess.run([sys.executable, str(DEMO / script), "--out", str(tmp_path), *extra],
                   check=True, cwd=DEMO, capture_output=True, text=True)
    name = script.removeprefix("run_").removesuffix(".py") + ".txt"
    return (tmp_path / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("script", ["run_01_attach_sqlite.py", "run_02_analytics.py"])
def test_report_matches_committed_output(script, tmp_path):
    name = script.removeprefix("run_").removesuffix(".py") + ".txt"
    assert run(script, tmp_path) == (EXPECTED / name).read_text(encoding="utf-8")


def test_parquet_demo_engines_agree(tmp_path):
    report = run("run_03_parquet.py", tmp_path, "--rows", "20000")
    assert "return the same years, row counts and view sums: yes" in report
    assert "Parquet, zstd (columnar)" in report


def test_sample_is_reproducible(tmp_path):
    sys.path.insert(0, str(ROOT / "data"))
    import make_sample

    rebuilt = make_sample.build(tmp_path / "sample.sqlite3")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    assert digest(rebuilt) == digest(ROOT / "data" / "sample.sqlite3")
