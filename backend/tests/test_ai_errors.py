import pytest

from app.api.ai_errors import _about


@pytest.mark.parametrize(
    "seconds, text",
    [
        (1, "about a minute"),
        (89, "about a minute"),
        (90, "about 2 minutes"),
        (1200, "about 20 minutes"),
        (3569, "about 59 minutes"),
        (3599, "about 1 hour"),
        (3600, "about 1 hour"),
        (56638, "about 16 hours"),
    ],
)
def test_waits_are_said_in_plain_words(seconds, text):
    assert _about(seconds) == text
