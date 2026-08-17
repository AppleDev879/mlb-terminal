"""Small shared helpers: safe payload access, dates, formatting."""

from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "dig",
    "ordinal",
    "parse_date",
    "parse_iso",
    "local_time",
    "record",
    "plural",
    "first",
]


def dig(obj: Any, path: str, default: Any = None) -> Any:
    """Walk a dotted path through nested mappings/sequences.

    Returns ``default`` on any miss, so callers never have to guard every hop.
    Numeric path segments index into lists: ``dig(d, "dates.0.games")``.
    The StatsAPI omits keys freely depending on game state, so essentially all
    payload access in this package goes through here.
    """
    cur = obj
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, Mapping):
            if part not in cur:
                return default
            cur = cur[part]
        elif isinstance(cur, Sequence) and not isinstance(cur, (str, bytes)):
            try:
                idx = int(part)
            except ValueError:
                return default
            if not -len(cur) <= idx < len(cur):
                return default
            cur = cur[idx]
        else:
            return default
    return default if cur is None else cur


def first(*values: Any, default: Any = None) -> Any:
    """Return the first value that is neither None nor an empty string."""
    for value in values:
        if value is not None and value != "":
            return value
    return default


def ordinal(n: Any) -> str:
    """1 -> '1st', 2 -> '2nd', 13 -> '13th'."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def plural(n: int, word: str, suffix: str = "s") -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}{suffix}"


_RELATIVE = {"today": 0, "tomorrow": 1, "yesterday": -1}


def parse_date(value: Optional[str], today: Optional[dt.date] = None) -> dt.date:
    """Parse a user-supplied date.

    Accepts ``today``/``yesterday``/``tomorrow``, ``YYYY-MM-DD``, ``MM/DD``,
    ``MM/DD/YYYY``, and a signed day offset such as ``-2`` or ``+1``.
    """
    base = today or dt.date.today()
    if value is None:
        return base
    text = value.strip().lower()
    if not text:
        return base
    if text in _RELATIVE:
        return base + dt.timedelta(days=_RELATIVE[text])
    if text[0] in "+-":
        try:
            return base + dt.timedelta(days=int(text))
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d", "%m-%d", "%b %d %Y", "%b %d"):
        try:
            parsed = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt:
            parsed = parsed.replace(year=base.year)
        return parsed.date()
    raise ValueError(f"could not read {value!r} as a date (try YYYY-MM-DD or 'today')")


def parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    """Parse an API timestamp such as ``2025-08-16T23:05:00Z`` into an aware datetime."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp


def local_time(value: Optional[str], fmt: str = "%-I:%M %p") -> str:
    """Format a UTC API timestamp in the viewer's local timezone."""
    stamp = parse_iso(value)
    if stamp is None:
        return ""
    local = stamp.astimezone()
    try:
        return local.strftime(fmt)
    except ValueError:  # platforms without %-I (e.g. Windows)
        return local.strftime(fmt.replace("%-I", "%I")).lstrip("0")


def record(wins: Any, losses: Any) -> str:
    """'(68-54)' when both halves are present, otherwise ''."""
    if wins is None or losses is None:
        return ""
    return f"({wins}-{losses})"
