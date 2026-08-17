import io

from mlb import live


class Sink(io.StringIO):
    def isatty(self):
        return False


def test_once_renders_a_single_frame_without_a_footer():
    stream = Sink()
    calls = []

    def fetch():
        calls.append(1)
        return {"score": 3}

    code = live.run(fetch, lambda p: [f"score {p['score']}"], once=True, stream=stream,
                    interactive=False)
    assert code == 0
    assert len(calls) == 1
    assert stream.getvalue().strip() == "score 3"


def test_loop_refreshes_until_max_iterations():
    stream = Sink()
    seen = []

    def fetch():
        seen.append(len(seen))
        return len(seen)

    live.run(fetch, lambda n: [f"frame {n}"], interval=0, stream=stream,
             interactive=False, max_iterations=3, sleeper=lambda _: True)
    assert seen == [0, 1, 2]
    assert "frame 3" in stream.getvalue()


def test_loop_stops_when_the_game_ends():
    stream = Sink()
    state = {"n": 0}

    def fetch():
        state["n"] += 1
        return {"final": state["n"] >= 2}

    live.run(fetch, lambda p: ["x"], interval=0, stream=stream, interactive=False,
             stop_when=lambda p: p["final"], sleeper=lambda _: True,
             max_iterations=10)
    assert state["n"] == 2
    assert "game over" in stream.getvalue()


def test_a_transient_failure_mid_session_keeps_the_loop_alive():
    stream = Sink()
    state = {"n": 0}

    def fetch():
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("connection reset")
        return state["n"]

    live.run(fetch, lambda n: [f"frame {n}"], interval=0, stream=stream,
             interactive=False, max_iterations=3, sleeper=lambda _: True)
    output = stream.getvalue()
    assert "connection reset" in output
    assert "frame 3" in output


def test_a_failure_on_the_very_first_fetch_exits_nonzero(capsys):
    stream = Sink()

    def fetch():
        raise RuntimeError("dns is down")

    code = live.run(fetch, lambda p: ["x"], stream=stream, interactive=False,
                    sleeper=lambda _: True)
    assert code == 1
    assert "dns is down" in capsys.readouterr().err


def test_interrupting_the_sleep_ends_the_loop():
    stream = Sink()
    state = {"n": 0}

    def fetch():
        state["n"] += 1
        return state["n"]

    live.run(fetch, lambda n: ["x"], interval=0, stream=stream, interactive=False,
             sleeper=lambda _: False, max_iterations=99)
    assert state["n"] == 1


def test_interactive_screen_uses_the_alternate_buffer():
    class TTY(io.StringIO):
        def isatty(self):
            return True

    stream = TTY()
    with live.Screen(stream=stream) as screen:
        screen.draw(["hello"])
    output = stream.getvalue()
    assert live.ALT_SCREEN_ON in output
    assert live.ALT_SCREEN_OFF in output
    assert live.HIDE_CURSOR in output and live.SHOW_CURSOR in output
    assert "hello" in output


def test_non_tty_screen_stays_plain():
    stream = Sink()
    with live.Screen(stream=stream) as screen:
        screen.draw(["hello"])
    assert stream.getvalue() == "hello\n"


def test_draw_strips_trailing_whitespace():
    stream = Sink()
    live.Screen(stream=stream, interactive=False).draw(["padded   ", "ok"])
    assert stream.getvalue() == "padded\nok\n"
