# FILE: app/ui/widgets/character_info_panel.py
# VERSION: 1.2.0

import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
)

from app.state.app_state import AppState
from app.ui.widgets.info_worker import CharacterInfoWorker


class CharacterInfoPanel(QGroupBox):
    """
    Displays live ESI data for the selected character with resolved names.
    """

    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Character Info", parent)
        self.app_state = app_state
        self.logger = logging.getLogger("app.ui.widgets.character_info_panel")
        self._active_workers = set()
        self._requested_char_id = None

        self._build_ui()
        self.app_state.selected_character_changed.connect(self._on_character_changed)
        self._on_character_changed(self.app_state.selected_character)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        self.form = QFormLayout()
        self.form.setSpacing(6)

        self.lbl_name = QLabel("-")
        self.lbl_online = QLabel("-")
        self.lbl_location = QLabel("-")
        self.lbl_ship = QLabel("-")

        self.form.addRow("Name:", self.lbl_name)
        self.form.addRow("Online:", self.lbl_online)
        self.form.addRow("Location:", self.lbl_location)
        self.form.addRow("Ship:", self.lbl_ship)

        layout.addLayout(self.form)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh Status")
        self.btn_refresh.clicked.connect(self.fetch_info)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_character_changed(self, character) -> None:
        if character is None:
            self._requested_char_id = None
            self.setTitle("Character Info (No selection)")
            self.lbl_name.setText("-")
            self.lbl_online.setText("-")
            self.lbl_online.setStyleSheet("color: #d7dde6;")
            self.lbl_location.setText("-")
            self.lbl_ship.setText("-")
            return

        self._requested_char_id = character.character_id
        self.setTitle(f"Character Info - {character.character_name}")
        self.lbl_name.setText(character.character_name)
        self.lbl_online.setText("Fetching...")
        self.lbl_online.setStyleSheet("color: #d7dde6;")
        self.lbl_location.setText("Fetching...")
        self.lbl_ship.setText("Fetching...")
        self.fetch_info()

    def fetch_info(self) -> None:
        char = self.app_state.selected_character
        if not char:
            return

        client = self.app_state.get_esi_client(char)
        resolver = self.app_state.get_universe_resolver()
        if not client:
            return

        self._requested_char_id = char.character_id
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Fetching...")

        worker = CharacterInfoWorker(client, resolver)
        worker.info_fetched.connect(
            lambda data, w=worker: self._on_info_fetched(w, data)
        )
        worker.error.connect(lambda msg, w=worker: self._on_error(w, msg))
        worker.finished.connect(lambda w=worker: self._on_worker_done(w))

        self._active_workers.add(worker)
        worker.start()

    def _on_worker_done(self, worker) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()

        if not self._active_workers:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Refresh Status")

    def _on_info_fetched(self, worker, data: dict) -> None:
        char = worker.client.character

        if char.character_id != self._requested_char_id:
            self.logger.debug(
                "Ignoring stale info result for %s", char.character_name
            )
            return

        online_data = data.get("online", {})
        is_online = online_data.get("online", False)

        if is_online:
            self.lbl_online.setText("Yes")
            self.lbl_online.setStyleSheet("color: #2ecc71; font-weight: bold;")
        else:
            self.lbl_online.setText("No")
            self.lbl_online.setStyleSheet("color: #e74c3c; font-weight: bold;")

        system_name = data.get("system_name", "")
        station_name = data.get("station_name", "")

        if station_name:
            self.lbl_location.setText(f"{station_name}")
            self.lbl_location.setToolTip(f"System: {system_name}")
        elif system_name:
            self.lbl_location.setText(f"{system_name}")
            self.lbl_location.setToolTip("")
        else:
            self.lbl_location.setText("Unknown")

        ship_name = data.get("ship_name", "")
        ship_type_id = data.get("ship", {}).get("ship_type_id", "")

        if ship_name:
            self.lbl_ship.setText(ship_name)
        elif ship_type_id:
            self.lbl_ship.setText(f"Type {ship_type_id}")
        else:
            self.lbl_ship.setText("Unknown")

    def _on_error(self, worker, msg: str) -> None:
        char = worker.client.character

        if char.character_id != self._requested_char_id:
            return

        self.lbl_online.setText("Error")
        self.lbl_online.setStyleSheet("color: #e74c3c;")
        self.lbl_location.setText("Error")
        self.lbl_location.setToolTip(msg)
        self.lbl_ship.setText("-")
        self.logger.error("Failed to fetch info: %s", msg)

    def stop_workers(self) -> None:
        """
        Wait for any running workers. Called on app shutdown.
        """
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(3000)
        self._active_workers.clear()