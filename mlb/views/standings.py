"""Division standings."""

from __future__ import annotations

from typing import List, Optional

from .. import ansi
from ..models import DivisionStandings
from ..table import Table


def division_table(division: DivisionStandings, width: int,
                   highlight: Optional[int] = None, wide: bool = False) -> List[str]:
    headers = ["", "W", "L", "PCT", "GB", "STRK"]
    aligns = ["left", "right", "right", "right", "right", "right"]
    if wide:
        headers += ["DIFF", "HOME", "AWAY", "L10"]
        aligns += ["right", "right", "right", "right"]

    table = Table(headers, aligns)
    for row in division.rows:
        name = row.name
        if row.clinched:
            name = f"{name} {ansi.paint('-' + row.clinched, 'bright_yellow')}"
        if highlight is not None and row.team_id == highlight:
            name = ansi.paint(name, "bold", "cyan")
        elif row.rank in (1, "1"):
            name = ansi.paint(name, "bold")

        streak = row.streak
        if streak.startswith("W"):
            streak = ansi.paint(streak, "bright_green")
        elif streak.startswith("L"):
            streak = ansi.paint(streak, "bright_red")

        cells = [name, row.wins, row.losses, row.pct, row.games_back, streak]
        if wide:
            diff = row.run_diff
            diff_text = f"+{diff}" if isinstance(diff, int) and diff > 0 else str(diff)
            if isinstance(diff, int):
                diff_text = ansi.paint(diff_text, "bright_green" if diff > 0 else "bright_red")
            cells += [diff_text, row.home, row.away, row.last_ten]
        table.add(*cells)

    out = [ansi.paint(f" {division.name}", "bold")]
    out.extend(table.render(max_width=width, indent="  "))
    return out


def render(divisions: List[DivisionStandings], width: int = 80,
           highlight: Optional[int] = None, wide: bool = False,
           season: Optional[int] = None) -> List[str]:
    if not divisions:
        return [ansi.paint("  No standings available.", "dim")]

    out: List[str] = []
    if season:
        out.append(ansi.paint(f" {season} Standings", "bold"))
        out.append(ansi.rule(min(width, 72)))
    for i, division in enumerate(divisions):
        if i:
            out.append("")
        out.extend(division_table(division, width, highlight=highlight, wide=wide))
    return out
