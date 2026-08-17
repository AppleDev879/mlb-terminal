"""Typed views over Stats API payloads.

Every field is parsed through :func:`mlb.util.dig`, so a payload missing keys
(a game that hasn't started, a suspended game, an API tweak) yields empty
values rather than a traceback. Views are free to assume these objects exist.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, List, Optional

from . import teams as team_ref
from .util import dig, first, ordinal, parse_iso

LIVE_STATES = {"Live"}
FINAL_STATES = {"Final", "Game Over"}


# ---------------------------------------------------------------- schedule


@dataclass
class TeamSide:
    id: Optional[int] = None
    name: str = ""
    abbr: str = ""
    short: str = ""
    wins: Optional[int] = None
    losses: Optional[int] = None
    runs: Optional[int] = None
    hits: Optional[int] = None
    errors: Optional[int] = None
    probable: str = ""

    @classmethod
    def from_schedule(cls, payload: dict) -> "TeamSide":
        team_id = dig(payload, "team.id")
        ref = team_ref.BY_ID.get(team_id) if isinstance(team_id, int) else None
        return cls(
            id=team_id,
            name=first(dig(payload, "team.name"), ref.name if ref else "", default=""),
            abbr=first(
                dig(payload, "team.abbreviation"),
                team_ref.abbr_for(team_id),
                default="",
            ),
            short=first(
                dig(payload, "team.teamName"), ref.short if ref else "", default=""
            ),
            wins=dig(payload, "leagueRecord.wins"),
            losses=dig(payload, "leagueRecord.losses"),
            runs=dig(payload, "score"),
            probable=dig(payload, "probablePitcher.fullName", ""),
        )

    @property
    def label(self) -> str:
        return self.abbr or self.short or self.name or "???"


@dataclass
class ScheduledGame:
    game_pk: Optional[int] = None
    start: Optional[dt.datetime] = None
    state: str = ""
    detailed_state: str = ""
    away: TeamSide = field(default_factory=TeamSide)
    home: TeamSide = field(default_factory=TeamSide)
    inning: Optional[int] = None
    inning_state: str = ""
    venue: str = ""
    series_description: str = ""
    game_number: Optional[int] = None
    doubleheader: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict) -> "ScheduledGame":
        away = TeamSide.from_schedule(dig(payload, "teams.away", {}) or {})
        home = TeamSide.from_schedule(dig(payload, "teams.home", {}) or {})
        away.runs = first(away.runs, dig(payload, "linescore.teams.away.runs"))
        home.runs = first(home.runs, dig(payload, "linescore.teams.home.runs"))
        return cls(
            game_pk=payload.get("gamePk"),
            start=parse_iso(payload.get("gameDate")),
            state=dig(payload, "status.abstractGameState", ""),
            detailed_state=dig(payload, "status.detailedState", ""),
            away=away,
            home=home,
            inning=dig(payload, "linescore.currentInning"),
            inning_state=dig(payload, "linescore.inningState", ""),
            venue=dig(payload, "venue.name", ""),
            series_description=payload.get("seriesDescription", "") or "",
            game_number=payload.get("gameNumber"),
            doubleheader=payload.get("doubleHeader", "") or "",
            raw=payload,
        )

    @property
    def is_live(self) -> bool:
        return self.state in LIVE_STATES

    @property
    def is_final(self) -> bool:
        return self.state in FINAL_STATES or self.detailed_state in FINAL_STATES

    @property
    def is_preview(self) -> bool:
        return not self.is_live and not self.is_final

    def matchup(self) -> str:
        return f"{self.away.label} @ {self.home.label}"

    def status_text(self) -> str:
        """Short status: inning for live games, 'Final' or a start time otherwise."""
        detailed = self.detailed_state or self.state
        if self.is_live:
            state = (self.inning_state or "").strip()
            short = {"Top": "Top", "Bottom": "Bot", "Middle": "Mid", "End": "End"}.get(
                state, state
            )
            if self.inning:
                return f"{short} {ordinal(self.inning)}".strip()
            return detailed or "Live"
        if self.is_final:
            if self.inning and self.inning != 9:
                return f"Final/{self.inning}"
            return "Final"
        return detailed


def parse_schedule(payload: dict) -> List[ScheduledGame]:
    """Flatten a schedule response (possibly several dates) into games."""
    games: List[ScheduledGame] = []
    for date_entry in dig(payload, "dates", []) or []:
        for game in dig(date_entry, "games", []) or []:
            games.append(ScheduledGame.from_payload(game))
    games.sort(key=lambda g: (g.start or dt.datetime.max.replace(tzinfo=dt.timezone.utc),
                              g.game_pk or 0))
    return games


# --------------------------------------------------------------- live feed


@dataclass
class Pitch:
    number: Optional[int] = None
    kind: str = ""            # "FF", "SL", ...
    kind_name: str = ""
    call: str = ""            # "Called Strike", "Ball", "In play, run(s)"
    speed: Optional[float] = None
    balls: Optional[int] = None
    strikes: Optional[int] = None
    is_pitch: bool = True
    description: str = ""

    @classmethod
    def from_event(cls, payload: dict) -> "Pitch":
        return cls(
            number=payload.get("pitchNumber"),
            kind=dig(payload, "details.type.code", ""),
            kind_name=dig(payload, "details.type.description", ""),
            call=dig(payload, "details.description", ""),
            speed=dig(payload, "pitchData.startSpeed"),
            balls=dig(payload, "count.balls"),
            strikes=dig(payload, "count.strikes"),
            is_pitch=bool(payload.get("isPitch", False)),
            description=dig(payload, "details.description", ""),
        )

    def summary(self) -> str:
        bits = []
        if self.number:
            bits.append(f"{self.number}.")
        if self.kind:
            bits.append(self.kind)
        if self.speed:
            bits.append(f"{self.speed:.0f}")
        if self.call:
            bits.append(self.call)
        return " ".join(bits)


@dataclass
class Play:
    inning: Optional[int] = None
    half: str = ""            # "top" / "bottom"
    description: str = ""
    event: str = ""
    is_scoring: bool = False
    is_complete: bool = False
    away_score: Optional[int] = None
    home_score: Optional[int] = None
    rbi: Optional[int] = None
    batter: str = ""
    pitcher: str = ""
    balls: Optional[int] = None
    strikes: Optional[int] = None
    outs: Optional[int] = None
    pitches: List[Pitch] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict) -> "Play":
        events = [
            Pitch.from_event(e)
            for e in (dig(payload, "playEvents", []) or [])
            if e.get("isPitch")
        ]
        return cls(
            inning=dig(payload, "about.inning"),
            half=(dig(payload, "about.halfInning", "") or "").lower(),
            description=dig(payload, "result.description", "") or "",
            event=dig(payload, "result.event", "") or "",
            is_scoring=bool(dig(payload, "about.isScoringPlay", False)),
            is_complete=bool(dig(payload, "about.isComplete", False)),
            away_score=dig(payload, "result.awayScore"),
            home_score=dig(payload, "result.homeScore"),
            rbi=dig(payload, "result.rbi"),
            batter=dig(payload, "matchup.batter.fullName", "") or "",
            pitcher=dig(payload, "matchup.pitcher.fullName", "") or "",
            balls=dig(payload, "count.balls"),
            strikes=dig(payload, "count.strikes"),
            outs=dig(payload, "count.outs"),
            pitches=events,
        )

    def half_label(self) -> str:
        mark = "T" if self.half.startswith("top") else "B"
        return f"{mark}{self.inning}" if self.inning else mark


@dataclass
class Inning:
    num: Optional[int] = None
    away_runs: Optional[int] = None
    home_runs: Optional[int] = None

    @classmethod
    def from_payload(cls, payload: dict) -> "Inning":
        return cls(
            num=payload.get("num"),
            away_runs=dig(payload, "away.runs"),
            home_runs=dig(payload, "home.runs"),
        )


@dataclass
class Linescore:
    innings: List[Inning] = field(default_factory=list)
    current_inning: Optional[int] = None
    inning_state: str = ""
    is_top: bool = True
    balls: Optional[int] = None
    strikes: Optional[int] = None
    outs: Optional[int] = None
    on_first: bool = False
    on_second: bool = False
    on_third: bool = False
    batter: str = ""
    on_deck: str = ""
    pitcher: str = ""
    scheduled_innings: int = 9

    @classmethod
    def from_payload(cls, payload: dict) -> "Linescore":
        return cls(
            innings=[Inning.from_payload(i) for i in (dig(payload, "innings", []) or [])],
            current_inning=dig(payload, "currentInning"),
            inning_state=dig(payload, "inningState", "") or "",
            is_top=bool(dig(payload, "isTopInning", True)),
            balls=dig(payload, "balls"),
            strikes=dig(payload, "strikes"),
            outs=dig(payload, "outs"),
            on_first=dig(payload, "offense.first") is not None,
            on_second=dig(payload, "offense.second") is not None,
            on_third=dig(payload, "offense.third") is not None,
            batter=dig(payload, "offense.batter.fullName", "") or "",
            on_deck=dig(payload, "offense.onDeck.fullName", "") or "",
            pitcher=dig(payload, "defense.pitcher.fullName", "") or "",
            scheduled_innings=dig(payload, "scheduledInnings", 9) or 9,
        )


@dataclass
class BatterLine:
    name: str = ""
    position: str = ""
    order: str = ""
    substitute: bool = False
    at_bats: Any = 0
    runs: Any = 0
    hits: Any = 0
    rbi: Any = 0
    walks: Any = 0
    strikeouts: Any = 0
    home_runs: Any = 0
    left_on_base: Any = 0
    avg: str = ""


@dataclass
class PitcherLine:
    name: str = ""
    innings: str = "0.0"
    hits: Any = 0
    runs: Any = 0
    earned_runs: Any = 0
    walks: Any = 0
    strikeouts: Any = 0
    home_runs: Any = 0
    pitches: Any = 0
    strikes: Any = 0
    era: str = ""
    note: str = ""


@dataclass
class TeamBox:
    name: str = ""
    abbr: str = ""
    batters: List[BatterLine] = field(default_factory=list)
    pitchers: List[PitcherLine] = field(default_factory=list)
    runs: Any = 0
    hits: Any = 0
    errors: Any = 0
    notes: List[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict) -> "TeamBox":
        players = dig(payload, "players", {}) or {}
        team_id = dig(payload, "team.id")

        batters = []
        for pid in dig(payload, "batters", []) or []:
            entry = players.get(f"ID{pid}") or {}
            stats = dig(entry, "stats.batting", {}) or {}
            if not stats and not dig(entry, "battingOrder"):
                continue
            order = str(dig(entry, "battingOrder", "") or "")
            batters.append(
                BatterLine(
                    name=dig(entry, "person.fullName", "") or "",
                    position=dig(entry, "position.abbreviation", "") or "",
                    order=order,
                    substitute=bool(order) and not order.endswith("00"),
                    at_bats=stats.get("atBats", 0),
                    runs=stats.get("runs", 0),
                    hits=stats.get("hits", 0),
                    rbi=stats.get("rbi", 0),
                    walks=stats.get("baseOnBalls", 0),
                    strikeouts=stats.get("strikeOuts", 0),
                    home_runs=stats.get("homeRuns", 0),
                    left_on_base=stats.get("leftOnBase", 0),
                    avg=dig(entry, "seasonStats.batting.avg", "") or "",
                )
            )

        pitchers = []
        for pid in dig(payload, "pitchers", []) or []:
            entry = players.get(f"ID{pid}") or {}
            stats = dig(entry, "stats.pitching", {}) or {}
            pitchers.append(
                PitcherLine(
                    name=dig(entry, "person.fullName", "") or "",
                    innings=str(stats.get("inningsPitched", "0.0")),
                    hits=stats.get("hits", 0),
                    runs=stats.get("runs", 0),
                    earned_runs=stats.get("earnedRuns", 0),
                    walks=stats.get("baseOnBalls", 0),
                    strikeouts=stats.get("strikeOuts", 0),
                    home_runs=stats.get("homeRuns", 0),
                    pitches=stats.get("pitchesThrown", stats.get("numberOfPitches", 0)),
                    strikes=stats.get("strikes", 0),
                    era=dig(entry, "seasonStats.pitching.era", "") or "",
                )
            )

        return cls(
            name=dig(payload, "team.name", "") or "",
            abbr=first(dig(payload, "team.abbreviation"), team_ref.abbr_for(team_id), default=""),
            batters=batters,
            pitchers=pitchers,
            runs=dig(payload, "teamStats.batting.runs", 0),
            hits=dig(payload, "teamStats.batting.hits", 0),
            errors=dig(payload, "teamStats.fielding.errors", 0),
            notes=[n.get("value", "") for n in (dig(payload, "note", []) or [])],
        )


@dataclass
class LiveGame:
    game_pk: Optional[int] = None
    state: str = ""
    detailed_state: str = ""
    start: Optional[dt.datetime] = None
    venue: str = ""
    away: TeamSide = field(default_factory=TeamSide)
    home: TeamSide = field(default_factory=TeamSide)
    linescore: Linescore = field(default_factory=Linescore)
    current_play: Optional[Play] = None
    plays: List[Play] = field(default_factory=list)
    away_box: TeamBox = field(default_factory=TeamBox)
    home_box: TeamBox = field(default_factory=TeamBox)
    winner: str = ""
    loser: str = ""
    save: str = ""
    weather_condition: str = ""
    weather_temp: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_feed(cls, payload: dict) -> "LiveGame":
        game_data = dig(payload, "gameData", {}) or {}
        live_data = dig(payload, "liveData", {}) or {}
        linescore = Linescore.from_payload(dig(live_data, "linescore", {}) or {})

        def side(key: str, box_key: str) -> TeamSide:
            team = dig(game_data, f"teams.{key}", {}) or {}
            team_id = team.get("id")
            ref = team_ref.BY_ID.get(team_id) if isinstance(team_id, int) else None
            return TeamSide(
                id=team_id,
                name=first(team.get("name"), ref.name if ref else "", default=""),
                abbr=first(team.get("abbreviation"), team_ref.abbr_for(team_id), default=""),
                short=first(team.get("teamName"), ref.short if ref else "", default=""),
                wins=dig(team, "record.wins"),
                losses=dig(team, "record.losses"),
                runs=dig(live_data, f"linescore.teams.{box_key}.runs"),
                hits=dig(live_data, f"linescore.teams.{box_key}.hits"),
                errors=dig(live_data, f"linescore.teams.{box_key}.errors"),
                probable=dig(game_data, f"probablePitchers.{key}.fullName", "") or "",
            )

        all_plays = [Play.from_payload(p) for p in (dig(live_data, "plays.allPlays", []) or [])]
        current_raw = dig(live_data, "plays.currentPlay")
        current = Play.from_payload(current_raw) if current_raw else None

        return cls(
            game_pk=first(dig(game_data, "game.pk"), payload.get("gamePk")),
            state=dig(game_data, "status.abstractGameState", "") or "",
            detailed_state=dig(game_data, "status.detailedState", "") or "",
            start=parse_iso(dig(game_data, "datetime.dateTime")),
            venue=dig(game_data, "venue.name", "") or "",
            away=side("away", "away"),
            home=side("home", "home"),
            linescore=linescore,
            current_play=current,
            plays=all_plays,
            away_box=TeamBox.from_payload(dig(live_data, "boxscore.teams.away", {}) or {}),
            home_box=TeamBox.from_payload(dig(live_data, "boxscore.teams.home", {}) or {}),
            winner=dig(live_data, "decisions.winner.fullName", "") or "",
            loser=dig(live_data, "decisions.loser.fullName", "") or "",
            save=dig(live_data, "decisions.save.fullName", "") or "",
            weather_condition=dig(game_data, "weather.condition", "") or "",
            weather_temp=str(dig(game_data, "weather.temp", "") or ""),
            raw=payload,
        )

    @property
    def is_live(self) -> bool:
        return self.state in LIVE_STATES

    @property
    def is_final(self) -> bool:
        return self.state in FINAL_STATES or self.detailed_state in FINAL_STATES

    @property
    def is_preview(self) -> bool:
        return not self.is_live and not self.is_final

    def status_text(self) -> str:
        if self.is_live:
            state = (self.linescore.inning_state or "").strip()
            short = {"Top": "Top", "Bottom": "Bot", "Middle": "Mid", "End": "End"}.get(
                state, state
            )
            inning = self.linescore.current_inning
            if inning:
                return f"{short} {ordinal(inning)}".strip()
            return self.detailed_state or "Live"
        if self.is_final:
            inning = self.linescore.current_inning
            if inning and inning != self.linescore.scheduled_innings:
                return f"Final/{inning}"
            return "Final"
        return self.detailed_state or self.state or "Scheduled"

    def completed_plays(self, limit: int = 6) -> List[Play]:
        """Most recent finished plays that carry a description, newest last."""
        done = [p for p in self.plays if p.description]
        if self.current_play is not None and done and not done[-1].is_complete:
            done = done[:-1]
        return done[-limit:] if limit else done


# --------------------------------------------------------------- standings


@dataclass
class StandingsRow:
    team_id: Optional[int] = None
    name: str = ""
    abbr: str = ""
    wins: Any = 0
    losses: Any = 0
    pct: str = ""
    games_back: str = "-"
    wildcard_games_back: str = "-"
    streak: str = ""
    run_diff: Any = 0
    home: str = ""
    away: str = ""
    last_ten: str = ""
    clinched: str = ""
    rank: Any = 0

    @classmethod
    def from_payload(cls, payload: dict) -> "StandingsRow":
        team_id = dig(payload, "team.id")
        splits = {}
        for entry in dig(payload, "records.splitRecords", []) or []:
            if not isinstance(entry, dict):
                continue
            # `type` is a plain string ("home") in most responses but an object
            # ({"code": "home"}) in some hydrations.
            kind = entry.get("type")
            code = kind.get("code", "") if isinstance(kind, dict) else str(kind or "")
            splits[code] = entry

        def split(code: str) -> str:
            entry = splits.get(code)
            if not entry:
                return ""
            return f"{entry.get('wins', 0)}-{entry.get('losses', 0)}"

        last_ten = ""
        for overall in dig(payload, "records.overallRecords", []) or []:
            if not isinstance(overall, dict):
                continue
            kind = overall.get("type")
            code = kind.get("code", "") if isinstance(kind, dict) else str(kind or "")
            if code == "lastTen":
                last_ten = f"{overall.get('wins', 0)}-{overall.get('losses', 0)}"

        return cls(
            team_id=team_id,
            name=first(dig(payload, "team.name"), team_ref.abbr_for(team_id), default=""),
            abbr=first(
                dig(payload, "team.abbreviation"), team_ref.abbr_for(team_id), default=""
            ),
            wins=payload.get("wins", 0),
            losses=payload.get("losses", 0),
            pct=payload.get("winningPercentage", "") or "",
            games_back=str(payload.get("gamesBack", "-") or "-"),
            wildcard_games_back=str(payload.get("wildCardGamesBack", "-") or "-"),
            streak=dig(payload, "streak.streakCode", "") or "",
            run_diff=payload.get("runDifferential", 0),
            home=split("home"),
            away=split("away"),
            last_ten=last_ten,
            clinched=payload.get("clinchIndicator", "") or "",
            rank=payload.get("divisionRank", 0),
        )


@dataclass
class DivisionStandings:
    division_id: Optional[int] = None
    name: str = ""
    rows: List[StandingsRow] = field(default_factory=list)


def parse_standings(payload: dict) -> List[DivisionStandings]:
    divisions: List[DivisionStandings] = []
    for record in dig(payload, "records", []) or []:
        division_id = dig(record, "division.id")
        name = first(
            dig(record, "division.nameShort"),
            team_ref.DIVISIONS.get(division_id),
            dig(record, "division.name"),
            default="Division",
        )
        rows = [
            StandingsRow.from_payload(r) for r in (dig(record, "teamRecords", []) or [])
        ]
        rows.sort(key=lambda r: _rank_key(r))
        divisions.append(DivisionStandings(division_id=division_id, name=name, rows=rows))

    order = {d: i for i, d in enumerate(team_ref.DIVISION_ORDER)}
    divisions.sort(key=lambda d: order.get(d.division_id, 99))
    return divisions


def _rank_key(row: StandingsRow):
    try:
        return (int(row.rank), -int(row.wins))
    except (TypeError, ValueError):
        return (99, 0)
