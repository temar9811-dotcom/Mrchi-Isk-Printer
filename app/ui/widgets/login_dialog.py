# FILE: app/ui/widgets/login_dialog.py
# VERSION: 1.1.0

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
)


class LoginDialog(QDialog):
    """
    Popup shown while the EVE SSO login flow is running.

    Shows instructions, the login link, and a Cancel button so a stuck
    or failed login never requires an app restart.
    """

    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("app.ui.login_dialog")
        self._finished = False

        self.setWindowTitle("Add Character - EVE SSO")
        self.setModal(False)
        self.setMinimumWidth(520)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Logging in to EVE Online...", self)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #7ec8ff;")
        layout.addWidget(title)

        instructions = QTextEdit(self)
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(170)
        instructions.setHtml(
            """
            <ol>
            <li>Your web browser has opened the EVE login page.</li>
            <li>Log in at the EVE website and choose the character to add.</li>
            <li>Click <b>Authorize</b> to grant the app access.</li>
            <li>The browser will show "Login successful!" and the app
                will finish automatically.</li>
            </ol>
            If the browser did not open, copy the login link below and
            open it manually.
            """
        )
        layout.addWidget(instructions)

        url_layout = QHBoxLayout()

        self.url_edit = QLineEdit(self)
        self.url_edit.setReadOnly(True)
        self.url_edit.setPlaceholderText("Login link will appear here...")
        url_layout.addWidget(self.url_edit, 1)

        self.btn_copy = QPushButton("Copy Link", self)
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_link)
        url_layout.addWidget(self.btn_copy)

        layout.addLayout(url_layout)

        self.status_label = QLabel("Waiting for you to log in...", self)
        self.status_label.setStyleSheet("color: #8f9baa;")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel Login", self)
        self.btn_cancel.setStyleSheet(
            "background-color: #5c2a2a; border-color: #8a3333;"
        )
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def set_auth_url(self, url: str) -> None:
        """
        Display the generated login URL in the dialog.
        """
        self.url_edit.setText(url)
        self.btn_copy.setEnabled(True)
        self.logger.debug("Auth URL displayed in login dialog")

    def _copy_link(self) -> None:
        QApplication.clipboard().setText(self.url_edit.text())
        self.status_label.setText("Link copied to clipboard.")
        self.logger.info("Login link copied to clipboard")

    def mark_finished(self) -> None:
        """
        Called by the main window before closing this dialog after a
        successful or failed login, so closeEvent does not trigger a
        cancel.
        """
        self._finished = True

    def _on_cancel(self) -> None:
        self.logger.info("User clicked Cancel Login")
        self.status_label.setText("Cancelling...")
        self.btn_cancel.setEnabled(False)
        self.cancel_requested.emit()

    def closeEvent(self, event) -> None:
        # Closing with the X button counts as a cancel, unless the
        # main window already finished the flow.
        if not self._finished and self.btn_cancel.isEnabled():
            self.cancel_requested.emit()
        super().closeEvent(event)