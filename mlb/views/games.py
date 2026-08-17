"""The day's slate — also the picker that turns a date into a game id."""

from __future__ import annotations

import datetime as dt
from typing import List, Optional

from .. import ansi
from ..models import ScheduledGame
from ..util import local_time


def status_style(game: ScheduledGame) -> str:
    if game.is_live:
        return "bright_green"
    if game.is_final:
        return "dim"
    return "cyan"


def _score_pair(game: ScheduledGame) -> str:
    """'4-3' with the leader emphasized, or blank before first pitch."""
    away, home = game.away.runs, game.home.runs
    if away is None or home is None:
        return ""
    away_text, home_text = str(away), str(home)
    if away > home:
        away_text = ansi.paint(away_text, "bold")
    elif home > away:
        home_text = ansi.paint(home_text, "bold")
    return f"{away_text}-{home_text}"


def render(games: List[ScheduledGame], date: dt.date, width: int = 80,
           highlight_team: Optional[int] = None) -> List[str]:
    heading = date.strftime("%A, %B %-d, %Y") if _supports_dash() else date.strftime("%A, %B %d, %Y")
    out = [ansi.paint(heading, "bold"), ansi.rule(min(width, 72))]

    if not games:
        out.append(ansi.paint("  No games scheduled.", "dim"))
        return out

    for game in games:
        marker = " "
        if game.is_live:
            marker = ansi.paint(ansi.glyph("●", "*"), "bright_green")
        elif highlight_team and highlight_team in (game.away.id, game.home.id):
            marker = ansi.paint(ansi.glyph("▸", ">"), "cyan")

        pk = ansi.paint(str(game.game_pk or ""), "dim")
        matchup = ansi.pad(f"{game.away.label} @ {game.home.label}", 11)
        score = ansi.pad(_score_pair(game), 6)
        status = ansi.paint(ansi.pad(game.status_text(), 12), status_style(game))

        extra = ""
        if game.is_preview:
            extra = local_time(game.raw.get("gameDate"))
            probables = [p for p in (game.away.probable, game.home.probable) if p]
            if probables:
                extra = f"{extra}  {' vs '.join(probables)}".strip()
        elif game.doubleheader in ("Y", "S") and game.game_number:
            extra = f"G{game.game_number}"

        line = f" {marker} {ansi.pad(pk, 6)}  {matchup}  {score} {status} {ansi.paint(extra, 'dim')}"
        out.append(ansi.trunc(line.rstrip(), width))

    out.append("")
    hint = "  mlb watch <id>" + ansi.glyph("   ·   ", "   |   ") + "mlb box <id>"
    out.append(ansi.paint(hint, "dim"))
    return out


def _supports_dash() -> bool:
    try:
        dt.date(2024, 1, 5).strftime("%-d")
        return True
    except ValueError:
        return False
