"""Static team reference data.

The API returns abbreviations in most payloads, but not all of them, and
resolving a ``--team`` flag shouldn't cost a round trip. This table is the
fallback; live payload values always win when present.
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional


class Team(NamedTuple):
    id: int
    abbr: str
    name: str
    short: str
    aliases: tuple = ()


TEAMS: List[Team] = [
    Team(108, "LAA", "Los Angeles Angels", "Angels", ("ana", "laa", "halos")),
    Team(109, "AZ", "Arizona Diamondbacks", "D-backs", ("ari", "dbacks", "d-backs", "diamondbacks")),
    Team(110, "BAL", "Baltimore Orioles", "Orioles", ("os", "birds")),
    Team(111, "BOS", "Boston Red Sox", "Red Sox", ("redsox", "sox")),
    Team(112, "CHC", "Chicago Cubs", "Cubs", ("chn", "cubbies")),
    Team(113, "CIN", "Cincinnati Reds", "Reds", ()),
    Team(114, "CLE", "Cleveland Guardians", "Guardians", ("guards", "indians")),
    Team(115, "COL", "Colorado Rockies", "Rockies", ("rox",)),
    Team(116, "DET", "Detroit Tigers", "Tigers", ()),
    Team(117, "HOU", "Houston Astros", "Astros", ("stros",)),
    Team(118, "KC", "Kansas City Royals", "Royals", ("kcr",)),
    Team(119, "LAD", "Los Angeles Dodgers", "Dodgers", ("lan",)),
    Team(120, "WSH", "Washington Nationals", "Nationals", ("was", "wsn", "nats")),
    Team(121, "NYM", "New York Mets", "Mets", ("nyn",)),
    Team(133, "ATH", "Athletics", "Athletics", ("oak", "as", "a's", "oakland")),
    Team(134, "PIT", "Pittsburgh Pirates", "Pirates", ("bucs",)),
    Team(135, "SD", "San Diego Padres", "Padres", ("sdp", "pads")),
    Team(136, "SEA", "Seattle Mariners", "Mariners", ("ms",)),
    Team(137, "SF", "San Francisco Giants", "Giants", ("sfg",)),
    Team(138, "STL", "St. Louis Cardinals", "Cardinals", ("cards", "st louis", "st. louis")),
    Team(139, "TB", "Tampa Bay Rays", "Rays", ("tbr", "tba")),
    Team(140, "TEX", "Texas Rangers", "Rangers", ()),
    Team(141, "TOR", "Toronto Blue Jays", "Blue Jays", ("jays", "bluejays")),
    Team(142, "MIN", "Minnesota Twins", "Twins", ()),
    Team(143, "PHI", "Philadelphia Phillies", "Phillies", ("phils",)),
    Team(144, "ATL", "Atlanta Braves", "Braves", ()),
    Team(145, "CWS", "Chicago White Sox", "White Sox", ("chw", "cha", "whitesox")),
    Team(146, "MIA", "Miami Marlins", "Marlins", ("fla", "fish")),
    Team(147, "NYY", "New York Yankees", "Yankees", ("nya", "yanks")),
    Team(158, "MIL", "Milwaukee Brewers", "Brewers", ("crew",)),
]

BY_ID: Dict[int, Team] = {t.id: t for t in TEAMS}

DIVISIONS: Dict[int, str] = {
    200: "AL West",
    201: "AL East",
    202: "AL Central",
    203: "NL West",
    204: "NL East",
    205: "NL Central",
}

LEAGUES: Dict[int, str] = {103: "American League", 104: "National League"}

# Order divisions the way standings pages do: East, Central, West.
DIVISION_ORDER = [201, 202, 200, 204, 205, 203]


def abbr_for(team_id: object, fallback: str = "") -> str:
    try:
        team = BY_ID.get(int(team_id))
    except (TypeError, ValueError):
        return fallback
    return team.abbr if team else fallback


def resolve(query: str) -> Optional[Team]:
    """Look up a team by abbreviation, nickname, city, id, or full name."""
    if query is None:
        return None
    text = str(query).strip().lower()
    if not text:
        return None
    if text.isdigit():
        team = BY_ID.get(int(text))
        if team:
            return team
    for team in TEAMS:
        if text == team.abbr.lower() or text == team.short.lower() or text == team.name.lower():
            return team
        if text in team.aliases:
            return team
    matches = [t for t in TEAMS if text in t.name.lower() or text in t.short.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_or_raise(query: str) -> Team:
    team = resolve(query)
    if team is None:
        known = ", ".join(sorted(t.abbr for t in TEAMS))
        raise ValueError(f"unknown team {query!r}. Try one of: {known}")
    return team
