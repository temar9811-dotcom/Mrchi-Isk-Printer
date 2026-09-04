# FILE: app/ui/widgets/trade_panel_ui.py
# VERSION: 1.1.0
import time
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QTreeWidget, QCheckBox,
    QHeaderView, QSplitter, QComboBox, QWidget,
)
from PySide6.QtCore import Qt
from app.state.app_state import AppState
from app.esi.market_service import MarketService
from app.ui.widgets.batch_list_widget import BatchListWidget
from app.ui.widgets.isk_spinbox import IskSpinBox
from app.utils.formatting import fmt_age

STRUCTURE_ID_THRESHOLD = 1_000_000_000
REGIONAL_HUBS = {
    "Jita 4-4": (60003760, 10000002),
    "Amarr": (60008494, 10000043),
    "Dodixie": (60003758, 10000036),
    "Rens": (60002059, 10000042),
    "Hek": (60004471, 10000042),
}
DEFAULT_HUB_LABEL = "Default (Settings)"


class TradePanelUI(QGroupBox):
    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 12, 8, 8)
        main_layout.setSpacing(6)

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
        
        # FIX: Load saved settings into Row 2 widgets
        self._load_haul_boxes()

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
        
        # FIX: Load saved settings into Row 3 widgets
        self._load_hub_boxes()

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

    def _effective_locations(self):
        s = self.app_state.settings
        if self.chk_use_hubs.isChecked():
            buy = REGIONAL_HUBS.get(self.combo_buy_hub.currentText(), (s.trade_buy_station_id or 0, 10000002))
            sell = REGIONAL_HUBS.get(self.combo_sell_hub.currentText(), (s.trade_sell_station_id or 0, 10000002))
            return buy[0], sell[0], buy[1], sell[1]
        return (s.trade_buy_station_id or 0, s.trade_sell_station_id or 0, 10000002, 10000002)

    def _station_fetched_at(self, loc: int):
        if not loc: return None
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