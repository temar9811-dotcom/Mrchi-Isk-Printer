# FILE: main.py
# VERSION: 1.3.0

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.logging_setup import setup_logging
from app.db.database import Database
from app.settings.settings_repository import SettingsRepository
from app.state.app_state import AppState
from app.ui.theme import apply_dark_theme
from app.ui.main_window import MainWindow


def main() -> None:
    logger = setup_logging()
    logger.info("Starting EVE Industry Assistant")

    db_path = Path("data/eve_assistant.db")
    db = Database(db_path)

    try:
        db.connect()
        db.init_schema()
        db.log_debug_event("startup", "Database initialized")
    except Exception:
        logger.exception("Failed to initialize database")
        raise

    settings_repo = SettingsRepository(db)
    app_state = AppState(db, settings_repo)

    app = QApplication(sys.argv)
    apply_dark_theme(app)

    window = MainWindow(app_state)
    window.show()
    app.processEvents()

    # Characters must be loaded before the preload so the primary
    # ESI token is available for structure market pulls.
    app_state.load_characters()

    # Heavy market preload runs after the window is visible so the
    # loading dialog appears immediately instead of a blank wait.
    window.run_startup_load()

    logger.info("Main window displayed")

    exit_code = app.exec()

    db.log_debug_event("shutdown", "Application closed")
    db.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()