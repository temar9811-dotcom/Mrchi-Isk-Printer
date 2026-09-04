# FILE: app/ui/widgets/trade_panel_market.py
# VERSION: 1.0.0
from PySide6.QtCore import QTimer
from app.services.market_refresh_service import MarketRefreshService
from app.services.trade_calculator import POPULAR_TRADE_TYPES
from app.services.price_alert_service import PriceAlertService
from app.ui.widgets.price_alerts_dialog import PriceAlertsDialog
from app.ui.widgets.trade_worker import MarketRefreshWorker


class TradePanelMarket:
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

    def open_price_alerts(self) -> None:
        alert_service = PriceAlertService(self.app_state.db)
        alert_service.scan_for_drops(threshold_pct=15.0)
        dlg = PriceAlertsDialog(self.app_state.db, self)
        dlg.exec()

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