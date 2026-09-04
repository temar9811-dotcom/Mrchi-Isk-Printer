# FILE: app/ui/widgets/market_browser_widget.py
# VERSION: 1.5.0

import logging
import time
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel, QMenu,
)
from PySide6.QtCore import Qt, QThread, Signal
from app.esi.market_service import MarketService
from app.db.trade_blacklist_repository import TradeBlacklistRepository
from app.utils.formatting import fmt_age

STRUCTURE_ID_THRESHOLD = 1_000_000_000
MAX_RENDER_ROWS = 2000

class BrowserLoadWorker(QThread):
    loaded = Signal(list)
    error = Signal(str)

    def __init__(self, db, resolver, station_id, side, access_token,
                 station_region, force=False, cache_only=True):
        super().__init__()
        self.db = db
        self.resolver = resolver
        self.station_id = station_id
        self.side = side
        self.access_token = access_token
        self.station_region = station_region
        self.force = force
        self.cache_only = cache_only
        self.logger = logging.getLogger("app.ui.widgets.browser_worker")

    def run(self):
        try:
            market = MarketService(self.db)

            if self.station_id >= STRUCTURE_ID_THRESHOLD:
                orders = market.get_structure_orders_all(
                    self.station_id, self.access_token,
                    force=self.force, cache_only=self.cache_only,
                )
            else:
                region_orders = market.get_region_orders_all(
                    self.station_region, force=self.force, cache_only=self.cache_only
                )
                orders = [o for o in region_orders if o.location_id == self.station_id]

            want_buy = self.side == "buy"
            pool = [o for o in orders if bool(o.is_buy_order) == want_buy]

            agg = {}
            for o in pool:
                a = agg.setdefault(o.type_id, {"vol": 0, "count": 0, "best": None})
                a["vol"] += o.volume_remain
                a["count"] += 1
                if a["best"] is None:
                    a["best"] = o.price
                elif want_buy:
                    a["best"] = max(a["best"], o.price)
                else:
                    a["best"] = min(a["best"], o.price)

            names = self.resolver.resolve_names_bulk(list(agg.keys()))
            group_map = self.resolver.get_market_group_map()

            rows = []
            for type_id, a in agg.items():
                gid, gname = group_map.get(type_id, (0, "Other"))
                rows.append({
                    "type_id": type_id,
                    "name": names.get(type_id, f"Type {type_id}"),
                    "group": gname,
                    "best": a["best"] or 0.0,
                    "vol": a["vol"],
                    "count": a["count"],
                })

            rows.sort(key=lambda r: r["name"].lower())
            self.logger.info("Browser loaded %s rows for %s", len(rows), self.side)
            self.loaded.emit(rows)
        except Exception as exc:
            self.logger.exception("Browser load failed")
            self.error.emit(str(exc))

class OrderPane(QGroupBox):
    def __init__(self, app_state, side: str, parent=None):
        super().__init__("Buy Orders" if side == "buy" else "Sell Orders", parent)
        self.app_state = app_state
        self.side = side
        self.logger = logging.getLogger("app.ui.widgets.order_pane")
        self._rows = []
        self._workers = set()
        self._blacklist = set()
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        controls = QHBoxLayout()
        self.station_combo = QComboBox()
        self.station_combo.addItems(["Buy station", "Sell station"])
        if self.side == "sell":
            self.station_combo.setCurrentIndex(1)
        self.station_combo.currentIndexChanged.connect(lambda _: self.reload())
        controls.addWidget(self.station_combo)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Force-pull this station's book from ESI")
        self.btn_refresh.clicked.connect(lambda: self.reload(force=True))
        controls.addWidget(self.btn_refresh)

        self.lbl_age = QLabel("never")
        self.lbl_age.setStyleSheet("color: #8f9baa;")
        controls.addWidget(self.lbl_age)

        self.group_combo = QComboBox()
        self.group_combo.currentIndexChanged.connect(lambda _: self.apply_filters())
        controls.addWidget(self.group_combo, 1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search type...")
        self.search_edit.textChanged.connect(lambda _: self.apply_filters())
        controls.addWidget(self.search_edit, 1)

        layout.addLayout(controls)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Type", "Group", "Best", "Volume", "Orders"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #8f9baa;")
        layout.addWidget(self.status_label)

    def station_id(self) -> int:
        s = self.app_state.settings
        if self.station_combo.currentIndex() == 0:
            return s.trade_buy_station_id or 0
        return s.trade_sell_station_id or 0

    def _cache_key(self, station_id: int) -> str:
        if station_id >= STRUCTURE_ID_THRESHOLD:
            return f"orders:structure:{station_id}:all"
        region = self.app_state.get_universe_resolver().get_region_id_for_location(
            station_id
        ) or 10000002
        return f"orders:region_all:{region}"

    def update_age_label(self) -> None:
        station_id = self.station_id()
        if not station_id:
            self.lbl_age.setText("never")
            return
        market = MarketService(self.app_state.db)
        fetched = market.repo.get_meta_fetched_at(self._cache_key(station_id))
        if fetched is None:
            self.lbl_age.setText("never")
        else:
            self.lbl_age.setText(fmt_age(time.time() - fetched))

    def reload(self, force: bool = False) -> None:
        self.stop_workers()
        station_id = self.station_id()
        self.tree.clear()
        self._rows = []

        if not station_id:
            self.status_label.setText("No station configured.")
            return

        token = self.app_state.get_primary_token()
        resolver = self.app_state.get_universe_resolver()
        region = resolver.get_region_id_for_location(station_id, token) or 10000002

        worker = BrowserLoadWorker(
            self.app_state.db, resolver, station_id, self.side, token, region,
            force=force, cache_only=not force,
        )
        worker.loaded.connect(lambda rows, w=worker: self._on_loaded(w, rows))
        worker.error.connect(lambda m, w=worker: self._on_error(w, m))
        self._workers.add(worker)
        self.btn_refresh.setEnabled(False)
        self.status_label.setText("Loading..." + (" (ESI pull)" if force else " (cache)"))
        worker.start()

    def _on_loaded(self, worker, rows: list) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        self.btn_refresh.setEnabled(True)
        self._rows = rows
        self._blacklist = TradeBlacklistRepository(self.app_state.db).get_ids()

        # No "All groups": only real groups, default to the first one.
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        groups = sorted({r["group"] for r in rows})
        for group in groups:
            self.group_combo.addItem(group)
        if groups:
            self.group_combo.setCurrentIndex(0)
        self.group_combo.blockSignals(False)

        if not rows:
            self.status_label.setText("No cached data. Press Refresh to pull from ESI.")
        self.apply_filters()
        self.update_age_label()

    def apply_filters(self) -> None:
        text = self.search_edit.text().strip().lower()
        group = self.group_combo.currentText()

        self.tree.clear()
        shown = 0

        for r in self._rows:
            if group and r["group"] != group:
                continue
            if text and text not in r["name"].lower():
                continue

            name = r["name"]
            if r["type_id"] in self._blacklist:
                name = f"⛔ {name}"

            item = QTreeWidgetItem([
                name, r["group"], f"{r['best']:,.2f}",
                f"{r['vol']:,.0f}", str(r["count"]),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, r["type_id"])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, r["name"])
            self.tree.addTopLevelItem(item)
            shown += 1

            if shown >= MAX_RENDER_ROWS:
                break

        suffix = ""
        if shown >= MAX_RENDER_ROWS:
            suffix = f" (showing first {MAX_RENDER_ROWS:,} - use search)"

        self.status_label.setText(
            f"{shown:,} types{suffix} | best = "
            + ("highest bid" if self.side == "buy" else "lowest ask")
        )

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        type_id = item.data(0, Qt.ItemDataRole.UserRole)
        type_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if type_id is None:
            return

        repo = TradeBlacklistRepository(self.app_state.db)
        menu = QMenu(self)

        if type_id in self._blacklist:
            action = menu.addAction("Remove from Blacklist")
        else:
            action = menu.addAction("Add to Blacklist")

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen != action:
            return

        if type_id in self._blacklist:
            repo.remove(int(type_id))
            self._blacklist.discard(int(type_id))
        else:
            repo.add(int(type_id), type_name or item.text(0))
            self._blacklist.add(int(type_id))

        self.apply_filters()

    def _on_error(self, worker, msg: str) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        self.btn_refresh.setEnabled(True)
        self.status_label.setText(f"Load error: {msg[:50]}")

    def stop_workers(self) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(3000)
        self._workers.clear()

class MarketBrowserTab(QWidget):
    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.buy_pane = OrderPane(app_state, "buy", self)
        self.sell_pane = OrderPane(app_state, "sell", self)

        layout.addWidget(self.buy_pane)
        layout.addWidget(self.sell_pane)

    def stop_workers(self) -> None:
        self.buy_pane.stop_workers()
        self.sell_pane.stop_workers()