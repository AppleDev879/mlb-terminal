# mlb-terminal

Watch MLB games from the terminal. Live scoreboard, pitch-by-pitch, box scores,
and standings — no dependencies beyond the Python standard library.

```
  Seattle Mariners (68-54)    4
  New York Yankees (70-52)    3     ● Bot 7th · 2 outs
  Yankee Stadium · Partly Cloudy 78°

        1  2  3  4  5  6  7  8  9  │  R  H  E
  SEA    0  1  0  2  0  1  0        │  4  9  0
▸ NYY    1  0  0  0  2  0  0        │  3  7  1

  COUNT         BASES    MATCHUP
  2-2             ◇      P Andrés Muñoz
  ●●○ 2 outs    ◆   ◆    B Aaron Judge
                  ⌂        on deck: Cody Bellinger
  PITCHES  FF 99 · SL 88 · FF 100 · SL 88

  RECENT
  B7  Cody Bellinger flies out to center fielder Julio Rodríguez.
  T7  Julio Rodríguez grounds out, second baseman Jazz Chisholm Jr. to first
      baseman Ben Rice.
  B6  Giancarlo Stanton strikes out swinging.
  T6  Cal Raleigh homers (23) on a fly ball to right field.  (4-3)
```

## Install

Requires Python 3.9+. Nothing else.

```sh
git clone https://github.com/appledev879/mlb-terminal
cd mlb-terminal
python3 -m mlb games            # run it straight from the checkout
```

Or install it so `mlb` is on your `PATH`:

```sh
pip install -e .
mlb games
```

## Commands

### `mlb games` — the day's slate

```sh
mlb games                       # today
mlb games --date 2025-07-04     # a specific day (also: yesterday, -2, 7/4)
mlb games --team sea            # just one team
mlb games --watch               # keep the list refreshing
```

Each row starts with the game id you pass to the other commands.

### `mlb watch` — follow a game live

```sh
mlb watch 776543                # by game id
mlb watch --team nyy            # today's Yankees game
mlb watch sea                   # shorthand for --team sea
mlb watch 776543 --once         # print one frame and exit
mlb watch 776543 --interval 5   # refresh every 5 seconds (default 10)
mlb watch 776543 --plays 10     # show more of the play-by-play
```

The view shows the score, linescore, count, outs, baserunners, the current
matchup, the pitch sequence of the at-bat in progress, and recent plays.
It stops on its own when the game goes final — pass `--keep` to stay.

### `mlb box` — box score

```sh
mlb box 776543                  # batting and pitching lines for both teams
mlb box --team chc              # today's Cubs game
mlb box 776543 --watch          # refresh as the game goes
```

### `mlb standings`

```sh
mlb standings                   # all six divisions
mlb standings --league al       # one league
mlb standings --team nyy        # highlight a team
mlb standings --wide            # add run differential, home/away, last 10
mlb standings --season 2024     # a past season
```

## Team names

Anywhere a team is accepted, most spellings work: `sea`, `SEA`, `mariners`,
`Seattle Mariners`, `136`. Nicknames too — `yanks`, `cards`, `nats`, `dbacks`,
`a's`.

## Display flags

Every command accepts:

| Flag | Effect |
| --- | --- |
| `--no-color` | plain text, no ANSI color |
| `--ascii` | ASCII-only glyphs (no `●`, `◆`, box drawing) |
| `--width N` | render to a fixed width instead of the terminal's |
| `--timeout N` | HTTP timeout in seconds (default 12) |

Color and unicode are autodetected: piping to a file or another program turns
both off, and `NO_COLOR` is honored. That means `mlb games > slate.txt` and
`mlb watch 776543 --once | mail ...` produce clean text with no escape codes.

## Data

Game data comes from the public MLB Stats API at `statsapi.mlb.com`:

- `/api/v1/schedule` for the day's games
- `/api/v1.1/game/{id}/feed/live` for the live feed, plays, and box score
- `/api/v1/standings` for standings

No API key needed. This project is unofficial and not affiliated with or
endorsed by MLB; the data is subject to MLB's terms of use.

## Development

```sh
pip install -e ".[dev]"
pytest
```

The test suite runs entirely against recorded fixtures in `tests/fixtures/`,
so it needs no network access.

Layout:

| Path | What it holds |
| --- | --- |
| `mlb/api.py` | Stats API client — urllib, retries, injectable transport |
| `mlb/models.py` | Dataclasses parsed defensively from API payloads |
| `mlb/views/` | Renderers, one per view; each returns a list of lines |
| `mlb/ansi.py` | Color, unicode fallbacks, width-aware padding/truncation |
| `mlb/live.py` | The refresh loop and alternate-screen handling |
| `mlb/cli.py` | Argument parsing and command wiring |

Every payload field is read through `util.dig`, so a partial or unfamiliar
response degrades to blank cells rather than a traceback.
