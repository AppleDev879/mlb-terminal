import datetime as dt

from mlb import ansi
from mlb.models import LiveGame, parse_schedule, parse_standings
from mlb.views import box as box_view
from mlb.views import game as game_view
from mlb.views import games as games_view
from mlb.views import standings as standings_view


def text_of(lines):
    return "\n".join(ansi.strip_ansi(line) for line in lines)


# ------------------------------------------------------------- game view


def test_live_game_view_shows_the_essentials(live_payload):
    game = LiveGame.from_feed(live_payload)
    out = text_of(game_view.render(game, width=80))
    assert "Seattle Mariners (68-54)" in out
    assert "New York Yankees (70-52)" in out
    assert "Bot 7th" in out
    assert "2 outs" in out
    assert "Aaron Judge" in out
    assert "Andrés Muñoz" in out
    assert "Yankee Stadium" in out


def test_live_game_view_includes_linescore_totals(live_payload):
    game = LiveGame.from_feed(live_payload)
    lines = [ansi.strip_ansi(x) for x in game_view.linescore(game, 80)]
    assert lines[1].split()[0] == "SEA"
    assert lines[1].split()[-3:] == ["4", "9", "0"]
    assert lines[2].split()[-3:] == ["3", "7", "1"]


def test_linescore_trims_columns_on_a_narrow_terminal(live_payload):
    game = LiveGame.from_feed(live_payload)
    for line in game_view.linescore(game, 52):
        assert ansi.vlen(line) <= 52


def test_pitch_sequence_lists_the_current_at_bat(live_payload):
    game = LiveGame.from_feed(live_payload)
    out = text_of(game_view.pitch_sequence(game, 80))
    assert "PITCHES" in out
    assert "FF 99" in out
    assert "SL 88" in out


def test_play_feed_is_newest_first(live_payload):
    game = LiveGame.from_feed(live_payload)
    out = text_of(game_view.play_feed(game, 80, limit=4))
    bellinger = out.index("Cody Bellinger flies out")
    raleigh = out.index("Cal Raleigh homers")
    assert bellinger < raleigh


def test_play_feed_wraps_long_descriptions(live_payload):
    game = LiveGame.from_feed(live_payload)
    for line in game_view.play_feed(game, 60, limit=5):
        assert ansi.vlen(line) <= 60


def test_bases_diamond_marks_occupied_bases():
    ansi.configure(color=False, unicode_=False)
    lines = game_view.bases(on_first=True, on_second=False, on_third=True)
    assert "[ ]" in lines[0]                    # second is empty
    assert lines[1].count("[X]") == 2           # first and third occupied


def test_outs_dots_ascii():
    ansi.configure(color=False, unicode_=False)
    assert ansi.strip_ansi(game_view.outs_dots(2)) == "XX-"
    assert ansi.strip_ansi(game_view.outs_dots(0)) == "---"


def test_final_game_view_shows_decisions(final_payload):
    game = LiveGame.from_feed(final_payload)
    out = text_of(game_view.render(game, width=80))
    assert "Final" in out
    assert "W Andrés Muñoz" in out
    assert "L Luke Weaver" in out
    assert "S Matt Brash" in out


def test_final_game_view_omits_the_live_situation_block(final_payload):
    game = LiveGame.from_feed(final_payload)
    out = text_of(game_view.render(game, width=80))
    assert "COUNT" not in out
    assert "BASES" not in out


def test_preview_game_view_shows_probables_not_a_fake_score(preview_payload):
    game = LiveGame.from_feed(preview_payload)
    out = text_of(game_view.render(game, width=80))
    assert "PROBABLES" in out
    assert "Bryan Woo" in out
    assert "Gerrit Cole" in out
    assert "Scheduled" in out
    assert " 0" not in out.splitlines()[0]


def test_game_view_of_an_empty_feed_renders_something():
    lines = game_view.render(LiveGame.from_feed({}), width=80)
    assert lines
    assert isinstance(text_of(lines), str)


def test_game_view_never_exceeds_the_requested_width(live_payload):
    game = LiveGame.from_feed(live_payload)
    for width in (48, 60, 80, 120):
        for line in game_view.render(game, width=width):
            assert ansi.vlen(line) <= width, (width, line)


# -------------------------------------------------------------- box view


def test_box_view_lists_both_lineups(live_payload):
    game = LiveGame.from_feed(live_payload)
    out = text_of(box_view.render(game, width=90))
    assert "Seattle Mariners" in out and "New York Yankees" in out
    assert "Julio Rodríguez" in out
    assert "Aaron Judge" in out
    assert "Gerrit Cole" in out
    assert "AB" in out and "RBI" in out and "ERA" in out


def test_box_view_totals_row(live_payload):
    game = LiveGame.from_feed(live_payload)
    lines = [ansi.strip_ansi(x) for x in box_view.batting_table(game.away_box, 90)]
    totals = [x for x in lines if x.strip().startswith("Totals")][0].split()
    assert totals[1:4] == ["34", "4", "9"]  # AB, R, H


def test_box_view_indents_substitutes(live_payload):
    game = LiveGame.from_feed(live_payload)
    lines = [ansi.strip_ansi(x) for x in box_view.batting_table(game.away_box, 90)]
    rivas = [x for x in lines if "Leo Rivas" in x][0]
    julio = [x for x in lines if "Julio Rodríguez" in x][0]
    assert rivas.index("Leo") > julio.index("Julio")


def test_box_view_handles_a_game_with_no_box_score(preview_payload):
    game = LiveGame.from_feed(preview_payload)
    out = text_of(box_view.render(game, width=80))
    assert "No box score yet." in out


def test_box_view_fits_the_width(live_payload):
    game = LiveGame.from_feed(live_payload)
    for line in box_view.render(game, width=64):
        assert ansi.vlen(line) <= 64


# ------------------------------------------------------------ games view


def test_games_view_lists_the_slate(schedule_payload):
    games = parse_schedule(schedule_payload)
    out = text_of(games_view.render(games, dt.date(2025, 8, 16), width=80))
    assert "SEA @ NYY" in out
    assert "CHC @ MIL" in out
    assert "776543" in out
    assert "Bot 7th" in out
    assert "Final" in out


def test_games_view_shows_probables_for_upcoming_games(schedule_payload):
    games = parse_schedule(schedule_payload)
    out = text_of(games_view.render(games, dt.date(2025, 8, 16), width=100))
    assert "Yoshinobu Yamamoto vs Logan Webb" in out


def test_games_view_with_no_games():
    out = text_of(games_view.render([], dt.date(2025, 12, 25), width=80))
    assert "No games scheduled." in out


def test_games_view_fits_the_width(schedule_payload):
    games = parse_schedule(schedule_payload)
    for line in games_view.render(games, dt.date(2025, 8, 16), width=56):
        assert ansi.vlen(line) <= 56


# --------------------------------------------------------- standings view


def test_standings_view_renders_divisions(standings_payload):
    divisions = parse_standings(standings_payload)
    out = text_of(standings_view.render(divisions, width=80, season=2025))
    assert "AL East" in out and "AL West" in out
    assert "Toronto Blue Jays" in out
    assert "2025 Standings" in out
    assert "PCT" in out and "GB" in out and "STRK" in out


def test_standings_wide_mode_adds_columns(standings_payload):
    divisions = parse_standings(standings_payload)
    narrow = text_of(standings_view.render(divisions, width=100))
    wide = text_of(standings_view.render(divisions, width=100, wide=True))
    assert "DIFF" not in narrow and "L10" not in narrow
    assert "DIFF" in wide and "L10" in wide and "+105" in wide


def test_standings_view_with_nothing_to_show():
    assert "No standings available." in text_of(standings_view.render([], width=80))


def test_standings_view_fits_the_width(standings_payload):
    divisions = parse_standings(standings_payload)
    for line in standings_view.render(divisions, width=50, wide=True):
        assert ansi.vlen(line) <= 50
