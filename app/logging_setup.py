# FILE: app/logging_setup.py
# VERSION: 1.1.0

import logging
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "app_debug.log"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """
    Configure root logging for the app.

    - Writes everything to logs/app_debug.log
    - File is deleted and recreated on every startup
    - Mirrors to the console
    - urllib3 is dampened to INFO so app debug lines stay readable
      (set it to logging.DEBUG here if you ever want raw HTTP noise back)
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Recreate the log file on every startup
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Dampen third-party noise; keep app modules at full debug
    logging.getLogger("urllib3").setLevel(logging.INFO)

    logger = logging.getLogger("app")
    logger.info("Logging initialized. Log file: %s", LOG_FILE)
    return logger