# FILE: app/ui/widgets/log_panel.py
# VERSION: 1.0.0

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class _QtLogSignal(QObject):
    """
    QObject used to carry log messages into the Qt event loop.
    """

    log_message = Signal(str)


class QtLogHandler(logging.Handler):
    """
    Logging handler that emits log records to a Qt signal.

    This lets Python logging write into the in-app debug log panel.
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.signals = _QtLogSignal()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.signals.log_message.emit(message)
        except Exception:
            self.handleError(record)


class LogPanel(QPlainTextEdit):
    """
    Read-only text panel that displays application logs.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        self.setPlaceholderText("Debug logs will appear here...")

        self._handler = None

    def attach_logger(self, logger: logging.Logger) -> None:
        """
        Attach this panel to a logger.

        Usually called with logging.getLogger() so it receives all logs.
        """
        self._handler = QtLogHandler()

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self._handler.setFormatter(formatter)
        self._handler.signals.log_message.connect(self.append_log)

        logger.addHandler(self._handler)

    def append_log(self, message: str) -> None:
        """
        Append a formatted log line and scroll to the bottom.
        """
        self.appendPlainText(message)
        self.moveCursor(QTextCursor.End)