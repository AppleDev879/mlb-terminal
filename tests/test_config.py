import json
import os

import pytest

from mlb import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point the config module at a throwaway file, not the real ~/.config."""
    path = tmp_path / "config.json"
    monkeypatch.setenv(config.PATH_ENV, str(path))
    monkeypatch.delenv(config.TEAM_ENV, raising=False)
    return path


def test_no_config_reads_as_empty(isolated_config):
    assert not isolated_config.exists()
    assert config.load() == {}
    assert config.default_team() is None


def test_set_and_read_back_a_default_team(isolated_config):
    team = config.set_default_team("mariners")
    assert team.abbr == "SEA"
    assert json.loads(isolated_config.read_text()) == {"team": "SEA"}
    assert config.default_team().id == 136


def test_setting_a_team_keeps_other_settings(isolated_config):
    config.save({"team": "NYY", "future_setting": 42})
    config.set_default_team("sea")
    assert json.loads(isolated_config.read_text()) == {"team": "SEA", "future_setting": 42}


def test_set_default_team_rejects_an_unknown_name(isolated_config):
    with pytest.raises(ValueError):
        config.set_default_team("isotopes")
    assert not isolated_config.exists()


def test_clear_reports_whether_anything_was_removed(isolated_config):
    assert config.clear_default_team() is False
    config.set_default_team("sea")
    assert config.clear_default_team() is True
    assert config.default_team() is None


def test_env_var_overrides_the_stored_team(isolated_config, monkeypatch):
    config.set_default_team("sea")
    monkeypatch.setenv(config.TEAM_ENV, "nyy")
    assert config.default_team().abbr == "NYY"


def test_env_var_works_with_no_config_file(isolated_config, monkeypatch):
    monkeypatch.setenv(config.TEAM_ENV, "cubs")
    assert config.default_team().abbr == "CHC"


def test_a_corrupt_config_warns_but_does_not_raise(isolated_config, capsys):
    isolated_config.write_text("{not json at all")
    assert config.load() == {}
    assert config.default_team() is None
    assert "unreadable config" in capsys.readouterr().err


def test_a_non_object_config_is_ignored(isolated_config):
    isolated_config.write_text("[1, 2, 3]")
    assert config.load() == {}


def test_an_unknown_stored_team_warns_and_returns_none(isolated_config, capsys):
    config.save({"team": "ZZZ"})
    assert config.default_team() is None
    err = capsys.readouterr().err
    assert "unknown team" in err and "ZZZ" in err


def test_an_unknown_env_team_names_the_env_var(isolated_config, capsys, monkeypatch):
    monkeypatch.setenv(config.TEAM_ENV, "ZZZ")
    assert config.default_team() is None
    assert config.TEAM_ENV in capsys.readouterr().err


def test_warnings_can_be_suppressed(isolated_config, capsys):
    config.save({"team": "ZZZ"})
    assert config.default_team(warn=False) is None
    assert capsys.readouterr().err == ""


def test_save_creates_missing_directories(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "deeper" / "config.json"
    monkeypatch.setenv(config.PATH_ENV, str(nested))
    config.set_default_team("sea")
    assert nested.exists()


def test_save_leaves_no_temp_file_behind(isolated_config):
    config.set_default_team("sea")
    leftovers = [p for p in os.listdir(os.path.dirname(isolated_config))
                 if p.endswith(".tmp")]
    assert leftovers == []


def test_config_path_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.delenv(config.PATH_ENV, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.config_path() == str(tmp_path / "mlb-terminal" / "config.json")


def test_config_path_defaults_under_home(tmp_path, monkeypatch):
    monkeypatch.delenv(config.PATH_ENV, raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config.config_path() == str(tmp_path / ".config" / "mlb-terminal" / "config.json")
