# FILE: app/esi/login_worker.py
# VERSION: 1.2.0

import logging
import threading

from PySide6.QtCore import QThread, Signal

from app.esi.auth_flow import perform_login_flow

logger = logging.getLogger("app.esi.login_worker")


class LoginWorker(QThread):
    """
    Runs the blocking ESI login flow in a background thread.
    Supports cancellation via a threading.Event.
    """

    success = Signal(dict)
    error = Signal(str)
    auth_url_ready = Signal(str)

    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()

    def cancel(self) -> None:
        """
        Request cancellation of the running login flow.
        """
        logger.info("Login cancel requested")
        self.stop_event.set()

    def _emit_url(self, url: str) -> None:
        """
        Called from the worker thread by perform_login_flow.
        Qt queues the signal delivery to the main thread.
        """
        self.auth_url_ready.emit(url)

    def run(self):
        try:
            logger.debug("LoginWorker thread started")
            result = perform_login_flow(
                self.stop_event,
                on_url=self._emit_url,
            )
            self.success.emit(result)
        except Exception as exc:
            logger.exception("LoginWorker failed")
            self.error.emit(str(exc))