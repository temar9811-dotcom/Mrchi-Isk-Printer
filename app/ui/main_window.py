# FILE: app/ui/main_window.py
# VERSION: 2.9.0

import json
import logging
import time

from PySide6.QtCore import Qt, QByteArray, QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QListWidgetItem,
    QDockWidget, QToolBar, QMessageBox, QApplication,
    QDialog, QLabel, QProgressBar,
)

from app import APP_NAME, APP_VERSION
from app.state.app_state import AppState
from app.ui.module_tab import build_module_tab
from app.ui.debug_menu import build_debug_menu
from app.ui.settings.settings_tab import SettingsTab
from app.ui.widgets.log_panel import LogPanel
from app.ui.widgets.pi_panel import PiPanel
from app.ui.widgets.trade_panel import TradePanel
from app.ui.widgets.login_dialog import LoginDialog
from app.ui.widgets.market_browser_widget import MarketBrowserTab
from app.ui.widgets.pnl_history_widget import PnlHistoryWidget

from app.services.market_refresh_service import MarketRefreshService
from app.services.trade_calculator import POPULAR_TRADE_TYPES

WINDOW_GEOMETRY_KEY = "ui.window_geometry"


class StartupLoadWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal()

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.logger = logging.getLogger("app.startup_load")

    def run(self):
        try:
            token = self.app_state.get_primary_token()
            service = MarketRefreshService(
                self.app_state.db,
                self.app_state.get_universe_resolver(),
                token,
            )
            s = self.app_state.settings
            service.preload(
                s.trade_buy_station_id or 0,
                s.trade_sell_station_id or 0,
                list(POPULAR_TRADE_TYPES),
                progress=self.progress.emit,
            )
        except Exception:
            self.logger.exception("Startup preload failed")
        finally:
            self.finished_ok.emit()


class StartupLoadDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Loading market data")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        self.label = QLabel("Checking market cache...")
        self.label.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)


class MainWindow(QMainWindow):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.logger = logging.getLogger("app.main_window")
        self.app_state = app_state
        self.module_tabs = {}
        self.login_dialog = None

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1280, 800)

        self._build_ui()
        self._build_toolbar()
        self._build_menu()
        self._build_log_dock()

        self.app_state.characters_changed.connect(self._refresh_all_character_lists)
        self.app_state.selected_character_changed.connect(self._on_selected_character_changed)
        self.app_state.login_started.connect(self._on_login_started)
        self.app_state.login_finished.connect(self._on_login_finished)

        self._restore_window_geometry()
        self._refresh_all_character_lists()
        self.statusBar().showMessage("Ready")

        # NOTE: startup preload is NOT run here anymore.
        # main.py calls run_startup_load() after the window is visible.

    def run_startup_load(self) -> None:
        self.startup_dialog = StartupLoadDialog(self)
        self.startup_worker = StartupLoadWorker(self.app_state)
        self.startup_worker.progress.connect(self.startup_dialog.label.setText)
        self.startup_worker.finished_ok.connect(self.startup_dialog.accept)
        self.startup_worker.finished.connect(self.startup_worker.deleteLater)
        self.startup_worker.start()
        self.startup_dialog.exec()
        self.startup_dialog.deleteLater()

        self._refresh_after_preload()

    def _refresh_after_preload(self) -> None:
        """
        The panes may have read the cache mid-replacement during the
        preload; give them one clean reload from the fresh cache.
        """
        if hasattr(self, "browser_tab"):
            self.browser_tab.buy_pane.reload()
            self.browser_tab.sell_pane.reload()

        trade_tab = self.module_tabs.get("Market Trade")
        if trade_tab is not None:
            panel = getattr(trade_tab, "detail_panel", None)
            if panel is not None and hasattr(panel, "update_market_age"):
                panel.update_market_age()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        pi_panel = PiPanel(self.app_state)
        pi_tab = build_module_tab(self, "PI", self._on_char_selected, self.app_state, detail_panel=pi_panel)
        self.tabs.addTab(pi_tab, "PI")
        self.module_tabs["PI"] = pi_tab

        trade_panel = TradePanel(self.app_state)
        trade_tab = build_module_tab(self, "Market Trade", self._on_char_selected, self.app_state, detail_panel=trade_panel)
        self.tabs.addTab(trade_tab, "Market Trade")
        self.module_tabs["Market Trade"] = trade_tab

        pnl_widget = PnlHistoryWidget(self.app_state)
        self.tabs.addTab(pnl_widget, "P&L History")

        self.browser_tab = MarketBrowserTab(self.app_state)
        self.tabs.addTab(self.browser_tab, "Market Browser")

        self.settings_tab = SettingsTab(self.app_state)
        self.tabs.addTab(self.settings_tab, "Settings")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction("Add Character (EVE SSO)").triggered.connect(self._start_add_character)

    def _build_menu(self) -> None:
        self.menuBar().addMenu(build_debug_menu(self, self.app_state))

    def _build_log_dock(self) -> None:
        self.log_panel = LogPanel(self)
        self.log_panel.attach_logger(logging.getLogger())
        self.log_dock = QDockWidget("Debug Log", self)
        self.log_dock.setWidget(self.log_panel)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

    def _start_add_character(self) -> None:
        if self.login_dialog is not None:
            return
        self.login_dialog = LoginDialog(self)
        self.login_dialog.cancel_requested.connect(self.app_state.cancel_login_flow)
        self.app_state.login_url_ready.connect(self.login_dialog.set_auth_url)
        self.login_dialog.show()
        self.app_state.start_login_flow()

    def _stop_all_workers(self) -> None:
        self.app_state.cancel_login_flow()

        for tab in self.module_tabs.values():
            for attr in ("info_panel", "detail_panel"):
                panel = getattr(tab, attr, None)
                if panel and hasattr(panel, "stop_workers"):
                    panel.stop_workers()

        if hasattr(self, "browser_tab"):
            self.browser_tab.stop_workers()

        if hasattr(self, "settings_tab"):
            self.settings_tab.stop_workers()

        QApplication.processEvents()
        time.sleep(0.1)

    def _restore_window_geometry(self) -> None:
        raw = self.app_state.settings_repo.get_setting(WINDOW_GEOMETRY_KEY)
        if not raw:
            return
        try:
            data = json.loads(raw)
            geometry_b64 = data.get("geometry_b64", "")
            maximized = bool(data.get("maximized", False))
            if geometry_b64:
                self.restoreGeometry(QByteArray.fromBase64(QByteArray(geometry_b64.encode("ascii"))))
            if maximized:
                self.showMaximized()
        except Exception:
            self.logger.exception("Failed to restore window geometry")

    def _save_window_geometry(self) -> None:
        try:
            geometry_b64 = bytes(self.saveGeometry().toBase64()).decode("ascii")
            payload = json.dumps({"geometry_b64": geometry_b64, "maximized": self.isMaximized()})
            self.app_state.settings_repo.set_setting(WINDOW_GEOMETRY_KEY, payload)
        except Exception:
            self.logger.exception("Failed to save window geometry")

    def closeEvent(self, event) -> None:
        self._stop_all_workers()
        self._save_window_geometry()
        super().closeEvent(event)

    def _refresh_all_character_lists(self) -> None:
        for tab in self.module_tabs.values():
            char_list = tab.char_list
            char_list.blockSignals(True)
            char_list.clear()
            if not self.app_state.characters:
                item = QListWidgetItem("[No characters added yet]")
                item.setData(Qt.ItemDataRole.UserRole, None)
                char_list.addItem(item)
            else:
                for character in self.app_state.characters:
                    item = QListWidgetItem(character.character_name)
                    item.setData(Qt.ItemDataRole.UserRole, character.character_id)
                    char_list.addItem(item)
            char_list.blockSignals(False)

    def _on_char_selected(self, module_name: str, current) -> None:
        if current is None:
            return
        character_id = current.data(Qt.ItemDataRole.UserRole)
        if character_id is None:
            self.app_state.set_selected_character(None)
            return
        self.app_state.select_character_by_id(character_id)

    def _on_selected_character_changed(self, character) -> None:
        status_text = f"Selected: {character.character_name}" if character else "No character selected"
        self.statusBar().showMessage(status_text)

    def _on_tab_changed(self, index: int) -> None:
        self.logger.debug("Tab changed: %s", self.tabs.tabText(index))

    def _on_login_started(self) -> None:
        self.statusBar().showMessage("Waiting for EVE SSO login...")

    def _on_login_finished(self, char_name: str, message: str) -> None:
        if self.login_dialog is not None:
            self.login_dialog.mark_finished()
            self.login_dialog.close()
            self.login_dialog.deleteLater()
            self.login_dialog = None

        self.statusBar().showMessage(message, 5000)
        if char_name:
            QMessageBox.information(self, "Login Successful", f"Added: {char_name}")
        elif "cancelled" in message.lower():
            self.logger.info("Login flow cancelled by user")
        else:
            QMessageBox.critical(self, "Login Failed", message)