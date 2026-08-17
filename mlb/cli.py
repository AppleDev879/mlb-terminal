"""Command line entry point."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from typing import List, Optional, Sequence

from . import ansi, teams as team_ref
from .api import ApiError, StatsAPI
from .live import run as run_live
from .models import LiveGame, ScheduledGame, parse_schedule, parse_standings
from .util import parse_date
from .views import box as box_view
from .views import game as game_view
from .views import games as games_view
from .views import standings as standings_view

PROG = "mlb"
VERSION = "0.1.0"

DEFAULT_INTERVAL = 10.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Watch MLB games from the terminal.",
        epilog=(
            "examples:\n"
            "  mlb games                    today's slate\n"
            "  mlb games --date 2025-07-04  a specific day\n"
            "  mlb watch 776543             follow a game live\n"
            "  mlb watch --team sea         follow today's Mariners game\n"
            "  mlb box 776543               full box score\n"
            "  mlb standings --team nyy     division standings\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {VERSION}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-color", action="store_true", help="disable ANSI color")
    common.add_argument("--ascii", action="store_true", help="ASCII-only output")
    common.add_argument("--width", type=int, default=None, help="output width (default: terminal width)")
    common.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout in seconds")

    sub = parser.add_subparsers(dest="command")

    games = sub.add_parser("games", parents=[common], aliases=["today", "scores"],
                           help="list games for a day")
    games.add_argument("--date", "-d", default="today", help="today, yesterday, or YYYY-MM-DD")
    games.add_argument("--team", "-t", default=None, help="only this team's games")
    games.add_argument("--watch", "-w", action="store_true", help="keep refreshing the list")
    games.add_argument("--interval", "-i", type=float, default=30.0, help="refresh seconds")
    games.set_defaults(func=cmd_games)

    watch = sub.add_parser("watch", parents=[common], aliases=["game"],
                           help="follow a single game live")
    watch.add_argument("game", nargs="?", default=None, help="game id (from `mlb games`)")
    watch.add_argument("--team", "-t", default=None, help="pick this team's game instead")
    watch.add_argument("--date", "-d", default="today", help="day to search when using --team")
    watch.add_argument("--interval", "-i", type=float, default=DEFAULT_INTERVAL,
                       help=f"refresh seconds (default {DEFAULT_INTERVAL:g})")
    watch.add_argument("--once", action="store_true", help="render one frame and exit")
    watch.add_argument("--plays", type=int, default=5, help="number of recent plays to show")
    watch.add_argument("--keep", action="store_true",
                       help="keep refreshing after the game ends")
    watch.set_defaults(func=cmd_watch)

    box = sub.add_parser("box", parents=[common], aliases=["boxscore"], help="box score for a game")
    box.add_argument("game", nargs="?", default=None, help="game id")
    box.add_argument("--team", "-t", default=None, help="pick this team's game instead")
    box.add_argument("--date", "-d", default="today", help="day to search when using --team")
    box.add_argument("--watch", "-w", action="store_true", help="keep refreshing")
    box.add_argument("--interval", "-i", type=float, default=20.0, help="refresh seconds")
    box.set_defaults(func=cmd_box)

    standings = sub.add_parser("standings", parents=[common], aliases=["rank"],
                               help="division standings")
    standings.add_argument("--season", "-s", type=int, default=None, help="season year")
    standings.add_argument("--team", "-t", default=None, help="highlight a team")
    standings.add_argument("--league", "-l", default=None, choices=["al", "nl", "AL", "NL"],
                           help="limit to one league")
    standings.add_argument("--wide", action="store_true", help="add run diff and splits")
    standings.add_argument("--date", "-d", default=None, help="standings as of a date")
    standings.set_defaults(func=cmd_standings)

    return parser


# ------------------------------------------------------------------ helpers


def _width(args) -> int:
    if args.width:
        return max(40, args.width)
    return ansi.term_size()[0]


def _client(args) -> StatsAPI:
    return StatsAPI(timeout=args.timeout)


def _find_game(client: StatsAPI, team_query: str, date: dt.date) -> ScheduledGame:
    """Resolve --team plus a date to a single game, preferring the live one."""
    team = team_ref.resolve_or_raise(team_query)
    payload = client.schedule(date=date, team_id=team.id)
    games = parse_schedule(payload)
    if not games:
        raise SystemExit(
            f"no {team.short} game on {date.isoformat()}. "
            f"Try `{PROG} games --date {date.isoformat()}`."
        )
    live = [g for g in games if g.is_live]
    if live:
        return live[0]
    upcoming = [g for g in games if g.is_preview]
    return upcoming[0] if upcoming else games[-1]


def _resolve_game_pk(client: StatsAPI, args) -> int:
    if getattr(args, "game", None):
        text = str(args.game).strip()
        if text.isdigit():
            return int(text)
        # Allow `mlb watch sea` as shorthand for `--team sea`.
        game = _find_game(client, text, parse_date(getattr(args, "date", "today")))
        return int(game.game_pk)
    if getattr(args, "team", None):
        game = _find_game(client, args.team, parse_date(args.date))
        return int(game.game_pk)
    raise SystemExit(
        f"give a game id or a team: `{PROG} watch 776543` or `{PROG} watch --team sea`.\n"
        f"Run `{PROG} games` to list today's game ids."
    )


def _emit(lines: List[str]) -> None:
    sys.stdout.write("\n".join(line.rstrip() for line in lines) + "\n")


# ----------------------------------------------------------------- commands


def cmd_games(args) -> int:
    client = _client(args)
    date = parse_date(args.date)
    team = team_ref.resolve_or_raise(args.team) if args.team else None
    width = _width(args)

    def fetch():
        return parse_schedule(client.schedule(date=date, team_id=team.id if team else None))

    def render(games):
        return games_view.render(games, date, width=width,
                                 highlight_team=team.id if team else None)

    if args.watch:
        return run_live(fetch, render, interval=max(5.0, args.interval))
    _emit(render(fetch()))
    return 0


def cmd_watch(args) -> int:
    client = _client(args)
    game_pk = _resolve_game_pk(client, args)
    width = _width(args)

    def fetch() -> LiveGame:
        return LiveGame.from_feed(client.game_feed(game_pk))

    def render(game: LiveGame) -> List[str]:
        return game_view.render(game, width=width, plays=args.plays)

    stop = None if args.keep else (lambda game: game.is_final)
    return run_live(
        fetch,
        render,
        interval=max(3.0, args.interval),
        once=args.once,
        stop_when=stop,
    )


def cmd_box(args) -> int:
    client = _client(args)
    game_pk = _resolve_game_pk(client, args)
    width = _width(args)

    def fetch() -> LiveGame:
        return LiveGame.from_feed(client.game_feed(game_pk))

    def render(game: LiveGame) -> List[str]:
        return box_view.render(game, width=width)

    if args.watch:
        return run_live(fetch, render, interval=max(5.0, args.interval),
                        stop_when=lambda game: game.is_final)
    _emit(render(fetch()))
    return 0


def cmd_standings(args) -> int:
    client = _client(args)
    width = _width(args)
    date = parse_date(args.date) if args.date else None
    season = args.season or (date.year if date else dt.date.today().year)

    league_ids = (103, 104)
    if args.league:
        league_ids = (103,) if args.league.lower() == "al" else (104,)

    team = team_ref.resolve_or_raise(args.team) if args.team else None
    payload = client.standings(season=season, league_ids=league_ids, date=date)
    divisions = parse_standings(payload)
    _emit(standings_view.render(divisions, width=width,
                                highlight=team.id if team else None,
                                wide=args.wide, season=season))
    return 0


# --------------------------------------------------------------------- main


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    ansi.configure(
        color=False if getattr(args, "no_color", False) else None,
        unicode_=False if getattr(args, "ascii", False) else None,
    )

    try:
        return args.func(args) or 0
    except ApiError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
