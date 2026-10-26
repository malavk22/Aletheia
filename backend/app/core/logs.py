"""Where the app's log lines go. Under uvicorn only uvicorn's own loggers
print; ours had nowhere to go, so only warnings and errors showed (through
Python's last-resort output) and every info line was lost."""

import logging

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(level: str) -> None:
    """Prints every `app.*` logger's lines at `level` and above (DEBUG, INFO,
    WARNING, ERROR) to the console, one line each."""
    logger = logging.getLogger("app")
    # Once, even when called again (a reload, a test): two handlers would
    # print every line twice.
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level.upper())
