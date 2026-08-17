from mlb.models import LiveGame, parse_schedule, parse_standings


# ---------------------------------------------------------------- schedule


def test_parse_schedule_reads_every_game(schedule_payload):
    games = parse_schedule(schedule_payload)
    assert len(games) == 3
    assert {g.game_pk for g in games} == {776543, 776544, 776545}


def test_parse_schedule_sorts_by_start_time(schedule_payload):
    games = parse_schedule(schedule_payload)
    assert [g.game_pk for g in games] == [776544, 776543, 776545]


def test_schedule_game_states(schedule_payload):
    by_pk = {g.game_pk: g for g in parse_schedule(schedule_payload)}
    assert by_pk[776543].is_live
    assert by_pk[776544].is_final
    assert by_pk[776545].is_preview


def test_schedule_game_status_text(schedule_payload):
    by_pk = {g.game_pk: g for g in parse_schedule(schedule_payload)}
    assert by_pk[776543].status_text() == "Bot 7th"
    assert by_pk[776544].status_text() == "Final"
    assert by_pk[776545].status_text() == "Scheduled"


def test_schedule_game_scores_and_teams(schedule_payload):
    game = {g.game_pk: g for g in parse_schedule(schedule_payload)}[776543]
    assert game.away.abbr == "SEA"
    assert game.home.abbr == "NYY"
    assert (game.away.runs, game.home.runs) == (4, 3)
    assert game.matchup() == "SEA @ NYY"


def test_schedule_survives_an_empty_payload():
    assert parse_schedule({}) == []
    assert parse_schedule({"dates": [{"games": []}]}) == []


# --------------------------------------------------------------- live feed


def test_live_game_core_fields(live_payload):
    game = LiveGame.from_feed(live_payload)
    assert game.game_pk == 776543
    assert game.is_live and not game.is_final
    assert game.away.abbr == "SEA" and game.home.abbr == "NYY"
    assert (game.away.runs, game.home.runs) == (4, 3)
    assert (game.away.hits, game.home.hits) == (9, 7)
    assert game.venue == "Yankee Stadium"
    assert game.status_text() == "Bot 7th"


def test_live_linescore_state(live_payload):
    ls = LiveGame.from_feed(live_payload).linescore
    assert (ls.balls, ls.strikes, ls.outs) == (2, 2, 2)
    assert ls.is_top is False
    assert ls.current_inning == 7
    assert len(ls.innings) == 7
    assert ls.innings[0].home_runs == 1


def test_baserunners_come_from_offense_keys(live_payload):
    ls = LiveGame.from_feed(live_payload).linescore
    assert ls.on_first is True
    assert ls.on_second is False
    assert ls.on_third is True
    assert ls.batter == "Aaron Judge"
    assert ls.on_deck == "Cody Bellinger"
    assert ls.pitcher == "Andrés Muñoz"


def test_current_play_pitches(live_payload):
    play = LiveGame.from_feed(live_payload).current_play
    assert play is not None
    assert play.batter == "Aaron Judge"
    assert len(play.pitches) == 4
    assert play.pitches[0].kind == "FF"
    assert play.pitches[0].call == "Ball"
    assert play.pitches[-1].speed == 87.6


def test_completed_plays_excludes_the_at_bat_in_progress(live_payload):
    game = LiveGame.from_feed(live_payload)
    plays = game.completed_plays(limit=10)
    assert all(p.description for p in plays)
    assert plays[-1].description.startswith("Cody Bellinger flies out")


def test_completed_plays_respects_the_limit(live_payload):
    game = LiveGame.from_feed(live_payload)
    assert len(game.completed_plays(limit=2)) == 2


def test_scoring_play_is_flagged(live_payload):
    game = LiveGame.from_feed(live_payload)
    homer = [p for p in game.plays if p.event == "Home Run"][0]
    assert homer.is_scoring
    assert homer.half_label() == "T6"
    assert (homer.away_score, homer.home_score) == (4, 3)


def test_box_score_batting_lines(live_payload):
    game = LiveGame.from_feed(live_payload)
    assert len(game.away_box.batters) == 10
    judge = game.home_box.batters[0]
    assert judge.name == "Aaron Judge"
    assert judge.position == "RF"
    assert (judge.at_bats, judge.hits, judge.rbi, judge.home_runs) == (3, 2, 2, 1)
    assert judge.avg == ".331"
    assert judge.substitute is False


def test_box_score_marks_substitutes(live_payload):
    game = LiveGame.from_feed(live_payload)
    rivas = [b for b in game.away_box.batters if b.name == "Leo Rivas"][0]
    assert rivas.substitute is True


def test_box_score_pitching_lines(live_payload):
    game = LiveGame.from_feed(live_payload)
    woo = game.away_box.pitchers[0]
    assert woo.name == "Bryan Woo"
    assert woo.innings == "6.0"
    assert (woo.strikeouts, woo.earned_runs) == (7, 3)
    assert woo.era == "2.98"


def test_final_game_decisions(final_payload):
    game = LiveGame.from_feed(final_payload)
    assert game.is_final
    assert game.status_text() == "Final"
    assert game.winner == "Andrés Muñoz"
    assert game.loser == "Luke Weaver"
    assert game.save == "Matt Brash"


def test_extra_innings_status(final_payload):
    payload = dict(final_payload)
    payload["liveData"] = dict(final_payload["liveData"])
    linescore = dict(final_payload["liveData"]["linescore"])
    linescore["currentInning"] = 11
    payload["liveData"]["linescore"] = linescore
    assert LiveGame.from_feed(payload).status_text() == "Final/11"


def test_preview_game_has_no_plays(preview_payload):
    game = LiveGame.from_feed(preview_payload)
    assert game.is_preview
    assert game.plays == []
    assert game.current_play is None
    assert game.away.probable == "Bryan Woo"


def test_live_game_from_empty_feed_does_not_explode():
    game = LiveGame.from_feed({})
    assert game.game_pk is None
    assert game.plays == []
    assert game.linescore.innings == []
    assert game.away_box.batters == []
    assert game.status_text() == "Scheduled"


def test_live_game_tolerates_missing_subtrees(live_payload):
    payload = {"gameData": live_payload["gameData"], "liveData": {}}
    game = LiveGame.from_feed(payload)
    assert game.away.abbr == "SEA"
    assert game.linescore.outs is None
    assert game.completed_plays() == []


# --------------------------------------------------------------- standings


def test_parse_standings_divisions_in_order(standings_payload):
    divisions = parse_standings(standings_payload)
    assert [d.name for d in divisions] == ["AL East", "AL West"]


def test_standings_rows_sorted_by_division_rank(standings_payload):
    east = parse_standings(standings_payload)[0]
    assert [r.abbr for r in east.rows] == ["TOR", "NYY", "TB", "BAL", "BOS"]


def test_standings_row_fields(standings_payload):
    east = parse_standings(standings_payload)[0]
    yankees = east.rows[1]
    assert (yankees.wins, yankees.losses) == (70, 52)
    assert yankees.pct == ".574"
    assert yankees.games_back == "2.0"
    assert yankees.streak == "W1"
    assert yankees.run_diff == 105
    assert yankees.home == "37-24"
    assert yankees.away == "33-28"
    assert yankees.last_ten == "6-4"


def test_standings_handles_object_style_split_types():
    payload = {
        "records": [
            {
                "division": {"id": 201},
                "teamRecords": [
                    {
                        "team": {"id": 147},
                        "wins": 70,
                        "losses": 52,
                        "divisionRank": "1",
                        "records": {
                            "splitRecords": [
                                {"wins": 37, "losses": 24, "type": {"code": "home"}},
                            ],
                            "overallRecords": [
                                {"wins": 6, "losses": 4, "type": {"code": "lastTen"}},
                            ],
                        },
                    }
                ],
            }
        ]
    }
    row = parse_standings(payload)[0].rows[0]
    assert row.home == "37-24"
    assert row.last_ten == "6-4"
    assert row.abbr == "NYY"  # filled in from the static table


def test_parse_standings_of_nothing():
    assert parse_standings({}) == []
