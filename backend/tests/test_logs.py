import io
import logging

from app.core.logs import setup_logging


def test_app_info_lines_are_printed(monkeypatch):
    setup_logging("INFO")
    printed = io.StringIO()
    handler = logging.getLogger("app").handlers[0]
    monkeypatch.setattr(handler, "stream", printed)

    logging.getLogger("app.probe").info("models loaded")

    assert "INFO app.probe: models loaded" in printed.getvalue()


def test_lines_below_the_level_are_not_printed(monkeypatch):
    printed = io.StringIO()
    setup_logging("WARNING")
    monkeypatch.setattr(logging.getLogger("app").handlers[0], "stream", printed)
    try:
        logging.getLogger("app.probe").info("too detailed")
    finally:
        setup_logging("INFO")

    assert printed.getvalue() == ""


def test_setting_up_twice_prints_each_line_once():
    setup_logging("INFO")
    setup_logging("INFO")

    assert len(logging.getLogger("app").handlers) == 1
