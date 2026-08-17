"""Terminal styling and width-aware text helpers.

Everything here degrades to plain ASCII text when color or unicode is turned
off, so the same view code renders to a pipe, a dumb terminal, or a modern
emulator without branching.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from typing import Optional

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

RESET = "\x1b[0m"

_CODES = {
    "bold": "1",
    "dim": "2",
    "italic": "3",
    "underline": "4",
    "reverse": "7",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "gray": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bg_red": "41",
    "bg_green": "42",
    "bg_yellow": "43",
    "bg_blue": "44",
}

_color_enabled = True
_unicode_enabled = True


def configure(color: Optional[bool] = None, unicode_: Optional[bool] = None,
              stream=None) -> None:
    """Set global rendering capabilities.

    ``color``/``unicode_`` of None means autodetect. Detection honors NO_COLOR,
    FORCE_COLOR, TERM=dumb, and whether the stream is a TTY.
    """
    global _color_enabled, _unicode_enabled
    stream = stream or sys.stdout
    if color is None:
        _color_enabled = _detect_color(stream)
    else:
        _color_enabled = bool(color)
    if unicode_ is None:
        _unicode_enabled = _detect_unicode(stream)
    else:
        _unicode_enabled = bool(unicode_)


def _detect_color(stream) -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM", "") == "dumb":
        return False
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _detect_unicode(stream) -> bool:
    encoding = (getattr(stream, "encoding", None) or "").lower()
    if not encoding:
        return False
    return "utf" in encoding


def color_enabled() -> bool:
    return _color_enabled


def unicode_enabled() -> bool:
    return _unicode_enabled


def paint(text: str, *styles: str) -> str:
    """Wrap text in the named styles, or return it untouched when color is off."""
    if not _color_enabled or not styles or not text:
        return text
    codes = [_CODES[s] for s in styles if s in _CODES]
    if not codes:
        return text
    return f"\x1b[{';'.join(codes)}m{text}{RESET}"


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def vlen(text: str) -> int:
    """Visible length, ignoring escape sequences."""
    return len(strip_ansi(text))


def trunc(text: str, width: int, ellipsis: str = "…") -> str:
    """Truncate to a visible width, preserving styling of the kept portion."""
    if width <= 0:
        return ""
    if vlen(text) <= width:
        return text
    mark = ellipsis if _unicode_enabled else "..."
    keep = max(0, width - len(mark))
    out = []
    seen = 0
    idx = 0
    trailing_reset = False
    while idx < len(text) and seen < keep:
        match = _ANSI_RE.match(text, idx)
        if match:
            out.append(match.group())
            trailing_reset = match.group() != RESET
            idx = match.end()
            continue
        out.append(text[idx])
        seen += 1
        idx += 1
    out.append(mark)
    if trailing_reset and _color_enabled:
        out.append(RESET)
    return "".join(out)


def pad(text: str, width: int, align: str = "left") -> str:
    """Pad to a visible width. align is 'left', 'right', or 'center'."""
    gap = width - vlen(text)
    if gap <= 0:
        return text
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def term_size(default_cols: int = 80, default_rows: int = 24):
    try:
        size = shutil.get_terminal_size((default_cols, default_rows))
        return max(40, size.columns), max(10, size.lines)
    except Exception:
        return default_cols, default_rows


def glyph(unicode_char: str, ascii_char: str) -> str:
    """Pick a glyph based on whether the output can render unicode."""
    return unicode_char if _unicode_enabled else ascii_char


def rule(width: int, style: str = "dim") -> str:
    return paint(glyph("─", "-") * max(0, width), style)


def hr_light(width: int, style: str = "dim") -> str:
    return paint(glyph("╌", "-") * max(0, width), style)
