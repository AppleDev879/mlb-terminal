"""The live game view: scoreboard, linescore, bases, count, and play feed."""

from __future__ import annotations

import textwrap
from typing import List, Optional

from .. import ansi
from ..models import LiveGame, Play
from ..table import columns
from ..util import dig, local_time, plural, record

MAX_INNING_COLUMNS = 12


# ------------------------------------------------------------------ header


def header(game: LiveGame, width: int) -> List[str]:
    away, home = game.away, game.home
    if game.is_preview:
        # Nothing has happened yet; an explicit 0-0 reads as a played tie.
        away_score = home_score = ""
    else:
        away_score = game.away.runs if game.away.runs is not None else 0
        home_score = game.home.runs if game.home.runs is not None else 0

    status = _status_text(game)

    # Line 2 carries the status, so the team column has to leave room for it:
    # "  " + name + "  " + score(3) + "     " + status
    natural = max(
        len(f"{away.name} {record(away.wins, away.losses)}".strip()),
        len(f"{home.name} {record(home.wins, home.losses)}".strip()),
    )
    name_width = max(8, min(natural, width - 12 - ansi.vlen(status)))

    def team_line(side, score, winning: bool) -> str:
        # Drop the city before resorting to an ellipsis on a narrow terminal.
        full = side.name or side.label
        if name_width < len(full) + 8 and side.short:
            full = side.short
        label = f"{full} {record(side.wins, side.losses)}".strip()
        label = ansi.pad(ansi.trunc(label, name_width), name_width)
        score_text = ansi.pad(str(score), 3, "right")
        if winning and (game.is_live or game.is_final):
            label = ansi.paint(label, "bold")
            score_text = ansi.paint(score_text, "bold", "bright_green")
        elif game.is_final:
            label = ansi.paint(label, "dim")
            score_text = ansi.paint(score_text, "dim")
        return f"  {label}  {score_text}"

    lines = [
        team_line(away, away_score, away_score > home_score),
        team_line(home, home_score, home_score > away_score),
    ]

    lines[1] = f"{lines[1]}     {_style_status(game, status)}"

    context = _sep().join(x for x in (game.venue, _weather(game)) if x)
    if context:
        lines.append(ansi.paint(f"  {ansi.trunc(context, width - 2)}", "dim"))
    return lines


def _sep() -> str:
    return ansi.glyph(" · ", " - ")


def _weather(game: LiveGame) -> str:
    if not game.weather_temp:
        return game.weather_condition
    degrees = ansi.glyph("°", "F")
    return f"{game.weather_condition} {game.weather_temp}{degrees}".strip()


def _status_text(game: LiveGame) -> str:
    """Status without styling, so its width can be measured before layout."""
    status = game.status_text()
    if game.is_live:
        outs = game.linescore.outs
        if outs is not None and (game.linescore.inning_state or "").lower() in ("top", "bottom"):
            status = f"{status}{_sep()}{plural(outs, 'out')}"
        return f"{ansi.glyph('●', '*')} {status}"
    if game.is_final:
        return status
    start = local_time(dig(game.raw, "gameData.datetime.dateTime"))
    return f"{status}  {start}" if start else status


def _style_status(game: LiveGame, status: str) -> str:
    if game.is_live:
        return ansi.paint(status, "bright_green")
    if game.is_final:
        return ansi.paint(status, "dim")
    return ansi.paint(status, "cyan")


# --------------------------------------------------------------- linescore


def linescore(game: LiveGame, width: int) -> List[str]:
    ls = game.linescore
    innings = list(ls.innings)
    played = max(len(innings), ls.scheduled_innings or 9)
    total = max(played, ls.current_inning or 0)

    numbers = list(range(1, total + 1))
    trimmed = False
    budget = max(3, (width - 26) // 3)
    if len(numbers) > min(MAX_INNING_COLUMNS, budget):
        keep = min(MAX_INNING_COLUMNS, budget)
        numbers = numbers[-keep:]
        trimmed = True

    by_num = {i.num: i for i in innings if i.num is not None}
    label_width = 5

    def cell(value) -> str:
        return ansi.pad("" if value is None else str(value), 2, "right")

    head = " " * (label_width + 2) + " ".join(cell(n) for n in numbers)
    head += "  " + ansi.glyph("│", "|") + " " + " ".join(cell(x) for x in ("R", "H", "E"))
    if trimmed:
        head = ansi.paint(ansi.glyph("…", "..") + head[2:], "dim")
    else:
        head = ansi.paint(head, "dim")

    def team_row(side, key: str) -> str:
        cells = []
        for num in numbers:
            inning = by_num.get(num)
            value = getattr(inning, f"{key}_runs", None) if inning else None
            if value is None:
                # An inning the home team never needed to bat in.
                if game.is_final or (ls.current_inning or 0) > num:
                    value = ansi.paint("-", "dim") if key == "home" else None
                elif (ls.current_inning or 0) == num:
                    value = None
            text = "" if value is None else str(value)
            if inning is not None and value not in (None, "") and str(value) != "0":
                text = ansi.paint(text, "bold")
            cells.append(ansi.pad(text, 2, "right"))
        label = ansi.pad(ansi.trunc(side.label, label_width), label_width)
        totals = " ".join(
            ansi.pad(str(v if v is not None else 0), 2, "right")
            for v in (side.runs, side.hits, side.errors)
        )
        return f"  {label} " + " ".join(cells) + "  " + ansi.glyph("│", "|") + " " + ansi.paint(totals, "bold")

    marker_away, marker_home = "  ", "  "
    if game.is_live:
        arrow = ansi.paint(ansi.glyph("▸", ">"), "bright_green")
        if ls.is_top:
            marker_away = arrow + " "
        else:
            marker_home = arrow + " "

    return [
        head,
        marker_away + team_row(game.away, "away")[2:],
        marker_home + team_row(game.home, "home")[2:],
    ]


# ------------------------------------------------------------ live details


def bases(on_first: bool, on_second: bool, on_third: bool) -> List[str]:
    """Three-line diamond, second base on top."""
    if ansi.unicode_enabled():
        filled, empty = ansi.paint("◆", "bright_yellow"), ansi.paint("◇", "gray")
        return [
            f"  {filled if on_second else empty}  ",
            f"{filled if on_third else empty}   {filled if on_first else empty}",
            ansi.paint("  " + ansi.glyph("⌂", "^") + "  ", "gray"),
        ]
    return [
        f"   {'[X]' if on_second else '[ ]'}   ",
        f"{'[X]' if on_third else '[ ]'}   {'[X]' if on_first else '[ ]'}",
        "    ^    ",
    ]


def outs_dots(outs: Optional[int]) -> str:
    count = outs or 0
    if ansi.unicode_enabled():
        on, off = "●", "○"
    else:
        on, off = "X", "-"
    dots = "".join(on if i < count else off for i in range(3))
    return ansi.paint(dots[:count], "bright_red") + ansi.paint(dots[count:], "gray")


def situation(game: LiveGame, width: int) -> List[str]:
    ls = game.linescore
    play = game.current_play

    count_block = [
        ansi.paint("COUNT", "dim"),
        ansi.paint(f"{ls.balls or 0}-{ls.strikes or 0}", "bold"),
        f"{outs_dots(ls.outs)} {ansi.paint(plural(ls.outs or 0, 'out'), 'dim')}",
    ]

    diamond = [ansi.paint("BASES", "dim")] + bases(ls.on_first, ls.on_second, ls.on_third)

    batter = play.batter if play and play.batter else ls.batter
    pitcher = play.pitcher if play and play.pitcher else ls.pitcher
    matchup_block = [ansi.paint("MATCHUP", "dim")]
    if pitcher:
        matchup_block.append(f"{ansi.paint('P', 'dim')} {pitcher}")
    if batter:
        matchup_block.append(f"{ansi.paint('B', 'dim')} {ansi.paint(batter, 'bold')}")
    if ls.on_deck:
        matchup_block.append(ansi.paint(f"  on deck: {ls.on_deck}", "dim"))

    lines = columns([count_block, diamond, matchup_block], gap=4)
    if max((ansi.vlen(line) for line in lines), default=0) + 2 > width:
        # Not enough room for three columns; put the matchup under the diamond.
        lines = columns([count_block, diamond], gap=4) + matchup_block
    return ["  " + ansi.trunc(line, width - 2) for line in lines]


def pitch_sequence(game: LiveGame, width: int) -> List[str]:
    play = game.current_play
    if not play or not play.pitches:
        return []
    parts = []
    for pitch in play.pitches[-8:]:
        call = (pitch.call or "").lower()
        if "ball" in call:
            style = "bright_green"
        elif "strike" in call or "foul" in call:
            style = "bright_red"
        elif "in play" in call:
            style = "bright_yellow"
        else:
            style = "white"
        speed = f" {pitch.speed:.0f}" if pitch.speed else ""
        parts.append(ansi.paint(f"{pitch.kind or '?'}{speed}", style))
    body = ansi.paint(_sep(), "dim").join(parts)
    return ["  " + ansi.paint("PITCHES  ", "dim") + ansi.trunc(body, max(10, width - 12))]


# --------------------------------------------------------------- play feed


def play_line(play: Play, width: int, indent: int = 2) -> List[str]:
    half = ansi.paint(ansi.pad(play.half_label(), 4), "dim")
    style = "bright_yellow" if play.is_scoring else None
    text = play.description or play.event
    wrap_width = max(20, width - indent - 6)
    wrapped = textwrap.wrap(text, wrap_width) or [""]
    lines = []
    for i, chunk in enumerate(wrapped):
        prefix = half if i == 0 else " " * 4
        body = ansi.paint(chunk, style) if style else chunk
        lines.append(" " * indent + f"{prefix}{body}")
    if play.is_scoring and play.away_score is not None and play.home_score is not None:
        lines[-1] += ansi.paint(f"  ({play.away_score}-{play.home_score})", "dim")
    return lines


def play_feed(game: LiveGame, width: int, limit: int = 5) -> List[str]:
    plays = game.completed_plays(limit)
    if not plays:
        return []
    out = ["", ansi.paint("  RECENT", "dim")]
    for play in reversed(plays):
        out.extend(play_line(play, width))
    return out


def decisions(game: LiveGame) -> List[str]:
    if not game.is_final:
        return []
    bits = []
    if game.winner:
        bits.append(f"{ansi.paint('W', 'dim')} {game.winner}")
    if game.loser:
        bits.append(f"{ansi.paint('L', 'dim')} {game.loser}")
    if game.save:
        bits.append(f"{ansi.paint('S', 'dim')} {game.save}")
    return ["", "  " + "   ".join(bits)] if bits else []


def probables(game: LiveGame) -> List[str]:
    if not game.is_preview:
        return []
    rows = []
    for side in (game.away, game.home):
        if side.probable:
            rows.append(f"  {ansi.paint(ansi.pad(side.label, 4), 'dim')} {side.probable}")
    if not rows:
        return []
    return ["", ansi.paint("  PROBABLES", "dim")] + rows


# ------------------------------------------------------------------ render


def render(game: LiveGame, width: int = 80, plays: int = 5,
           show_feed: bool = True) -> List[str]:
    out: List[str] = []
    out.extend(header(game, width))
    if not (game.is_preview and not game.linescore.innings):
        out.append("")
        out.extend(linescore(game, width))
    if game.is_live:
        out.append("")
        out.extend(situation(game, width))
        out.extend(pitch_sequence(game, width))
    out.extend(probables(game))
    if show_feed and not game.is_preview:
        out.extend(play_feed(game, width, plays))
    out.extend(decisions(game))
    return out
