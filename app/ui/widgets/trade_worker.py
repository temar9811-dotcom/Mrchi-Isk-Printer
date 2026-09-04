# FILE: app/ui/widgets/trade_worker.py
# VERSION: 1.1.0

import logging

from PySide6.QtCore import QThread, Signal

from app.services.trade_calculator import TradeCalculator


class TradeWorker(QThread):
    """
    Runs the heavy trade calculation in the background.
    """
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, calculator: TradeCalculator, params: dict):
        super().__init__()
        self.calculator = calculator
        self.params = params
        self.logger = logging.getLogger("app.ui.widgets.trade_worker")

    def run(self):
        try:
            self.logger.info("Starting trade calculation...")
            results = self.calculator.calculate(**self.params)
            self.logger.info("Calculation complete. Found %s trades.", len(results))
            self.finished.emit(results)
        except Exception as exc:
            self.logger.exception("Trade calculation failed")
            self.error.emit(str(exc))


class MarketRefreshWorker(QThread):
    """
    Force-pulls trade-relevant market data (books + histories) into the DB.
    """
    progress = Signal(str)
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, service, buy_loc: int, sell_loc: int, popular: list):
        super().__init__()
        self.service = service
        self.buy_loc = buy_loc
        self.sell_loc = sell_loc
        self.popular = popular
        self.logger = logging.getLogger("app.ui.widgets.market_refresh_worker")

    def run(self):
        try:
            self.service.refresh_trade_data(
                self.buy_loc, self.sell_loc, self.popular, self.progress.emit
            )
            self.finished_ok.emit()
        except Exception as exc:
            self.logger.exception("Market refresh failed")
            self.error.emit(str(exc))