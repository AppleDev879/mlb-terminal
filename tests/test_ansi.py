from mlb import ansi


def test_paint_is_a_noop_without_color():
    ansi.configure(color=False, unicode_=False)
    assert ansi.paint("Judge", "bold") == "Judge"


def test_paint_wraps_and_resets_with_color(styled_output):
    text = ansi.paint("Judge", "bold", "bright_green")
    assert text.startswith("\x1b[1;92m")
    assert text.endswith(ansi.RESET)
    assert ansi.strip_ansi(text) == "Judge"


def test_vlen_ignores_escape_codes(styled_output):
    assert ansi.vlen(ansi.paint("Judge", "bold")) == 5


def test_pad_measures_visible_width(styled_output):
    padded = ansi.pad(ansi.paint("SEA", "bold"), 6)
    assert ansi.vlen(padded) == 6
    assert ansi.strip_ansi(padded) == "SEA   "


def test_pad_alignment():
    assert ansi.pad("4", 3, "right") == "  4"
    assert ansi.pad("x", 5, "center") == "  x  "
    assert ansi.pad("too long", 3) == "too long"


def test_trunc_respects_visible_width(styled_output):
    text = ansi.paint("Giancarlo Stanton", "bold")
    cut = ansi.trunc(text, 10)
    assert ansi.vlen(cut) <= 10
    assert cut.endswith(ansi.RESET)


def test_trunc_ascii_ellipsis_without_unicode():
    ansi.configure(color=False, unicode_=False)
    assert ansi.trunc("Giancarlo Stanton", 8) == "Gianc..."


def test_trunc_leaves_short_text_alone():
    assert ansi.trunc("SEA", 10) == "SEA"


def test_glyph_falls_back_to_ascii():
    ansi.configure(color=False, unicode_=False)
    assert ansi.glyph("●", "*") == "*"
    ansi.configure(color=False, unicode_=True)
    assert ansi.glyph("●", "*") == "●"


def test_no_color_env_disables_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")

    class FakeTTY:
        encoding = "utf-8"

        def isatty(self):
            return True

    ansi.configure(stream=FakeTTY())
    assert ansi.color_enabled() is False


def test_non_tty_stream_disables_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)

    class FakePipe:
        encoding = "utf-8"

        def isatty(self):
            return False

    ansi.configure(stream=FakePipe())
    assert ansi.color_enabled() is False
    assert ansi.unicode_enabled() is True


def test_latin1_stream_disables_unicode():
    class FakeStream:
        encoding = "latin-1"

        def isatty(self):
            return True

    ansi.configure(stream=FakeStream())
    assert ansi.unicode_enabled() is False
