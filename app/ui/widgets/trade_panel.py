# FILE: app/ui/widgets/trade_panel.py
# VERSION: 1.24.0
import logging
from PySide6.QtCore import QTimer
from app.state.app_state import AppState
from app.ui.widgets.trade_panel_ui import TradePanelUI
from app.ui.widgets.trade_panel_market import TradePanelMarket
from app.ui.widgets.trade_panel_actions import TradePanelActions


class TradePanel(TradePanelUI, TradePanelMarket, TradePanelActions):
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