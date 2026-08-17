import pytest

from mlb import teams


def test_thirty_teams_with_unique_ids_and_abbrs():
    assert len(teams.TEAMS) == 30
    assert len({t.id for t in teams.TEAMS}) == 30
    assert len({t.abbr for t in teams.TEAMS}) == 30


@pytest.mark.parametrize(
    "query,expected_id",
    [
        ("sea", 136),
        ("SEA", 136),
        ("mariners", 136),
        ("Seattle Mariners", 136),
        ("136", 136),
        ("nyy", 147),
        ("yanks", 147),
        ("oak", 133),
        ("a's", 133),
        ("cards", 138),
        ("wsh", 120),
        ("nats", 120),
        ("dbacks", 109),
    ],
)
def test_resolve_accepts_common_spellings(query, expected_id):
    team = teams.resolve(query)
    assert team is not None and team.id == expected_id


def test_resolve_returns_none_for_nonsense():
    assert teams.resolve("Springfield Isotopes") is None
    assert teams.resolve("") is None
    assert teams.resolve(None) is None


def test_resolve_or_raise_lists_the_options():
    with pytest.raises(ValueError) as exc:
        teams.resolve_or_raise("isotopes")
    assert "SEA" in str(exc.value)


def test_ambiguous_substring_is_not_guessed():
    # "New York" matches both the Mets and the Yankees.
    assert teams.resolve("new york") is None


def test_abbr_for_falls_back_gracefully():
    assert teams.abbr_for(147) == "NYY"
    assert teams.abbr_for(9999) == ""
    assert teams.abbr_for(None, "???") == "???"


def test_division_order_covers_every_division():
    assert set(teams.DIVISION_ORDER) == set(teams.DIVISIONS)
