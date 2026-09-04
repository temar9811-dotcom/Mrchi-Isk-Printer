# FILE: app/ui/widgets/trade_panel.py
# VERSION: 1.23.1
import logging
import time
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QTreeWidget, QTreeWidgetItem, QCheckBox,
    QHeaderView, QSplitter, QMessageBox, QComboBox, QMenu, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from app.state.app_state import AppState
from app.services.trade_calculator import TradeCalculator, POPULAR_TRADE_TYPES
from app.services.tax_service import TaxService
from app.services.market_refresh_service import MarketRefreshService
from app.esi.market_service import MarketService
from app.db.trade_batch_repository import TradeBatchRepository
from app.db.trade_blacklist_repository import TradeBlacklistRepository
from app.models.trade_batch import (
    TradeBatch, TradeBatchItem, TradeBatchRecommendation, TradeSuggestion,
)
from app.ui.widgets.trade_worker import TradeWorker, MarketRefreshWorker
from app.ui.widgets.batch_list_widget import BatchListWidget
from app.ui.widgets.blacklist_dialog import BlacklistDialog
from app.services.price_alert_service import PriceAlertService
from app.ui.widgets.price_alerts_dialog import PriceAlertsDialog
from app.ui.widgets.isk_spinbox import IskSpinBox
from app.ui.widgets.trade_panel_calc import (
    get_active_batch_exclusions, group_into_batches_smart,
)
from app.services.ignore_groups import get_ignore_group_names, get_type_ids_for_groups
from app.ui.widgets.ignore_list_dialog import IgnoreListDialog
from app.utils.formatting import fmt_num, fmt_age

STRUCTURE_ID_THRESHOLD = 1_000_000_000
REGIONAL_HUBS = {
    "Jita 4-4": (60003760, 10000002),
    "Amarr": (60008494, 10000043),
    "Dodixie": (60003758, 10000036),
    "Rens": (60002059, 10000042),
    "Hek": (60004471, 10000042),
}
DEFAULT_HUB_LABEL = "Default (Settings)"


class TradePanel(QGroupBox):
    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Market Trade Calculator", parent)
        self.app_state = app_state
        self.logger = logging.getLogger("app.ui.widgets.trade_panel")
        self._active_workers = set()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._on_auto_refresh)
        self._setup_auto_refresh()
        self._build_ui()
        self.update_market_age()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 12, 8, 8)
        main_layout.setSpacing(6)

        # Row 1: cycle / items / share
        self.row1 = QHBoxLayout()
        self.row1.addWidget(QLabel("Cycle (days):"))
        self.spin_cycle = QSpinBox(); self.spin_cycle.setRange(1, 90)
        self.spin_cycle.setValue(self.app_state.settings.trade_cycle_days)
        self.row1.addWidget(self.spin_cycle)
        self.row1.addWidget(QLabel("Max Items:"))
        self.spin_items = QSpinBox(); self.spin_items.setRange(1, 100)
        self.spin_items.setValue(self.app_state.settings.trade_item_limit)
        self.row1.addWidget(self.spin_items)
        self.row1.addWidget(QLabel("My share %:"))
        self.spin_share = QDoubleSpinBox(); self.spin_share.setRange(0.1, 100.0)
        self.spin_share.setDecimals(1); self.spin_share.setSingleStep(0.5)
        self.spin_share.setValue(self.app_state.settings.trade_market_share_pct)
        self.row1.addWidget(self.spin_share)
        self.row1.addStretch()

        # Row 2: hauling + budget
        self.row2 = QHBoxLayout()
        self.row2.addWidget(QLabel("ISK/m3:"))
        self.spin_haul_m3 = IskSpinBox()
        self.row2.addWidget(self.spin_haul_m3)
        self.row2.addWidget(QLabel("Min load:"))
        self.spin_haul_min = IskSpinBox()
        self.row2.addWidget(self.spin_haul_min)
        self.row2.addWidget(QLabel("Full load:"))
        self.spin_haul_full = IskSpinBox()
        self.row2.addWidget(self.spin_haul_full)
        self.row2.addWidget(QLabel("Budget (0=off):"))
        self.spin_budget = IskSpinBox()
        self.row2.addWidget(self.spin_budget)
        self.chk_use_wallet = QCheckBox("Use buy char wallet")
        self.chk_use_wallet.toggled.connect(self._on_wallet_toggled)
        self.row2.addWidget(self.chk_use_wallet)
        self.btn_ignore_list = QPushButton("Ignore List")
        self.btn_ignore_list.clicked.connect(self.open_ignore_list)
        self.row2.addWidget(self.btn_ignore_list)
        self.row2.addStretch()
        self._load_haul_boxes()

        # Row 3: hubs
        self.row3 = QHBoxLayout()
        self.chk_use_hubs = QCheckBox("Use Regional Hubs")
        self.chk_use_hubs.toggled.connect(self._on_hubs_toggled)
        self.row3.addWidget(self.chk_use_hubs)
        self.row3.addWidget(QLabel("Buy hub:"))
        self.combo_buy_hub = QComboBox()
        self.combo_buy_hub.addItems([DEFAULT_HUB_LABEL] + list(REGIONAL_HUBS.keys()))
        self.combo_buy_hub.setEnabled(False)
        self.row3.addWidget(self.combo_buy_hub)
        self.row3.addWidget(QLabel("Sell hub:"))
        self.combo_sell_hub = QComboBox()
        self.combo_sell_hub.addItems([DEFAULT_HUB_LABEL] + list(REGIONAL_HUBS.keys()))
        self.combo_sell_hub.setEnabled(False)
        self.row3.addWidget(self.combo_sell_hub)
        self.chk_auto_refresh = QCheckBox("Auto-refresh (20 min)")
        self.chk_auto_refresh.setToolTip("Automatically refresh market every 20 minutes")
        self.chk_auto_refresh.setChecked(self.app_state.settings.trade_auto_refresh_minutes > 0)
        self.chk_auto_refresh.toggled.connect(self._on_auto_refresh_toggled)
        self.row3.addWidget(self.chk_auto_refresh)
        self.row3.addStretch()
        self._load_hub_boxes()

        # Row 4: toggles + refresh + blacklist + price alerts + calculate
        self.row4 = QHBoxLayout()
        self.chk_instant_buy = QCheckBox("Instant Buy")
        self.row4.addWidget(self.chk_instant_buy)
        self.chk_instant_sell = QCheckBox("Instant Sell")
        self.row4.addWidget(self.chk_instant_sell)
        self.chk_invert = QCheckBox("Invert")
        self.chk_invert.setToolTip("Swap buy and sell stations")
        self.row4.addWidget(self.chk_invert)
        self.chk_exclude_active = QCheckBox("Exclude active batches")
        self.chk_exclude_active.setChecked(self.app_state.settings.trade_exclude_active_batches)
        self.chk_exclude_active.toggled.connect(self._on_exclude_active_toggled)
        self.row4.addWidget(self.chk_exclude_active)
        self.chk_include_alerted = QCheckBox("Include alerted items")
        self.chk_include_alerted.setToolTip("Include items flagged by unexpected price drop alerts")
        self.row4.addWidget(self.chk_include_alerted)
        self.btn_refresh_market = QPushButton("Refresh Market")
        self.btn_refresh_market.clicked.connect(self.refresh_market)
        self.row4.addWidget(self.btn_refresh_market)
        self.lbl_market_age = QLabel("Market: never")
        self.lbl_market_age.setStyleSheet("color: #8f9baa;")
        self.row4.addWidget(self.lbl_market_age)
        self.btn_blacklist = QPushButton("Blacklist")
        self.btn_blacklist.clicked.connect(self.open_blacklist)
        self.row4.addWidget(self.btn_blacklist)
        self.btn_price_alerts = QPushButton("Price Alerts")
        self.btn_price_alerts.clicked.connect(self.open_price_alerts)
        self.row4.addWidget(self.btn_price_alerts)
        self.row4.addStretch()
        self.btn_calc = QPushButton("Calculate Recommended Batches")
        self.btn_calc.clicked.connect(self.start_calculation)
        self.row4.addWidget(self.btn_calc)

        main_layout.addLayout(self.row1)
        main_layout.addLayout(self.row2)
        main_layout.addLayout(self.row3)
        main_layout.addLayout(self.row4)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.tree = QTreeWidget(splitter)
        self.tree.setHeaderLabels(
            ["Batch / Item", "Qty", "Sellable", "Buy", "Sell", "Vol (m3)",
             "Haul", "Fees", "Profit", "ISK/m3", "Shift"]
        )
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        splitter.addWidget(self.tree)

        accept_layout = QHBoxLayout()
        self.btn_accept = QPushButton("Accept Selected Batch(es)")
        self.btn_accept.clicked.connect(self.accept_selected)
        accept_layout.addWidget(self.btn_accept)
        accept_layout.addStretch()
        main_layout.addLayout(accept_layout)

        self.batch_list = BatchListWidget(self.app_state, splitter)
        splitter.addWidget(self.batch_list)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 1)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #8f9baa;")
        main_layout.addWidget(self.status_label)

    def _load_haul_boxes(self) -> None:
        s = self.app_state.settings
        self.spin_haul_m3.setValue(s.haul_per_m3_isk)
        self.spin_haul_min.setValue(s.haul_min_charge_isk)
        self.spin_haul_full.setValue(s.haul_full_load_charge_isk)
        self.spin_budget.setValue(s.trade_budget_isk)
        self.chk_use_wallet.setChecked(s.trade_use_wallet)
        self.spin_budget.setEnabled(not s.trade_use_wallet)

    def _load_hub_boxes(self) -> None:
        s = self.app_state.settings
        self.chk_use_hubs.setChecked(s.trade_use_hubs)
        self.combo_buy_hub.setEnabled(s.trade_use_hubs)
        self.combo_sell_hub.setEnabled(s.trade_use_hubs)
        for combo, value in (
            (self.combo_buy_hub, s.trade_buy_hub),
            (self.combo_sell_hub, s.trade_sell_hub),
        ):
            idx = combo.findText(value)
            combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_wallet_toggled(self, checked: bool) -> None:
        self.spin_budget.setEnabled(not checked)
        self.app_state.settings.trade_use_wallet = checked
        self.app_state.save_settings()

    def _on_hubs_toggled(self, checked: bool) -> None:
        self.combo_buy_hub.setEnabled(checked)
        self.combo_sell_hub.setEnabled(checked)
        self.app_state.settings.trade_use_hubs = checked
        self.app_state.save_settings()

    def _on_exclude_active_toggled(self, checked: bool) -> None:
        self.app_state.settings.trade_exclude_active_batches = checked
        self.app_state.save_settings()

    def _setup_auto_refresh(self) -> None:
        minutes = self.app_state.settings.trade_auto_refresh_minutes
        if minutes > 0:
            self.refresh_timer.start(minutes * 60 * 1000)
            self.logger.info("Auto-refresh enabled: every %s minutes", minutes)
        else:
            self.refresh_timer.stop()

    def _on_auto_refresh(self) -> None:
        self.logger.info("Auto-refresh triggered")
        if self.btn_refresh_market.isEnabled():
            self.refresh_market()

    def _on_auto_refresh_toggled(self, checked: bool) -> None:
        self.app_state.settings.trade_auto_refresh_minutes = 20 if checked else 0
        self.app_state.save_settings()
        self._setup_auto_refresh()

    def _save_trade_controls(self) -> None:
        s = self.app_state.settings
        s.haul_per_m3_isk = self.spin_haul_m3.value()
        s.haul_min_charge_isk = self.spin_haul_min.value()
        s.haul_full_load_charge_isk = self.spin_haul_full.value()
        s.trade_market_share_pct = self.spin_share.value()
        s.trade_cycle_days = self.spin_cycle.value()
        s.trade_item_limit = self.spin_items.value()
        if not s.trade_use_wallet:
            s.trade_budget_isk = self.spin_budget.value()
        s.trade_buy_hub = self.combo_buy_hub.currentText()
        s.trade_sell_hub = self.combo_sell_hub.currentText()
        self.app_state.save_settings()

    def open_price_alerts(self) -> None:
        alert_service = PriceAlertService(self.app_state.db)
        alert_service.scan_for_drops(threshold_pct=15.0)
        dlg = PriceAlertsDialog(self.app_state.db, self)
        dlg.exec()

    def _effective_locations(self):
        s = self.app_state.settings
        if self.chk_use_hubs.isChecked():
            buy = REGIONAL_HUBS.get(
                self.combo_buy_hub.currentText(),
                (s.trade_buy_station_id or 0, 10000002),
            )
            sell = REGIONAL_HUBS.get(
                self.combo_sell_hub.currentText(),
                (s.trade_sell_station_id or 0, 10000002),
            )
            return buy[0], sell[0], buy[1], sell[1]
        return (
            s.trade_buy_station_id or 0,
            s.trade_sell_station_id or 0,
            10000002, 10000002,
        )

    def _station_fetched_at(self, loc: int):
        if not loc:
            return None
        market = MarketService(self.app_state.db)
        if loc >= STRUCTURE_ID_THRESHOLD:
            key = f"orders:structure:{loc}:all"
        else:
            region = self.app_state.get_universe_resolver().get_region_id_for_location(loc) or 10000002
            key = f"orders:region_all:{region}"
        return market.repo.get_meta_fetched_at(key)

    def update_market_age(self) -> None:
        buy_loc, sell_loc, _, _ = self._effective_locations()
        stamps = [t for t in (self._station_fetched_at(buy_loc), self._station_fetched_at(sell_loc)) if t is not None]
        if not stamps:
            self.lbl_market_age.setText("Market: never")
        else:
            self.lbl_market_age.setText(f"Market: {fmt_age(time.time() - min(stamps))}")

    def refresh_market(self) -> None:
        self.btn_refresh_market.setEnabled(False)
        self.btn_calc.setEnabled(False)
        self.status_label.setText("Refreshing market data...")
        buy_loc, sell_loc, _, _ = self._effective_locations()
        service = MarketRefreshService(
            self.app_state.db, self.app_state.get_universe_resolver(), self.app_state.get_primary_token()
        )
        worker = MarketRefreshWorker(service, buy_loc, sell_loc, list(POPULAR_TRADE_TYPES))
        worker.progress.connect(self.status_label.setText)
        worker.finished_ok.connect(lambda w=worker: self._on_refresh_done(w))
        worker.error.connect(lambda m, w=worker: self._on_refresh_error(w, m))
        self._active_workers.add(worker)
        worker.start()

    def _on_refresh_done(self, worker) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        self.btn_refresh_market.setEnabled(True)
        self.update_market_age()
        self.start_calculation()

    def _on_refresh_error(self, worker, msg: str) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        self.btn_refresh_market.setEnabled(True)
        self.btn_calc.setEnabled(True)
        self.status_label.setText(f"Refresh failed: {msg[:50]}")

    def open_blacklist(self) -> None:
        dialog = BlacklistDialog(self.app_state.db, self)
        dialog.exec()
        dialog.deleteLater()

    def open_ignore_list(self) -> None:
        dialog = IgnoreListDialog(self.app_state, self)
        if dialog.exec():
            self.start_calculation()
        dialog.deleteLater()

    def _tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, TradeSuggestion):
            return
        menu = QMenu(self)
        action = menu.addAction(f"Blacklist {data.type_name}")
        if menu.exec(self.tree.viewport().mapToGlobal(pos)) == action:
            TradeBlacklistRepository(self.app_state.db).add(data.type_id, data.type_name)
            self.status_label.setText(f"{data.type_name} blacklisted.")

    def _resolve_budget(self) -> float:
        if not self.chk_use_wallet.isChecked():
            return self.spin_budget.value()
        buy_id = self.app_state.settings.trade_buy_character_id
        char = self.app_state.get_character(buy_id)
        if char is None:
            self.status_label.setText("No buy character set - wallet budget ignored.")
            return self.spin_budget.value()
        client = self.app_state.get_esi_client(char)
        if client is None:
            return self.spin_budget.value()
        try:
            balance = float(client.get_wallet_balance())
            self.spin_budget.setValue(balance)
            return balance
        except Exception as exc:
            self.status_label.setText(f"Wallet fetch failed: {str(exc)[:40]}")
            return self.spin_budget.value()

    def start_calculation(self) -> None:
        self.btn_calc.setEnabled(False)
        self.status_label.setText("Calculating from cache...")
        self.tree.clear()
        self._save_trade_controls()
        budget = self._resolve_budget()
        buy_loc, sell_loc, buy_region, sell_region = self._effective_locations()
        s = self.app_state.settings

        buy_client = self.app_state.get_esi_client(self.app_state.get_character(s.trade_buy_character_id)) if s.trade_buy_character_id else None
        sell_client = self.app_state.get_esi_client(self.app_state.get_character(s.trade_sell_character_id)) if s.trade_sell_character_id else None
        tax = TaxService(self.app_state.get_universe_resolver(), s, buy_client, sell_client)
        try:
            buy_fee = tax.buy_leg_fee_frac(buy_loc, placed=not self.chk_instant_buy.isChecked())
            sell_fee = tax.sell_leg_fee_frac(sell_loc, placed=not self.chk_instant_sell.isChecked())
        except Exception as exc:
            self.logger.warning("Fee calc failed, using 0: %s", exc)
            buy_fee, sell_fee = 0.0, 0.0

        blacklist = TradeBlacklistRepository(self.app_state.db).get_ids()
        
        # Add active batch exclusions if enabled
        if self.chk_exclude_active.isChecked():
            active_exclusions = get_active_batch_exclusions(
                self.app_state.db, s.trade_buy_character_id or 0, s.trade_sell_character_id or 0
            )
            blacklist = blacklist.union(active_exclusions)

        enabled_groups = {name for name, enabled in self.app_state.settings.trade_ignore_groups.items() if enabled}
        if enabled_groups:
            ignored_ids = get_type_ids_for_groups(enabled_groups)
            blacklist = blacklist.union(ignored_ids)
            self.logger.info("Excluding %d type_ids from ignore groups", len(ignored_ids))

        params = {
            "buy_region": buy_region, "buy_loc": buy_loc,
            "sell_region": sell_region, "sell_loc": sell_loc,
            "cycle_days": self.spin_cycle.value(), "max_items": self.spin_items.value(),
            "haul_per_m3": self.spin_haul_m3.value(), "haul_min_charge": self.spin_haul_min.value(),
            "haul_full_load": self.spin_haul_full.value(), "haul_capacity": s.haul_jf_capacity_m3,
            "budget_isk": budget, "market_share_pct": self.spin_share.value(),
            "buy_fee_frac": buy_fee, "sell_fee_frac": sell_fee,
            "exclude_types": set(), "blacklist": blacklist,
            "access_token": self.app_state.get_primary_token(),
            "instant_buy": self.chk_instant_buy.isChecked(),
            "instant_sell": self.chk_instant_sell.isChecked(),
            "invert": self.chk_invert.isChecked(),
            "cache_only": True,
        }
        market_service = MarketService(self.app_state.db)
        resolver = self.app_state.get_universe_resolver()
        calculator = TradeCalculator(market_service, resolver)
        worker = TradeWorker(calculator, params)
        worker.finished.connect(lambda res, w=worker: self._on_finished(w, res))
        worker.error.connect(lambda msg, w=worker: self._on_error(w, msg))
        self._active_workers.add(worker)
        worker.start()

    def _on_finished(self, worker, results: list) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        if not self._active_workers:
            self.btn_calc.setEnabled(True)
        if not results:
            self.status_label.setText("No trades in cache. Press Refresh Market to pull fresh data.")
            self.btn_accept.setEnabled(False)
            return
        
        # Apply smart batch grouping
        s = self.app_state.settings
        all_suggestions = []
        for batch in results:
            all_suggestions.extend(batch.items)
        
        regrouped = group_into_batches_smart(
            all_suggestions, self.spin_items.value(),
            s.haul_jf_capacity_m3, self._resolve_budget(),
            s.trade_max_merge_attempts,
        )
        
        is_all_negative = regrouped[0].items[0].net_profit <= 0 if regrouped and regrouped[0].items else False
        if is_all_negative:
            self.status_label.setText("No profitable trades found. Showing top 5 least-negative trades.")
            self.btn_accept.setEnabled(False)
            text_color = Qt.GlobalColor.red
        else:
            self.status_label.setText(f"Found {len(regrouped)} recommended JF batches.")
            self.btn_accept.setEnabled(True)
            text_color = Qt.GlobalColor.green

        for batch in regrouped:
            batch_item = QTreeWidgetItem([
                f"{batch.batch_name} ({batch.total_volume:,.0f} m3, spend {fmt_num(batch.total_buy)})",
                "", "", "", "", "", "", "", f"{fmt_num(batch.total_profit)} ISK", "", "",
            ])
            batch_item.setData(0, Qt.ItemDataRole.UserRole, batch)
            batch_item.setForeground(0, text_color)
            for r in batch.items:
                prefix = "⚡ " if hasattr(r, 'sell_mode') and r.sell_mode == "instant" else "  "
                shift_display = f"{r.shift_ratio:.2f}" if hasattr(r, 'shift_ratio') else "1.00"
                child = QTreeWidgetItem([
                    f"{prefix}{r.type_name}", f"{r.quantity:,}", f"{r.est_sellable:,}",
                    f"{r.buy_price:,.2f}", f"{r.sell_price:,.2f}", f"{r.total_volume:,.1f}",
                    fmt_num(r.hauling_cost), fmt_num(r.tax_cost), fmt_num(r.net_profit),
                    f"{r.profit_per_m3:,.2f}",
                    shift_display,
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, r)
                if is_all_negative:
                    child.setForeground(0, Qt.GlobalColor.red)
                batch_item.addChild(child)
            batch_item.setExpanded(True)
            self.tree.addTopLevelItem(batch_item)

    def accept_selected(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a batch or item.")
            return
        s = self.app_state.settings
        batch = TradeBatch(buy_char_id=s.trade_buy_character_id or 0, sell_char_id=s.trade_sell_character_id or 0)
        total_expected = 0.0
        for tree_item in selected:
            data = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, TradeBatchRecommendation):
                for item in data.items:
                    batch.items.append(TradeBatchItem(
                        type_id=item.type_id, type_name=item.type_name,
                        quantity=item.quantity, buy_price=item.buy_price,
                        sell_price=item.sell_price,
                    ))
                    total_expected += item.net_profit
            elif isinstance(data, TradeSuggestion):
                batch.items.append(TradeBatchItem(
                    type_id=data.type_id, type_name=data.type_name,
                    quantity=data.quantity, buy_price=data.buy_price,
                    sell_price=data.sell_price,
                ))
                total_expected += data.net_profit
        batch.expected_profit = total_expected
        repo = TradeBatchRepository(self.app_state.db)
        batch_id = repo.save_batch(batch)
        self.status_label.setText(f"Batch {batch_id} saved and tracked.")
        self.batch_list.refresh()
        self.tree.clear()

    def _on_error(self, worker, msg: str) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        if not self._active_workers:
            self.btn_calc.setEnabled(True)
        self.status_label.setText(f"Error: {msg[:60]}")

    def stop_workers(self) -> None:
        self.batch_list.stop_workers()
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(3000)
        self._active_workers.clear()