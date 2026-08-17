"""Auto-refresh loop and screen handling for the watch commands."""

from __future__ import annotations

import datetime as dt
import signal
import sys
import time
from typing import Callable, List, Optional

from . import ansi

ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
HOME_CLEAR = "\x1b[H\x1b[J"


class Screen:
    """Manages the alternate screen buffer and cursor for a live view.

    Falls back to plain sequential printing when stdout is not a terminal, so
    piping the output to a file or ``less`` still works.
    """

    def __init__(self, stream=None, interactive: Optional[bool] = None):
        self.stream = stream or sys.stdout
        if interactive is None:
            try:
                interactive = bool(self.stream.isatty())
            except Exception:
                interactive = False
        self.interactive = interactive
        self._entered = False

    def __enter__(self) -> "Screen":
        if self.interactive:
            self.stream.write(ALT_SCREEN_ON + HIDE_CURSOR)
            self.stream.flush()
            self._entered = True
        return self

    def __exit__(self, *exc_info) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if self._entered:
            self.stream.write(SHOW_CURSOR + ALT_SCREEN_OFF)
            self.stream.flush()
            self._entered = False

    def draw(self, lines: List[str]) -> None:
        body = "\n".join(line.rstrip() for line in lines)
        if self.interactive:
            self.stream.write(HOME_CLEAR + body + "\n")
        else:
            self.stream.write(body + "\n")
        self.stream.flush()


def footer(interval: float, note: str = "", error: str = "") -> str:
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    bits = [f"updated {stamp}", f"every {interval:g}s"]
    if note:
        bits.append(note)
    text = ansi.paint("  " + ansi.glyph("·", "-").join(f" {b} " for b in bits), "dim")
    if error:
        text += "  " + ansi.paint(error, "bright_red")
    return text


def sleep_interruptible(seconds: float) -> bool:
    """Sleep, returning False if interrupted by Ctrl-C."""
    try:
        time.sleep(max(0.0, seconds))
        return True
    except KeyboardInterrupt:
        return False


def run(
    fetch: Callable[[], object],
    render: Callable[[object], List[str]],
    interval: float = 10.0,
    once: bool = False,
    stop_when: Optional[Callable[[object], bool]] = None,
    stream=None,
    interactive: Optional[bool] = None,
    max_iterations: Optional[int] = None,
    sleeper: Callable[[float], bool] = sleep_interruptible,
) -> int:
    """Fetch/render on a loop until interrupted, stopped, or ``once``.

    Transient fetch failures are shown in the footer and retried rather than
    killing a session that has been running all game.
    """
    screen = Screen(stream=stream, interactive=interactive)
    exit_code = 0
    iterations = 0
    error = ""
    handler = _install_sigint()
    try:
        with screen:
            while True:
                iterations += 1
                payload = None
                try:
                    payload = fetch()
                    error = ""
                except KeyboardInterrupt:
                    break
                except Exception as exc:  # keep the loop alive across blips
                    error = f"refresh failed: {exc}"
                    if once or iterations == 1:
                        screen.close()
                        print(f"error: {exc}", file=sys.stderr)
                        return 1

                lines = list(render(payload)) if payload is not None else []
                note = ""
                if payload is not None and stop_when and stop_when(payload):
                    note = "game over"
                if not once:
                    lines.append("")
                    lines.append(footer(interval, note=note, error=error))
                    if screen.interactive:
                        lines.append(ansi.paint("  ctrl-c to quit", "dim"))
                screen.draw(lines)

                if once:
                    break
                if payload is not None and stop_when and stop_when(payload):
                    break
                if max_iterations is not None and iterations >= max_iterations:
                    break
                if not sleeper(interval):
                    break
    except KeyboardInterrupt:
        exit_code = 0
    finally:
        screen.close()
        _restore_sigint(handler)
    return exit_code


def _install_sigint():
    try:
        return signal.getsignal(signal.SIGINT)
    except Exception:
        return None


def _restore_sigint(handler) -> None:
    if handler is not None:
        try:
            signal.signal(signal.SIGINT, handler)
        except Exception:
            pass
