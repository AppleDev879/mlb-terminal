"""Persistent user settings, currently just a default team.

Stored as JSON at ``~/.config/mlb-terminal/config.json`` (or under
``XDG_CONFIG_HOME``). A missing or damaged file is never fatal: it reads as
empty settings, so a bad edit can't stop you from watching a game.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

from . import teams as team_ref

APP_DIR = "mlb-terminal"
CONFIG_FILENAME = "config.json"

#: Points the whole module at a different file. Set by the test suite, and
#: useful for keeping a separate config per shell.
PATH_ENV = "MLB_TERMINAL_CONFIG"

#: Overrides the stored team for a single shell/session.
TEAM_ENV = "MLB_TEAM"


def config_path() -> str:
    override = os.environ.get(PATH_ENV)
    if override:
        return os.path.expanduser(override)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, APP_DIR, CONFIG_FILENAME)


def load() -> Dict[str, Any]:
    path = config_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        print(f"warning: ignoring unreadable config at {path}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def save(data: Dict[str, Any]) -> str:
    """Write settings atomically so an interrupted write can't truncate them."""
    path = config_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def default_team(warn: bool = True) -> Optional[team_ref.Team]:
    """The team to use when no ``--team`` was given.

    ``MLB_TEAM`` wins over the config file, so a shell can override the
    stored default without editing it.
    """
    stored = load().get("team")
    from_env = os.environ.get(TEAM_ENV)
    source, value = (TEAM_ENV, from_env) if from_env else ("config", stored)
    if not value:
        return None
    team = team_ref.resolve(value)
    if team is None and warn:
        print(
            f"warning: {source} names an unknown team {value!r}; "
            f"run `mlb config --team <team>` to fix it",
            file=sys.stderr,
        )
    return team


def set_default_team(query: str) -> team_ref.Team:
    """Store a default team. Raises ValueError if the name isn't a team."""
    team = team_ref.resolve_or_raise(query)
    data = load()
    data["team"] = team.abbr
    save(data)
    return team


def clear_default_team() -> bool:
    """Remove the stored team. Returns True if there was one."""
    data = load()
    if "team" not in data:
        return False
    data.pop("team")
    save(data)
    return True
