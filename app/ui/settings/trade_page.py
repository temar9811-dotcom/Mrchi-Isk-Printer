# FILE: app/ui/settings/trade_page.py
# VERSION: 1.3.0

import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
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


class TradeSettingsPage(QWidget):
    """
    Market Trade settings page.

    Buy/sell characters are chosen from dropdowns of added ESI
    characters. Stations are entered by ID or the docked-station
    button with the selected character.
    """

    def __init__(self, app_state: AppState):
        super().__init__()

        self.logger = logging.getLogger("app.ui.settings.trade_page")
        self.app_state = app_state
        self._workers = set()

        self.app_state.characters_changed.connect(
            self._refresh_character_combos
        )

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self.cycle_days = QSpinBox(self)
        self.cycle_days.setRange(1, 365)
        self.cycle_days.setSuffix(" days")

        self.item_limit = QSpinBox(self)
        self.item_limit.setRange(1, 1000)

        self.full_load_m3 = QSpinBox(self)
        self.full_load_m3.setRange(0, 10_000_000)
        self.full_load_m3.setSingleStep(1000)
        self.full_load_m3.setSuffix(" m3")

        self.citadel_sales_tax = QDoubleSpinBox(self)
        self.citadel_sales_tax.setRange(0.0, 25.0)
        self.citadel_sales_tax.setDecimals(2)
        self.citadel_sales_tax.setSuffix(" %")

        self.citadel_broker_fee = QDoubleSpinBox(self)
        self.citadel_broker_fee.setRange(0.0, 25.0)
        self.citadel_broker_fee.setDecimals(2)
        self.citadel_broker_fee.setSuffix(" %")

        self.buy_character_combo = QComboBox(self)
        self.sell_character_combo = QComboBox(self)

        self.buy_station_id = create_id_line_edit(self)
        self.sell_station_id = create_id_line_edit(self)

        form.addRow("Trade cycle length", self.cycle_days)
        form.addRow("Item type limit", self.item_limit)
        form.addRow("Full load size", self.full_load_m3)
        form.addRow("Citadel sales tax", self.citadel_sales_tax)
        form.addRow("Citadel broker fee", self.citadel_broker_fee)
        form.addRow("Buy character", self.buy_character_combo)
        form.addRow("Sell character", self.sell_character_combo)
        form.addRow(
            "Buy station",
            create_id_row(
                self,
                self.buy_station_id,
                lambda: self._fetch_docked_station(self.buy_station_id),
            ),
        )
        form.addRow(
            "Sell station",
            create_id_row(
                self,
                self.sell_station_id,
                lambda: self._fetch_docked_station(self.sell_station_id),
            ),
        )

        layout.addLayout(form)
        layout.addStretch()

        self._refresh_character_combos()

    # --- character dropdowns ---

    def _refresh_character_combos(self) -> None:
        """
        Rebuild character dropdowns from added ESI characters,
        preserving current selection (or falling back to settings).
        """
        settings = self.app_state.settings

        buy_keep = self.buy_character_combo.currentData()
        sell_keep = self.sell_character_combo.currentData()

        self.buy_character_combo.clear()
        self.buy_character_combo.addItem("[None]", None)

        self.sell_character_combo.clear()
        self.sell_character_combo.addItem("[None]", None)

        for char in self.app_state.characters:
            self.buy_character_combo.addItem(
                char.character_name, char.character_id
            )
            self.sell_character_combo.addItem(
                char.character_name, char.character_id
            )

        self._set_combo_by_id(
            self.buy_character_combo,
            buy_keep if buy_keep is not None
            else settings.trade_buy_character_id,
        )
        self._set_combo_by_id(
            self.sell_character_combo,
            sell_keep if sell_keep is not None
            else settings.trade_sell_character_id,
        )

        self.logger.debug(
            "Character combos refreshed (%s characters)",
            len(self.app_state.characters),
        )

    def _set_combo_by_id(self, combo: QComboBox, char_id) -> None:
        if char_id is None:
            combo.setCurrentIndex(0)
            return

        for i in range(combo.count()):
            if combo.itemData(i) == char_id:
                combo.setCurrentIndex(i)
                return

        combo.setCurrentIndex(0)

    # --- docked station buttons ---

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
        worker.error.connect(
            lambda msg, w=worker: self._on_loc_error(w, msg)
        )

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
            self, "Location Error", f"Failed to fetch location: {msg[:80]}"
        )

    # --- settings load/apply ---

    def load_settings(self) -> None:
        settings = self.app_state.settings

        self.cycle_days.setValue(settings.trade_cycle_days)
        self.item_limit.setValue(settings.trade_item_limit)
        self.full_load_m3.setValue(settings.trade_full_load_m3)
        self.citadel_sales_tax.setValue(settings.citadel_sales_tax_pct)
        self.citadel_broker_fee.setValue(settings.citadel_broker_fee_pct)

        self._set_combo_by_id(
            self.buy_character_combo, settings.trade_buy_character_id
        )
        self._set_combo_by_id(
            self.sell_character_combo, settings.trade_sell_character_id
        )

        set_optional_id(self.buy_station_id, settings.trade_buy_station_id)
        set_optional_id(self.sell_station_id, settings.trade_sell_station_id)

        self.logger.debug("Market Trade settings loaded into UI")

    def apply_to_settings(self) -> None:
        settings = self.app_state.settings

        settings.trade_cycle_days = self.cycle_days.value()
        settings.trade_item_limit = self.item_limit.value()
        settings.trade_full_load_m3 = self.full_load_m3.value()
        settings.citadel_sales_tax_pct = self.citadel_sales_tax.value()
        settings.citadel_broker_fee_pct = self.citadel_broker_fee.value()

        settings.trade_buy_character_id = (
            self.buy_character_combo.currentData()
        )
        settings.trade_sell_character_id = (
            self.sell_character_combo.currentData()
        )

        for line_edit, attr, name in (
            (self.buy_station_id, "trade_buy_station_id", "trade_buy_station_id"),
            (self.sell_station_id, "trade_sell_station_id", "trade_sell_station_id"),
        ):
            setattr(
                settings,
                attr,
                get_optional_id(line_edit, getattr(settings, attr), name, self.logger),
            )

        self.logger.debug("Market Trade settings applied")

    def stop_workers(self) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(3000)
        self._workers.clear()