# FILE: app/ui/debug_menu.py
# VERSION: 1.0.0

import logging

from PySide6.QtWidgets import QMenu, QMessageBox


def build_debug_menu(main_window, app_state) -> QMenu:
    """
    Build the Debug menu.

    This gives quick access to test actions while we build the app.
    """
    logger = logging.getLogger("app.ui.debug_menu")

    menu = QMenu("Debug", main_window.menuBar())

    menu.addAction(
        "Add test character",
        app_state.add_test_character,
    )

    menu.addAction(
        "Refresh characters",
        app_state.load_characters,
    )

    menu.addAction(
        "Reload settings",
        app_state.reload_settings,
    )

    menu.addAction(
        "Save settings",
        app_state.save_settings,
    )

    menu.addSeparator()

    menu.addAction(
        "Emit info log",
        lambda: logger.info("Test info log emitted"),
    )

    menu.addAction(
        "Emit warning log",
        lambda: logger.warning("Test warning log emitted"),
    )

    menu.addAction(
        "Emit error log",
        lambda: logger.error("Test error log emitted"),
    )

    menu.addAction(
        "Raise test exception",
        lambda: _raise_test_exception(main_window),
    )

    menu.addAction(
        "Show debug log",
        lambda: _show_debug_log(main_window),
    )

    logger.debug("Debug menu built")
    return menu


def _raise_test_exception(main_window) -> None:
    """
    Deliberately raise and catch an exception for debug testing.
    """
    logger = logging.getLogger("app.ui.debug_menu")

    try:
        raise RuntimeError("Deliberate test exception for debugging")
    except Exception:
        logger.exception("Test exception caught")
        QMessageBox.critical(
            main_window,
            "Debug",
            "Test exception raised and logged.",
        )


def _show_debug_log(main_window) -> None:
    """
    Show and raise the debug log dock.
    """
    logger = logging.getLogger("app.ui.debug_menu")

    if hasattr(main_window, "log_dock"):
        main_window.log_dock.show()
        main_window.log_dock.raise_()
    else:
        logger.warning("Show debug log clicked, but log_dock is missing")