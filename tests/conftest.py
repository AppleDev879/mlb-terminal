import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mlb import ansi  # noqa: E402


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(autouse=True)
def plain_output():
    """Render without color or unicode so assertions can match plain text."""
    ansi.configure(color=False, unicode_=False)
    yield
    ansi.configure(color=False, unicode_=False)


@pytest.fixture
def styled_output():
    ansi.configure(color=True, unicode_=True)
    yield
    ansi.configure(color=False, unicode_=False)


@pytest.fixture
def schedule_payload():
    return load("schedule.json")


@pytest.fixture
def live_payload():
    return load("feed_live.json")


@pytest.fixture
def final_payload():
    return load("feed_final.json")


@pytest.fixture
def preview_payload():
    return load("feed_preview.json")


@pytest.fixture
def standings_payload():
    return load("standings.json")
