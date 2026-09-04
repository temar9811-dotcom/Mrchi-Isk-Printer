# FILE: app/ui/settings/pi_page.py
# VERSION: 1.1.0

import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QMessageBox,
)

from app.state.app_state import AppState
from app.ui.settings.fields import (
    create_id_line_edit,
    create_id_row,
    get_optional_id,
    set_optional_id,
)
from app.ui.widgets.location_worker import LocationFetchWorker


class PiSettingsPage(QWidget):
    """
    PI settings page.
    """

    def __init__(self, app_state: AppState):
        super().__init__()

        self.logger = logging.getLogger("app.ui.settings.pi_page")
        self.app_state = app_state
        self._workers = set()

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self.cycle_days = QSpinBox(self)
        self.cycle_days.setMinimum(1)
        self.cycle_days.setMaximum(365)
        self.cycle_days.setSuffix(" days")

        self.search_range = QSpinBox(self)
        self.search_range.setMinimum(0)
        self.search_range.setMaximum(20)
        self.search_range.setSuffix(" jumps")

        self.price_mode = QComboBox(self)
        self.price_mode.addItems(["sell", "buy"])

        self.include_raw_extractor_pi = QCheckBox(
            "Include raw extractor PI",
            self,
        )

        self.home_station_id = create_id_line_edit(self)
        self.market_station_id = create_id_line_edit(self)

        form.addRow("PI cycle length", self.cycle_days)
        form.addRow("Home station search range", self.search_range)
        form.addRow("Market price mode", self.price_mode)
        form.addRow(self.include_raw_extractor_pi)
        form.addRow(
            "Home station",
            create_id_row(
                self,
                self.home_station_id,
                lambda: self._fetch_docked_station(self.home_station_id),
            ),
        )
        form.addRow(
            "Market station",
            create_id_row(
                self,
                self.market_station_id,
                lambda: self._fetch_docked_station(self.market_station_id),
            ),
        )

        layout.addLayout(form)
        layout.addStretch()

    def _fetch_docked_station(self, line_edit) -> None:
        char = self.app_state.selected_character

        if char is None:
            QMessageBox.warning(
                self,
                "No Character",
                "Select a character in the left list first "
                "(the character must be docked in-game).",
            )
            return

        client = self.app_state.get_esi_client(char)
        if not client:
            return

        self.logger.info(
            "Fetching docked station for %s", char.character_name
        )

        worker = LocationFetchWorker(client)
        worker.location_fetched.connect(
            lambda loc, le=line_edit, w=worker: self._on_location(w, le, loc)
        )
        worker.error.connect(lambda msg, w=worker: self._on_loc_error(w, msg))

        self._workers.add(worker)
        worker.start()

    def _on_location(self, worker, line_edit, loc: dict) -> None:
        self._workers.discard(worker)
        worker.deleteLater()

        station_id = loc.get("station_id") or loc.get("structure_id")

        if not station_id:
            QMessageBox.warning(
                self,
                "Not Docked",
                "The selected character is not docked at a "
                "station or structure.",
            )
            return

        set_optional_id(line_edit, int(station_id))
        self.logger.info("Docked station field set to %s", station_id)

    def _on_loc_error(self, worker, msg: str) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        QMessageBox.critical(
            self,
            "Location Error",
            f"Failed to fetch location: {msg[:80]}",
        )

    def load_settings(self) -> None:
        settings = self.app_state.settings

        self.cycle_days.setValue(settings.pi_cycle_days)
        self.search_range.setValue(settings.pi_search_range_jumps)

        price_index = self.price_mode.findText(settings.pi_price_mode)

        if price_index >= 0:
            self.price_mode.setCurrentIndex(price_index)
        else:
            self.price_mode.setCurrentIndex(0)

        self.include_raw_extractor_pi.setChecked(
            settings.pi_include_raw_extractor_pi
        )

        set_optional_id(self.home_station_id, settings.pi_home_station_id)
        set_optional_id(self.market_station_id, settings.pi_market_station_id)

        self.logger.debug("PI settings loaded into UI")

    def apply_to_settings(self) -> None:
        settings = self.app_state.settings

        settings.pi_cycle_days = self.cycle_days.value()
        settings.pi_search_range_jumps = self.search_range.value()
        settings.pi_price_mode = self.price_mode.currentText()
        settings.pi_include_raw_extractor_pi = (
            self.include_raw_extractor_pi.isChecked()
        )

        settings.pi_home_station_id = get_optional_id(
            self.home_station_id,
            settings.pi_home_station_id,
            "pi_home_station_id",
            self.logger,
        )

        settings.pi_market_station_id = get_optional_id(
            self.market_station_id,
            settings.pi_market_station_id,
            "pi_market_station_id",
            self.logger,
        )

        self.logger.debug("PI settings applied")

    def stop_workers(self) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(3000)
        self._workers.clear()