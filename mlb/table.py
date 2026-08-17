"""A minimal width-aware column renderer used by the box score and standings."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from . import ansi


class Table:
    """Fixed-column text table.

    Columns size themselves to their widest cell. Cells may contain ANSI
    styling; widths are computed on visible length.
    """

    def __init__(self, headers: Sequence[str], aligns: Optional[Sequence[str]] = None,
                 gap: int = 2, header_style: str = "dim"):
        self.headers = list(headers)
        self.aligns = list(aligns) if aligns else ["left"] * len(self.headers)
        if len(self.aligns) < len(self.headers):
            self.aligns += ["left"] * (len(self.headers) - len(self.aligns))
        self.gap = gap
        self.header_style = header_style
        self.rows: List[List[str]] = []
        self._separators: set = set()

    def add(self, *cells: object) -> None:
        row = ["" if c is None else str(c) for c in cells]
        if len(row) < len(self.headers):
            row += [""] * (len(self.headers) - len(row))
        self.rows.append(row[: len(self.headers)])

    def add_separator(self) -> None:
        """Mark a horizontal divider before the next row."""
        self._separators.add(len(self.rows))

    def widths(self) -> List[int]:
        widths = [ansi.vlen(h) for h in self.headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], ansi.vlen(cell))
        return widths

    def render(self, max_width: Optional[int] = None, indent: str = "") -> List[str]:
        widths = self.widths()
        sep = " " * self.gap
        if max_width is not None:
            widths = self._shrink(widths, max_width - len(indent), len(sep))

        def line(cells: Sequence[str], styles: Optional[str] = None) -> str:
            parts = []
            for i, cell in enumerate(cells):
                text = ansi.trunc(cell, widths[i])
                if styles:
                    text = ansi.paint(text, styles)
                parts.append(ansi.pad(text, widths[i], self.aligns[i]))
            return (indent + sep.join(parts)).rstrip()

        out = []
        if any(h for h in self.headers):
            out.append(line(self.headers, self.header_style))
        total = sum(widths) + len(sep) * (len(widths) - 1)
        for idx, row in enumerate(self.rows):
            if idx in self._separators:
                out.append(indent + ansi.rule(total))
            out.append(line(row))
        return out

    def _shrink(self, widths: List[int], budget: int, gap: int) -> List[int]:
        """Steal width from the widest column until the table fits."""
        total = sum(widths) + gap * (len(widths) - 1)
        if budget <= 0 or total <= budget:
            return widths
        widths = list(widths)
        overflow = total - budget
        while overflow > 0:
            widest = max(range(len(widths)), key=lambda i: widths[i])
            if widths[widest] <= 3:
                break
            take = min(overflow, widths[widest] - 3)
            widths[widest] -= take
            overflow -= take
        return widths


def columns(blocks: Iterable[Sequence[str]], gap: int = 4) -> List[str]:
    """Lay several multi-line blocks side by side, top-aligned."""
    blocks = [list(b) for b in blocks if b]
    if not blocks:
        return []
    height = max(len(b) for b in blocks)
    widths = [max((ansi.vlen(line) for line in b), default=0) for b in blocks]
    spacer = " " * gap
    out = []
    for row in range(height):
        parts = []
        for i, block in enumerate(blocks):
            cell = block[row] if row < len(block) else ""
            parts.append(ansi.pad(cell, widths[i]))
        out.append(spacer.join(parts).rstrip())
    return out
