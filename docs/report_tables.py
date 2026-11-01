"""Read the tables out of the demo reports in demo/output/, so the deck quotes the
numbers of the last committed run instead of copies typed by hand."""

from __future__ import annotations

import re
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "demo" / "output"


def _value(cell: str):
    text = cell.strip()
    if re.fullmatch(r"-?[\d,]+", text):
        return int(text.replace(",", ""))
    if re.fullmatch(r"-?[\d,]+\.\d+", text):
        return float(text.replace(",", ""))
    return text


def table(report: str, section_prefix: str) -> list[dict]:
    """Rows of the first table under the section whose title starts with `section_prefix`."""
    lines = (OUTPUT / report).read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(section_prefix))
    rule = next(i for i in range(start + 2, len(lines)) if re.fullmatch(r"-+( +-+)*", lines[i]))
    spans = [m.span() for m in re.finditer(r"-+", lines[rule])]
    header = lines[rule - 1]

    def cut(line):
        cells = []
        for k, (a, b) in enumerate(spans):
            end = spans[k + 1][0] if k + 1 < len(spans) else None
            cells.append(line[a:end].strip() if end else line[a:].strip())
        return cells

    names = cut(header)
    rows = []
    for line in lines[rule + 1:]:
        if line.startswith("(") and line.endswith(")"):
            break
        rows.append({n: _value(c) for n, c in zip(names, cut(line))})
    return rows


def line_with(report: str, prefix: str) -> str:
    for line in (OUTPUT / report).read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line
    raise KeyError(prefix)
