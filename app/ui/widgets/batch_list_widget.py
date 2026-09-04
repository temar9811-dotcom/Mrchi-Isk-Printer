# FILE: app/ui/widgets/batch_list_widget.py
# VERSION: 1.3.0

import logging

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox, QMenu,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from app.state.app_state import AppState
from app.db.wallet_repository import WalletRepository
from app.db.trade_batch_repository import TradeBatchRepository
from app.db.contract_repository import ContractRepository
from app.db.trade_blacklist_repository import TradeBlacklistRepository
from app.services.batch_tracker import BatchTracker
from app.services.contract_sync_worker import ContractSyncWorker
from app.esi.contract_service import haul_state
from app.models.trade_batch import TradeBatch
from app.utils.formatting import fmt_num

RED = QColor("#e06c75")

OVERRIDE_OPTIONS = ("pending", "buying", "bought", "hauling", "sold", "lost")


class WalletSyncWorker(QThread):
    finished_ok = Signal(list)
    error = Signal(str)

    def __init__(self, tracker: BatchTracker):
        super().__init__()
        self.tracker = tracker
        self.logger = logging.getLogger("app.ui.widgets.wallet_sync_worker")

    def run(self):
        try:
            summary = self.tracker.sync_active()
            self.finished_ok.emit(summary)
        except Exception as exc:
            self.logger.exception("Wallet sync worker failed")
            self.error.emit(str(exc))


class BatchListWidget(QGroupBox):
    """
    Active batches view with wallet/contract sync, haul status,
    manual overrides, blacklist and delete.
    """

    def __init__(self, app_state: AppState, parent=None):
        super().__init__("Active Batches", parent)
        self.app_state = app_state
        self.logger = logging.getLogger("app.ui.widgets.batch_list")
        self._workers = set()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(
            ["Batch / Item", "Qty", "Bought", "Sold",
             "Buy ISK", "Sell ISK", "Haul", "Status"]
        )
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._item_context_menu)
        layout.addWidget(self.tree, 1)

        btn_layout = QHBoxLayout()

        self.btn_sync = QPushButton("Sync Wallets && Update Progress")
        self.btn_sync.clicked.connect(self.start_sync)
        btn_layout.addWidget(self.btn_sync)

        self.btn_contracts = QPushButton("Sync Contracts")
        self.btn_contracts.clicked.connect(self.start_contract_sync)
        btn_layout.addWidget(self.btn_contracts)

        self.btn_delete = QPushButton("Delete Selected Batch")
        self.btn_delete.clicked.connect(self.delete_selected_batch)
        self.btn_delete.setStyleSheet(
            "background-color: #5c2a2a; border-color: #8a3333;"
        )
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #8f9baa;")
        layout.addWidget(self.status_label)

    def _route_haul_state(self) -> str:
        s = self.app_state.settings
        buy_char = s.trade_buy_character_id
        start = s.trade_buy_station_id or 0
        end = s.trade_sell_station_id or 0
        if not (buy_char and start and end):
            return ""
        repo = ContractRepository(self.app_state.db)
        hauls = [
            r for r in repo.get_contracts(contract_type="courier")
            if r.get("issuer_id") == buy_char
            and r.get("start_location_id") == start
            and r.get("end_location_id") == end
        ]
        if not hauls:
            return ""
        hauls.sort(key=lambda r: r.get("date_issued") or "", reverse=True)
        return haul_state(hauls[0].get("status"))

    def refresh(self) -> None:
        self.tree.clear()
        repo = TradeBatchRepository(self.app_state.db)
        haul = self._route_haul_state()

        for batch in repo.get_active_batches():
            haul_text = haul or "-"
            status_text = batch.status.upper()
            if haul == "failed":
                haul_text = "FAILED"
                status_text = "ATTENTION"

            parent = QTreeWidgetItem([
                f"Batch #{batch.batch_id} ({len(batch.items)} items)",
                "", "", "", "", "", haul_text, status_text,
            ])
            parent.setData(0, Qt.ItemDataRole.UserRole, batch)
            if haul == "failed":
                for col in range(8):
                    parent.setForeground(col, RED)

            for item in batch.items:
                shown_status = item.status.upper()
                if item.status_override:
                    shown_status += " (M)"
                child = QTreeWidgetItem([
                    item.type_name,
                    f"{item.quantity:,}",
                    f"{item.bought_qty:,}",
                    f"{item.sold_qty:,}",
                    fmt_num(item.buy_spent),
                    fmt_num(item.sell_received),
                    "",
                    shown_status,
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, item.item_id)
                child.setData(0, Qt.ItemDataRole.UserRole + 1, item.type_id)
                child.setData(0, Qt.ItemDataRole.UserRole + 2, item.type_name)
                if item.status == "lost":
                    for col in range(8):
                        child.setForeground(col, RED)
                parent.addChild(child)

            parent.setExpanded(True)
            self.tree.addTopLevelItem(parent)

    def _item_context_menu(self, pos) -> None:
        node = self.tree.itemAt(pos)
        if node is None or node.parent() is None:
            return
        item_id = node.data(0, Qt.ItemDataRole.UserRole)
        type_id = node.data(0, Qt.ItemDataRole.UserRole + 1)
        type_name = node.data(0, Qt.ItemDataRole.UserRole + 2)
        if item_id is None:
            return

        repo = TradeBatchRepository(self.app_state.db)
        menu = QMenu(self)
        actions = []
        for st in OVERRIDE_OPTIONS:
            act = menu.addAction(f"Override status: {st}")
            act.setData(("override", st))
            actions.append(act)
        clear_act = menu.addAction("Clear manual override")
        clear_act.setData(("override", None))
        actions.append(clear_act)

        menu.addSeparator()
        blacklist_repo = TradeBlacklistRepository(self.app_state.db)
        blacklisted = type_id in blacklist_repo.get_ids()
        if blacklisted:
            bl_act = menu.addAction(f"Remove {type_name} from Blacklist")
            bl_act.setData(("blacklist", False))
        else:
            bl_act = menu.addAction(f"Blacklist {type_name}")
            bl_act.setData(("blacklist", True))
        actions.append(bl_act)

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen not in actions:
            return

        kind, value = chosen.data()
        if kind == "override":
            repo.set_item_override(int(item_id), value)
        else:
            if value:
                blacklist_repo.add(int(type_id), type_name or "")
            else:
                blacklist_repo.remove(int(type_id))
        self.refresh()

    def start_sync(self) -> None:
        self.btn_sync.setEnabled(False)
        self.status_label.setText("Syncing wallets...")

        tracker = BatchTracker(
            self.app_state.db,
            WalletRepository(self.app_state.db),
            TradeBatchRepository(self.app_state.db),
            self.app_state.characters_repo,
            self.app_state.get_esi_client,
            settings=self.app_state.settings,
            contract_repo=ContractRepository(self.app_state.db),
        )

        worker = WalletSyncWorker(tracker)
        worker.finished_ok.connect(lambda s, w=worker: self._on_sync_done(w, s))
        worker.error.connect(lambda m, w=worker: self._on_sync_error(w, m))
        self._workers.add(worker)
        worker.start()

    def start_contract_sync(self) -> None:
        self.btn_contracts.setEnabled(False)
        self.status_label.setText("Syncing contracts...")

        s = self.app_state.settings
        char_ids = [c for c in (s.trade_buy_character_id, s.trade_sell_character_id) if c]
        worker = ContractSyncWorker(self.app_state, char_ids)
        worker.finished_ok.connect(lambda m, w=worker: self._on_contracts_done(w, m))
        worker.error.connect(lambda m, w=worker: self._on_sync_error(w, m))
        self._workers.add(worker)
        worker.start()

    def _on_contracts_done(self, worker, messages: list) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        self.btn_contracts.setEnabled(True)
        self.refresh()
        self.status_label.setText(" | ".join(messages[:3]))

    def _on_sync_done(self, worker, summary: list) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        self.btn_sync.setEnabled(True)
        self.refresh()

        text = " | ".join(summary[:4])
        if len(summary) > 4:
            text += f" (+{len(summary) - 4} more)"
        self.status_label.setText(text)

        for line in summary:
            self.logger.info("Sync: %s", line)

    def _on_sync_error(self, worker, msg: str) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        self.btn_sync.setEnabled(True)
        self.btn_contracts.setEnabled(True)
        self.status_label.setText(f"Sync error: {msg[:60]}")

    def delete_selected_batch(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a batch to delete.")
            return

        root_item = selected[0]
        while root_item.parent():
            root_item = root_item.parent()

        batch = root_item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(batch, TradeBatch):
            return

        reply = QMessageBox.question(
            self, "Delete Batch",
            f"Delete Batch #{batch.batch_id}?\n\nIts items become tradable again.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            repo = TradeBatchRepository(self.app_state.db)
            repo.delete_batch(batch.batch_id)
            self.status_label.setText(f"Batch #{batch.batch_id} deleted.")
            self.refresh()

    def stop_workers(self) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(3000)
        self._workers.clear()