"""Command line entry point."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import List, Optional, Sequence

from . import ansi, config, teams as team_ref
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
            "  mlb config --team sea        save a default, then just `mlb watch`\n"
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

    settings = sub.add_parser(
        "config", parents=[common], help="show or change saved settings",
        description=(
            "Saved settings, currently a default team used whenever --team is "
            "omitted. The MLB_TEAM environment variable overrides it."
        ),
    )
    settings.add_argument("--team", "-t", default=None, help="save this team as the default")
    settings.add_argument("--clear", action="store_true", help="forget the saved team")
    settings.set_defaults(func=cmd_config)

    return parser


# ------------------------------------------------------------------ helpers


def _width(args) -> int:
    if args.width:
        return max(40, args.width)
    return ansi.term_size()[0]


def _client(args) -> StatsAPI:
    return StatsAPI(timeout=args.timeout)


def _default_team():
    """The configured team, or None. Never raises — a bad value just warns."""
    return config.default_team()


def _team_arg(args):
    """Resolve --team, falling back to the configured default."""
    if getattr(args, "team", None):
        return team_ref.resolve_or_raise(args.team)
    return _default_team()


def _find_game(client: StatsAPI, team, date: dt.date) -> ScheduledGame:
    """Resolve a team plus a date to a single game, preferring the live one."""
    if not isinstance(team, team_ref.Team):
        team = team_ref.resolve_or_raise(team)
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
    team = _team_arg(args)
    if team is not None:
        game = _find_game(client, team, parse_date(args.date))
        return int(game.game_pk)
    raise SystemExit(
        f"give a game id or a team: `{PROG} watch 776543` or `{PROG} watch --team sea`.\n"
        f"Set a default with `{PROG} config --team sea` to just run `{PROG} watch`.\n"
        f"Run `{PROG} games` to list today's game ids."
    )


def _emit(lines: List[str]) -> None:
    sys.stdout.write("\n".join(line.rstrip() for line in lines) + "\n")


# ----------------------------------------------------------------- commands


def cmd_games(args) -> int:
    client = _client(args)
    date = parse_date(args.date)
    width = _width(args)

    # An explicit --team narrows the slate; a configured default only marks it,
    # since `mlb games` is how you see what else is on.
    filter_team = team_ref.resolve_or_raise(args.team) if args.team else None
    mark_team = filter_team or _default_team()

    def fetch():
        return parse_schedule(
            client.schedule(date=date, team_id=filter_team.id if filter_team else None)
        )

    def render(games):
        return games_view.render(games, date, width=width,
                                 highlight_team=mark_team.id if mark_team else None)

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

    team = _team_arg(args)
    payload = client.standings(season=season, league_ids=league_ids, date=date)
    divisions = parse_standings(payload)
    _emit(standings_view.render(divisions, width=width,
                                highlight=team.id if team else None,
                                wide=args.wide, season=season))
    return 0


def cmd_config(args) -> int:
    if args.team and args.clear:
        print(f"{PROG}: pass either --team or --clear, not both", file=sys.stderr)
        return 2

    if args.team:
        team = config.set_default_team(args.team)
        _emit([
            f"  default team: {ansi.paint(team.name, 'bold')} ({team.abbr})",
            ansi.paint(f"  saved to {config.config_path()}", "dim"),
            "",
            ansi.paint(f"  `{PROG} watch` now follows the {team.short}.", "dim"),
        ])
        return 0

    if args.clear:
        if config.clear_default_team():
            _emit([ansi.paint("  default team cleared.", "dim")])
        else:
            _emit([ansi.paint("  no default team was set.", "dim")])
        return 0

    return _show_config()


def _show_config() -> int:
    path = config.config_path()
    stored = config.load().get("team")
    override = os.environ.get(config.TEAM_ENV)
    team = config.default_team()

    lines = []
    if team is None:
        lines.append(ansi.paint("  no default team set", "dim"))
        lines.append("")
        lines.append(ansi.paint(f"  set one with `{PROG} config --team sea`", "dim"))
    else:
        source = f"{config.TEAM_ENV} environment variable" if override else path
        lines.append(f"  default team: {ansi.paint(team.name, 'bold')} ({team.abbr})")
        lines.append(ansi.paint(f"  from {source}", "dim"))
        if override and stored and str(stored).upper() != team.abbr:
            lines.append(ansi.paint(f"  (overriding saved {stored})", "dim"))
    _emit(lines)
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
