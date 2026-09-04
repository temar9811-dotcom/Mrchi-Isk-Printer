# FILE: app/ui/widgets/pi_panel.py
# VERSION: 1.5.0

import logging
import time

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt

from app.state.app_state import AppState
from app.db.esi_cache_repository import EsiCacheRepository
from app.ui.widgets.pi_worker import PiDataWorker
from app.ui.widgets.pi_detail_panel import PiDetailPanel
from app.services.pi_optimizer import PiOptimizer
from app.esi.market_service import MarketService
from app.utils.formatting import fmt_age


class PiPanel(QGroupBox):
    def __init__(self, app_state: AppState, parent=None):
        super().__init__("PI Colonies", parent)
        self.app_state = app_state
        self.logger = logging.getLogger("app.ui.widgets.pi_panel")
        self._active_workers = set()
        self._requested_char_id = None
        self._build_ui()
        self.app_state.selected_character_changed.connect(self._on_character_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Planet", "Type", "System", "Pins", "CC Level", "Last Update"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.currentItemChanged.connect(self._on_colony_selected)
        layout.addWidget(self.tree, 2)

        self.detail_panel = PiDetailPanel(self.app_state, self)
        layout.addWidget(self.detail_panel, 3)

        btn_layout = QHBoxLayout()
        self.status_label = QLabel("No character selected.")
        self.status_label.setStyleSheet("color: #8f9baa;")

        self.lbl_pi_age = QLabel("PI: never")
        self.lbl_pi_age.setStyleSheet("color: #8f9baa;")

        self.chk_raws = QCheckBox("Recommend Raws", self)
        self.chk_raws.setChecked(bool(self.app_state.settings.pi_include_raw_extractor_pi))
        self.chk_raws.stateChanged.connect(self._on_raws_toggled)

        self.btn_suggest = QPushButton("Suggest PI Batches")
        self.btn_suggest.clicked.connect(self.suggest_setup)
        self.btn_suggest.setEnabled(False)

        self.btn_refresh = QPushButton("Refresh PI Data")
        self.btn_refresh.setToolTip("Force-pull PI data from ESI for the selected character")
        self.btn_refresh.clicked.connect(lambda: self.fetch_data(cache_only=False))
        self.btn_refresh.setEnabled(False)

        btn_layout.addWidget(self.status_label, 1)
        btn_layout.addWidget(self.lbl_pi_age)
        btn_layout.addWidget(self.chk_raws)
        btn_layout.addWidget(self.btn_suggest)
        btn_layout.addWidget(self.btn_refresh)
        layout.addLayout(btn_layout)

    def _on_raws_toggled(self, state: int) -> None:
        enabled = bool(state)
        self.app_state.settings.pi_include_raw_extractor_pi = enabled
        self.app_state.save_settings()
        self.logger.info("Recommend Raws toggled: %s", enabled)

    def _pi_key(self, char_id) -> str:
        return f"pi:planets:{char_id}"

    def update_age_label(self) -> None:
        char = self.app_state.selected_character
        if char is None:
            self.lbl_pi_age.setText("PI: never")
            return
        repo = EsiCacheRepository(self.app_state.db)
        fetched = repo.fetched_at(self._pi_key(char.character_id))
        if fetched is None:
            self.lbl_pi_age.setText("PI: never")
        else:
            self.lbl_pi_age.setText(f"PI: {fmt_age(time.time() - fetched)}")

    def _on_character_changed(self, character) -> None:
        self.tree.clear()
        self.detail_panel.clear()
        if character is None:
            self._requested_char_id = None
            self.status_label.setText("No character selected.")
            self.btn_refresh.setEnabled(False)
            self.btn_suggest.setEnabled(False)
            self.update_age_label()
            return
        self._requested_char_id = character.character_id
        self.status_label.setText("Ready.")
        self.btn_refresh.setEnabled(True)
        self.btn_suggest.setEnabled(True)
        self.update_age_label()
        self.fetch_data(cache_only=True)

    def _on_colony_selected(self, current, previous) -> None:
        if current is None:
            self.detail_panel.load_colony(None)
            return
        colony = current.data(0, Qt.ItemDataRole.UserRole)
        self.detail_panel.load_colony(colony, cache_only=True)

    def fetch_data(self, cache_only: bool) -> None:
        char = self.app_state.selected_character
        if not char:
            return
        client = self.app_state.get_esi_client(char)
        resolver = self.app_state.get_universe_resolver()
        if not client:
            return
        self._requested_char_id = char.character_id
        self.btn_refresh.setEnabled(False)
        self.status_label.setText("Loading PI..." + (" (cache)" if cache_only else " (ESI pull)"))

        worker = PiDataWorker(client, resolver, self.app_state.db, cache_only=cache_only)
        worker.data_fetched.connect(lambda c, w=worker: self._on_data_fetched(w, c))
        worker.cache_empty.connect(lambda w=worker: self._on_cache_empty(w))
        worker.error.connect(lambda m, w=worker: self._on_error(w, m))
        worker.finished.connect(lambda w=worker: self._on_worker_done(w))
        self._active_workers.add(worker)
        worker.start()

    def _on_cache_empty(self, worker) -> None:
        self.status_label.setText("No cached PI data. Press Refresh PI Data.")

    def _on_worker_done(self, worker) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        if not self._active_workers:
            self.btn_refresh.setEnabled(True)
        self.update_age_label()

    def _on_data_fetched(self, worker, colonies: list) -> None:
        if worker.client.character.character_id != self._requested_char_id:
            return
        if not colonies:
            self.status_label.setText("No PI colonies found.")
            return
        self.tree.clear()
        for colony in colonies:
            item = QTreeWidgetItem([
                colony.display_name, colony.planet_type, colony.display_location,
                str(colony.num_pins), str(colony.upgrade_level),
                colony.last_update[:10] if colony.last_update else "?",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, colony)
            self.tree.addTopLevelItem(item)
        self.status_label.setText(f"{len(colonies)} colonies loaded.")

        if not worker.cache_only:
            self.detail_panel.refresh_current()

    def _on_error(self, worker, msg: str) -> None:
        if worker.client.character.character_id != self._requested_char_id:
            return
        self.status_label.setText(f"Error: {msg[:60]}")

    def suggest_setup(self) -> None:
        char = self.app_state.selected_character
        if not char:
            return

        self.btn_suggest.setEnabled(False)
        self.status_label.setText("Evaluating colonies...")

        client = self.app_state.get_esi_client(char)
        market = MarketService(self.app_state.db)
        resolver = self.app_state.get_universe_resolver()

        sell_region = 10000002

        optimizer = PiOptimizer(
            client, market, resolver, sell_region,
            include_raws=self.chk_raws.isChecked(),
        )

        all_suggestions = []
        for i in range(self.tree.topLevelItemCount()):
            colony = self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            all_suggestions.extend(optimizer.evaluate_colony(colony))

        self.btn_suggest.setEnabled(True)
        self.status_label.setText(f"{len(all_suggestions)} PI batch suggestions.")

        if not all_suggestions:
            QMessageBox.information(
                self, "PI Optimizer",
                "No collection batches worth hauling yet.\n"
                "(Stored value below 1m ISK per planet, or raws excluded.)",
            )
            return

        msg = "Suggested PI Batches:\n\n"
        for s in all_suggestions:
            msg += f"[{s.planet_name}] {s.action}\n"
            msg += f"  -> Est. value: {s.estimated_value:,.0f} ISK\n"
            msg += f"  -> {s.details}\n\n"

        QMessageBox.information(self, "PI Optimizer Suggestions", msg)

    def stop_workers(self) -> None:
        self.detail_panel.stop_workers()
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(3000)
        self._active_workers.clear()