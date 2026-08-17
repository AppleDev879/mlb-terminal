"""Client for the public MLB Stats API (statsapi.mlb.com).

Standard library only: urllib with gzip, retries, and friendly errors. The
transport is injectable so tests can drive the client from fixtures.
"""

from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, Optional

__all__ = ["StatsAPI", "ApiError"]

BASE_URL = "https://statsapi.mlb.com"
USER_AGENT = "mlb-terminal/0.1 (+https://github.com/appledev879/mlb-terminal)"

SPORT_MLB = 1
LEAGUE_AL = 103
LEAGUE_NL = 104

SCHEDULE_HYDRATE = "team,linescore,probablePitcher,game(content(summary))"


class ApiError(RuntimeError):
    """Any failure talking to the Stats API, already phrased for a human."""


def _urlopen_transport(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return raw


class StatsAPI:
    """Thin, defensive wrapper over the endpoints this CLI needs."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 12.0,
        retries: int = 2,
        transport: Optional[Callable[[str, float], bytes]] = None,
        cache_ttl: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(0, retries)
        self._transport = transport or _urlopen_transport
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple] = {}
        self.last_url: Optional[str] = None

    # -- plumbing ---------------------------------------------------------

    def build_url(self, path: str, params: Optional[Dict[str, Any]] = None) -> str:
        clean = {}
        for key, value in (params or {}).items():
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple, set)):
                value = ",".join(str(v) for v in value)
            clean[key] = str(value)
        query = urllib.parse.urlencode(clean)
        url = f"{self.base_url}/{path.lstrip('/')}"
        return f"{url}?{query}" if query else url

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> dict:
        url = self.build_url(path, params)
        self.last_url = url
        if self.cache_ttl > 0:
            hit = self._cache.get(url)
            if hit and (time.monotonic() - hit[0]) < self.cache_ttl:
                return hit[1]
        payload = self._fetch(url)
        if self.cache_ttl > 0:
            self._cache[url] = (time.monotonic(), payload)
        return payload

    def _fetch(self, url: str) -> dict:
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                raw = self._transport(url, self.timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    last_error = exc
                    time.sleep(0.6 * (2 ** attempt))
                    continue
                raise ApiError(self._describe_http(exc, url)) from exc
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.6 * (2 ** attempt))
                    continue
                raise ApiError(
                    f"could not reach {urllib.parse.urlsplit(url).netloc}: "
                    f"{self._describe_network(exc)}"
                ) from exc
            try:
                return json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ApiError(f"unreadable response from {url}: {exc}") from exc
        raise ApiError(f"request to {url} failed: {last_error}")

    @staticmethod
    def _describe_http(exc: urllib.error.HTTPError, url: str) -> str:
        if exc.code == 404:
            return f"not found ({url}) — check the game id or date"
        if exc.code in (401, 403):
            return f"access denied by the network or API for {url} (HTTP {exc.code})"
        return f"HTTP {exc.code} from {url}: {exc.reason}"

    @staticmethod
    def _describe_network(exc: Exception) -> str:
        reason = getattr(exc, "reason", exc)
        return str(reason) or exc.__class__.__name__

    # -- endpoints --------------------------------------------------------

    def schedule(
        self,
        date: Optional[dt.date] = None,
        team_id: Optional[int] = None,
        sport_id: int = SPORT_MLB,
        hydrate: str = SCHEDULE_HYDRATE,
    ) -> dict:
        """Games for a single day."""
        params = {
            "sportId": sport_id,
            "hydrate": hydrate,
            "teamId": team_id,
        }
        if date is not None:
            params["date"] = date.strftime("%Y-%m-%d")
        return self.get("/api/v1/schedule", params)

    def schedule_range(
        self,
        start: dt.date,
        end: dt.date,
        team_id: Optional[int] = None,
        sport_id: int = SPORT_MLB,
        hydrate: str = SCHEDULE_HYDRATE,
    ) -> dict:
        return self.get(
            "/api/v1/schedule",
            {
                "sportId": sport_id,
                "startDate": start.strftime("%Y-%m-%d"),
                "endDate": end.strftime("%Y-%m-%d"),
                "teamId": team_id,
                "hydrate": hydrate,
            },
        )

    def game_feed(self, game_pk: int, timecode: Optional[str] = None) -> dict:
        """The full live feed for one game — linescore, plays, and box score."""
        return self.get(f"/api/v1.1/game/{int(game_pk)}/feed/live", {"timecode": timecode})

    def standings(
        self,
        season: Optional[int] = None,
        league_ids: Iterable[int] = (LEAGUE_AL, LEAGUE_NL),
        date: Optional[dt.date] = None,
        standings_type: str = "regularSeason",
    ) -> dict:
        params = {
            "leagueId": list(league_ids),
            "season": season or (date or dt.date.today()).year,
            "standingsTypes": standings_type,
            "hydrate": "team",
        }
        if date is not None:
            params["date"] = date.strftime("%Y-%m-%d")
        return self.get("/api/v1/standings", params)

    def teams(self, season: Optional[int] = None, sport_id: int = SPORT_MLB) -> dict:
        return self.get("/api/v1/teams", {"sportId": sport_id, "season": season})
