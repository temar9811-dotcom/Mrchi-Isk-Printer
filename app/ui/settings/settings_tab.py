# FILE: app/ui/settings/settings_tab.py
# VERSION: 1.1.0

import json
import logging

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QStackedWidget,
    QPushButton,
    QLabel,
)

from app.state.app_state import AppState
from app.ui.settings.general_page import GeneralSettingsPage
from app.ui.settings.pi_page import PiSettingsPage
from app.ui.settings.trade_page import TradeSettingsPage
from app.ui.settings.hauling_page import HaulingSettingsPage


class SettingsTab(QWidget):
    """
    Settings screen.

    Left side:
        Settings categories.

    Right side:
        Settings pages.
    """

    def __init__(self, app_state: AppState):
        super().__init__()

        self.logger = logging.getLogger("app.ui.settings_tab")
        self.app_state = app_state
        self.pages = []

        self._build_ui()
        self.load_from_settings()

        self.app_state.settings_changed.connect(self.load_from_settings)

        self.logger.debug("SettingsTab initialized")

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.category_list = QListWidget(self)
        self.category_list.setMaximumWidth(220)
        self.category_list.addItems(
            ["General", "PI", "Market Trade", "Hauling"]
        )

        self.page_stack = QStackedWidget(self)

        self.general_page = GeneralSettingsPage(self.app_state)
        self.pi_page = PiSettingsPage(self.app_state)
        self.trade_page = TradeSettingsPage(self.app_state)
        self.hauling_page = HaulingSettingsPage(self.app_state)

        self.pages = [
            self.general_page,
            self.pi_page,
            self.trade_page,
            self.hauling_page,
        ]

        for page in self.pages:
            self.page_stack.addWidget(page)

        self.category_list.currentRowChanged.connect(
            self.page_stack.setCurrentIndex
        )

        self.category_list.setCurrentRow(0)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.page_stack, 1)

        button_layout = QHBoxLayout()

        save_button = QPushButton("Save Settings", self)
        reload_button = QPushButton("Reload Settings", self)
        print_button = QPushButton("Print Settings to Log", self)

        save_button.clicked.connect(self.save_settings)
        reload_button.clicked.connect(self.reload_settings)
        print_button.clicked.connect(self.print_settings)

        button_layout.addWidget(save_button)
        button_layout.addWidget(reload_button)
        button_layout.addWidget(print_button)
        button_layout.addStretch()

        self.status_label = QLabel("Ready", self)
        self.status_label.setStyleSheet("color: #8f9baa;")

        right_layout.addLayout(button_layout)
        right_layout.addWidget(self.status_label)

        layout.addWidget(self.category_list, 1)
        layout.addLayout(right_layout, 4)

    def load_from_settings(self) -> None:
        for page in self.pages:
            page.load_settings()
        self.logger.debug("All settings pages loaded from AppState.settings")

    def save_settings(self) -> None:
        for page in self.pages:
            page.apply_to_settings()
        self.app_state.save_settings()
        self.status_label.setText("Settings saved.")
        self.logger.info("Settings saved from SettingsTab")

    def reload_settings(self) -> None:
        self.app_state.reload_settings()
        self.status_label.setText("Settings reloaded.")
        self.logger.info("Settings reloaded from SettingsTab")

    def print_settings(self) -> None:
        settings_json = json.dumps(
            self.app_state.settings.to_dict(),
            indent=2,
            sort_keys=True,
        )
        self.logger.info("Current settings:\n%s", settings_json)
        self.status_label.setText("Settings printed to log.")

    def stop_workers(self) -> None:
        """
        Stop any background workers owned by settings pages.
        """
        for page in self.pages:
            if hasattr(page, "stop_workers"):
                page.stop_workers()