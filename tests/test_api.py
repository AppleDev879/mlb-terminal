import datetime as dt
import json
import urllib.error

import pytest

from mlb.api import ApiError, StatsAPI


class Recorder:
    """Fake transport that records URLs and replays canned responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        response = self.responses.pop(0) if self.responses else {"ok": True}
        if isinstance(response, Exception):
            raise response
        if isinstance(response, bytes):
            return response
        return json.dumps(response).encode("utf-8")


def test_build_url_encodes_and_drops_empty_params():
    client = StatsAPI()
    url = client.build_url("/api/v1/schedule", {"sportId": 1, "teamId": None, "date": ""})
    assert url == "https://statsapi.mlb.com/api/v1/schedule?sportId=1"


def test_build_url_joins_list_params():
    client = StatsAPI()
    url = client.build_url("/api/v1/standings", {"leagueId": [103, 104]})
    assert "leagueId=103%2C104" in url


def test_schedule_request_shape():
    transport = Recorder({"dates": []})
    client = StatsAPI(transport=transport)
    client.schedule(date=dt.date(2025, 8, 16), team_id=136)
    url = transport.urls[0]
    assert "/api/v1/schedule?" in url
    assert "date=2025-08-16" in url
    assert "teamId=136" in url
    assert "sportId=1" in url


def test_game_feed_request_shape():
    transport = Recorder({"gamePk": 776543})
    client = StatsAPI(transport=transport)
    payload = client.game_feed(776543)
    assert payload["gamePk"] == 776543
    assert transport.urls[0].endswith("/api/v1.1/game/776543/feed/live")


def test_standings_defaults_to_both_leagues():
    transport = Recorder({"records": []})
    client = StatsAPI(transport=transport)
    client.standings(season=2025)
    url = transport.urls[0]
    assert "leagueId=103%2C104" in url
    assert "season=2025" in url


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    transport = Recorder(urllib.error.URLError("temporary glitch"), {"ok": 1})
    client = StatsAPI(transport=transport, retries=2)
    assert client.get("/api/v1/teams") == {"ok": 1}
    assert len(transport.urls) == 2


def test_network_failure_becomes_a_readable_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    transport = Recorder(*[urllib.error.URLError("no route to host")] * 3)
    client = StatsAPI(transport=transport, retries=2)
    with pytest.raises(ApiError) as exc:
        client.get("/api/v1/teams")
    assert "statsapi.mlb.com" in str(exc.value)
    assert "no route to host" in str(exc.value)


def test_404_is_not_retried_and_explains_itself():
    error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
    transport = Recorder(error, {"ok": 1})
    client = StatsAPI(transport=transport, retries=2)
    with pytest.raises(ApiError) as exc:
        client.game_feed(1)
    assert "not found" in str(exc.value)
    assert len(transport.urls) == 1


def test_server_error_is_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    error = urllib.error.HTTPError("url", 503, "Service Unavailable", {}, None)
    transport = Recorder(error, {"ok": 1})
    client = StatsAPI(transport=transport, retries=1)
    assert client.get("/api/v1/teams") == {"ok": 1}


def test_bad_json_is_reported_clearly():
    transport = Recorder(b"<html>maintenance</html>")
    client = StatsAPI(transport=transport)
    with pytest.raises(ApiError) as exc:
        client.get("/api/v1/teams")
    assert "unreadable response" in str(exc.value)


def test_cache_avoids_a_second_request():
    transport = Recorder({"n": 1}, {"n": 2})
    client = StatsAPI(transport=transport, cache_ttl=60)
    assert client.get("/api/v1/teams") == {"n": 1}
    assert client.get("/api/v1/teams") == {"n": 1}
    assert len(transport.urls) == 1


def test_cache_off_by_default():
    transport = Recorder({"n": 1}, {"n": 2})
    client = StatsAPI(transport=transport)
    assert client.get("/api/v1/teams") == {"n": 1}
    assert client.get("/api/v1/teams") == {"n": 2}
