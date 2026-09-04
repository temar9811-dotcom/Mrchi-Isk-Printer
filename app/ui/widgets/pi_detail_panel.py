# FILE: app/ui/widgets/pi_detail_panel.py
# VERSION: 1.3.0

import logging

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QSplitter, QTreeWidget, QTreeWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt

from app.state.app_state import AppState
from app.models.pi_colony import PiColony
from app.models.pi_colony_detail import PiColonyDetail
from app.ui.widgets.pi_detail_worker import PiDetailWorker


CATEGORY_ORDER = [
    "Extractors", "Factories", "Command Center",
    "Launchers", "Storage", "Other",
]


class PiDetailPanel(QGroupBox):
    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Colony Layout", parent)
        self.app_state = app_state
        self.logger = logging.getLogger("app.ui.widgets.pi_detail_panel")
        self._active_workers = set()
        self._requested_planet_id = None
        self._current_colony = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.pins_tree = QTreeWidget(splitter)
        self.pins_tree.setHeaderLabels(["Pin", "Details"])
        self.pins_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pins_tree.setAlternatingRowColors(True)

        self.routes_tree = QTreeWidget(splitter)
        self.routes_tree.setHeaderLabels(["Source", "Destination", "Item", "Qty"])
        self.routes_tree.setRootIsDecorated(False)
        self.routes_tree.setAlternatingRowColors(True)
        self.routes_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)

        splitter.addWidget(self.pins_tree)
        splitter.addWidget(self.routes_tree)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

        self.status_label = QLabel("Select a colony above.")
        self.status_label.setStyleSheet("color: #8f9baa;")
        layout.addWidget(self.status_label)

    def clear(self) -> None:
        self._current_colony = None
        self._requested_planet_id = None
        self.pins_tree.clear()
        self.routes_tree.clear()
        self.status_label.setText("Select a colony above.")

    def refresh_current(self) -> None:
        if self._current_colony is not None:
            self.load_colony(self._current_colony, cache_only=False)

    def load_colony(self, colony: PiColony, cache_only: bool = True) -> None:
        if colony is None:
            self.clear()
            return

        self._current_colony = colony
        client = self.app_state.get_esi_client()
        resolver = self.app_state.get_universe_resolver()
        if not client:
            return

        self._requested_planet_id = colony.planet_id
        self.pins_tree.clear()
        self.routes_tree.clear()
        self.status_label.setText(
            f"Loading {colony.display_name}..."
            + (" (cache)" if cache_only else " (ESI pull)")
        )

        worker = PiDetailWorker(
            client, resolver, self.app_state.db, colony, cache_only=cache_only
        )
        worker.detail_fetched.connect(
            lambda detail, w=worker: self._on_detail_fetched(w, detail)
        )
        worker.cache_empty.connect(lambda w=worker: self._on_cache_empty(w))
        worker.error.connect(lambda msg, w=worker: self._on_error(w, msg))
        worker.finished.connect(lambda w=worker: self._on_worker_done(w))
        self._active_workers.add(worker)
        worker.start()

    def _on_cache_empty(self, worker) -> None:
        self.status_label.setText("No cached layout. Press Refresh PI Data.")

    def _on_worker_done(self, worker) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()

    def _on_detail_fetched(self, worker, detail: PiColonyDetail) -> None:
        if detail.planet_id != self._requested_planet_id:
            return

        self.setTitle(f"Colony Layout - {detail.planet_name}")

        groups = {}
        for pin in detail.pins:
            groups.setdefault(pin.category, []).append(pin)

        for category in CATEGORY_ORDER:
            pins = groups.get(category)
            if not pins:
                continue

            cat_item = QTreeWidgetItem([f"{category} ({len(pins)})", ""])
            self.pins_tree.addTopLevelItem(cat_item)

            for pin in pins:
                pin_item = QTreeWidgetItem([pin.type_name, self._pin_details(pin)])
                for content in pin.contents:
                    pin_item.addChild(QTreeWidgetItem(
                        [f"  {content.type_name}", f"{content.amount:,}"]
                    ))
                cat_item.addChild(pin_item)

            cat_item.setExpanded(True)

        for route in detail.routes:
            self.routes_tree.addTopLevelItem(QTreeWidgetItem([
                route.source_name, route.destination_name,
                route.content_type_name, f"{route.quantity:,}",
            ]))

        self.status_label.setText(
            f"{len(detail.pins)} pins | "
            f"{len(detail.routes)} routes | "
            f"{detail.links_count} links"
        )

    def _pin_details(self, pin) -> str:
        parts = []

        if pin.category == "Extractors":
            parts.append(f"{pin.head_count} heads")
            if pin.cycle_time_display:
                parts.append(f"cycle {pin.cycle_time_display}")
            if pin.qty_per_cycle:
                parts.append(f"{pin.qty_per_cycle:,}/cycle")
            if pin.product_type_name:
                parts.append(f"product: {pin.product_type_name}")
            if pin.expiry_time:
                try:
                    from datetime import datetime, timezone
                    exp_dt = datetime.fromisoformat(pin.expiry_time.replace("Z", "+00:00"))
                    delta = exp_dt - datetime.now(timezone.utc)
                    if delta.total_seconds() < 0:
                        parts.append("EXPIRED")
                    else:
                        parts.append(f"finishes in {delta.days}d {delta.seconds // 3600}h")
                except Exception:
                    pass
        elif pin.category == "Factories":
            if pin.schematic_name:
                parts.append(f"Schematic: {pin.schematic_name}")
            else:
                parts.append("No Schematic")

        if pin.upgrade_level:
            parts.append(f"lvl {pin.upgrade_level}")

        return " | ".join(parts)

    def _on_error(self, worker, msg: str) -> None:
        if worker.colony.planet_id != self._requested_planet_id:
            return
        self.status_label.setText(f"Error: {msg[:60]}")

    def stop_workers(self) -> None:
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(3000)
        self._active_workers.clear()