"""Box score: batting and pitching lines for both teams."""

from __future__ import annotations

from typing import List

from .. import ansi
from ..models import LiveGame, TeamBox
from ..table import Table


def batting_table(box: TeamBox, width: int) -> List[str]:
    table = Table(
        ["", "AB", "R", "H", "RBI", "BB", "SO", "AVG"],
        ["left", "right", "right", "right", "right", "right", "right", "right"],
    )
    for line in box.batters:
        name = line.name
        if line.substitute:
            name = "  " + name
        if line.position:
            name = f"{name} {ansi.paint(line.position, 'dim')}"
        hits = str(line.hits)
        if _as_int(line.home_runs) > 0:
            hits = ansi.paint(f"{hits}", "bright_yellow")
        elif _as_int(line.hits) >= 3:
            hits = ansi.paint(hits, "bold")
        table.add(name, line.at_bats, line.runs, hits, line.rbi, line.walks,
                  line.strikeouts, line.avg)

    if box.batters:
        table.add_separator()
        table.add(
            ansi.paint("Totals", "dim"),
            _total(box.batters, "at_bats"),
            box.runs,
            box.hits,
            _total(box.batters, "rbi"),
            _total(box.batters, "walks"),
            _total(box.batters, "strikeouts"),
            "",
        )
    return table.render(max_width=width, indent="  ")


def pitching_table(box: TeamBox, width: int) -> List[str]:
    table = Table(
        ["", "IP", "H", "R", "ER", "BB", "SO", "P-S", "ERA"],
        ["left", "right", "right", "right", "right", "right", "right", "right", "right"],
    )
    for line in box.pitchers:
        pitches = ""
        if _as_int(line.pitches) or _as_int(line.strikes):
            pitches = f"{line.pitches}-{line.strikes}"
        table.add(line.name, line.innings, line.hits, line.runs, line.earned_runs,
                  line.walks, line.strikeouts, pitches, line.era)
    return table.render(max_width=width, indent="  ")


def team_section(box: TeamBox, width: int) -> List[str]:
    title = box.name or box.abbr or "Team"
    out = [ansi.paint(f" {title}", "bold"), ansi.rule(min(width, 76))]
    if not box.batters and not box.pitchers:
        out.append(ansi.paint("  No box score yet.", "dim"))
        return out
    out.extend(batting_table(box, width))
    if box.pitchers:
        out.append("")
        out.extend(pitching_table(box, width))
    for note in box.notes:
        if note:
            out.append(ansi.paint(f"  {note}", "dim"))
    return out


def render(game: LiveGame, width: int = 80) -> List[str]:
    from .game import decisions, header, linescore

    out = header(game, width)
    out.append("")
    out.extend(linescore(game, width))
    out.append("")
    out.extend(team_section(game.away_box, width))
    out.append("")
    out.extend(team_section(game.home_box, width))
    out.extend(decisions(game))
    return out


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _total(lines, attr: str) -> int:
    return sum(_as_int(getattr(line, attr, 0)) for line in lines)
