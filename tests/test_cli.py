import json

import pytest

from mlb import cli
from tests.conftest import load


class FakeTransport:
    """Serves fixture payloads based on the URL the client builds."""

    def __init__(self, feed="feed_live.json"):
        self.feed = feed
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        if "/schedule" in url:
            payload = load("schedule.json")
        elif "/feed/live" in url:
            payload = load(self.feed)
        elif "/standings" in url:
            payload = load("standings.json")
        else:
            payload = {}
        return json.dumps(payload).encode("utf-8")


@pytest.fixture
def transport(monkeypatch):
    fake = FakeTransport()
    monkeypatch.setattr("mlb.api._urlopen_transport", fake)

    original = cli._client

    def patched(args):
        client = original(args)
        client._transport = fake
        return client

    monkeypatch.setattr(cli, "_client", patched)
    return fake


def run(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr()


def test_no_arguments_prints_help(capsys):
    code, out = run([], capsys)
    assert code == 0
    assert "Watch MLB games from the terminal" in out.out


def test_games_lists_the_slate(transport, capsys):
    code, out = run(["games", "--date", "2025-08-16", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "SEA @ NYY" in out.out
    assert "776543" in out.out
    assert "date=2025-08-16" in transport.urls[0]


def test_games_filters_by_team(transport, capsys):
    code, _ = run(["games", "--team", "sea", "--no-color"], capsys)
    assert code == 0
    assert "teamId=136" in transport.urls[0]


def test_games_rejects_an_unknown_team(transport, capsys):
    code, out = run(["games", "--team", "isotopes"], capsys)
    assert code == 2
    assert "unknown team" in out.err


def test_watch_once_renders_the_game(transport, capsys):
    code, out = run(["watch", "776543", "--once", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "Seattle Mariners" in out.out
    assert "Bot 7th" in out.out
    assert "Aaron Judge" in out.out
    assert "/api/v1.1/game/776543/feed/live" in transport.urls[-1]


def test_watch_by_team_resolves_the_game_id(transport, capsys):
    code, out = run(["watch", "--team", "nyy", "--once", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "776543" in "".join(transport.urls)
    assert "Bot 7th" in out.out


def test_watch_accepts_a_bare_team_name(transport, capsys):
    code, out = run(["watch", "mariners", "--once", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "Bot 7th" in out.out


def test_watch_without_a_target_explains_itself(transport, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["watch"])
    assert "game id" in str(exc.value)


def test_watch_respects_the_plays_limit(transport, capsys):
    code, out = run(["watch", "776543", "--once", "--plays", "1", "--no-color", "--ascii"],
                    capsys)
    assert code == 0
    assert "Cody Bellinger flies out" in out.out
    assert "Cal Raleigh homers" not in out.out


def test_box_renders_both_lineups(transport, capsys):
    code, out = run(["box", "776543", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "Julio Rodríguez" in out.out
    assert "Gerrit Cole" in out.out
    assert "ERA" in out.out


def test_standings_renders_divisions(transport, capsys):
    code, out = run(["standings", "--season", "2025", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "AL East" in out.out
    assert "Toronto Blue Jays" in out.out
    assert "season=2025" in transport.urls[0]


def test_standings_league_filter(transport, capsys):
    code, _ = run(["standings", "--league", "nl", "--no-color"], capsys)
    assert code == 0
    assert "leagueId=104" in transport.urls[0]


def test_standings_wide_adds_columns(transport, capsys):
    code, out = run(["standings", "--wide", "--no-color", "--ascii"], capsys)
    assert code == 0
    assert "DIFF" in out.out and "L10" in out.out


def test_api_errors_are_reported_not_raised(monkeypatch, capsys):
    def boom(url, timeout):
        raise OSError("network unreachable")

    monkeypatch.setattr("mlb.api._urlopen_transport", boom)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    code, out = run(["standings"], capsys)
    assert code == 2
    assert "network unreachable" in out.err


DECORATIVE_GLYPHS = "●○◆◇⌂│─╌▸…·°"


@pytest.mark.parametrize("command", [
    ["watch", "776543", "--once"],
    ["box", "776543"],
    ["games"],
    ["standings"],
])
def test_ascii_mode_emits_no_decorative_glyphs(transport, capsys, command):
    """Player names keep their accents; the chrome must stay 7-bit."""
    code, out = run(command + ["--no-color", "--ascii"], capsys)
    assert code == 0
    found = [ch for ch in DECORATIVE_GLYPHS if ch in out.out]
    assert found == []


def test_no_color_output_has_no_escape_codes(transport, capsys):
    code, out = run(["games", "--no-color"], capsys)
    assert code == 0
    assert "\x1b[" not in out.out


def test_width_flag_is_respected(transport, capsys):
    code, out = run(["watch", "776543", "--once", "--no-color", "--ascii", "--width", "50"],
                    capsys)
    assert code == 0
    assert all(len(line) <= 50 for line in out.out.splitlines())


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert cli.VERSION in capsys.readouterr().out
