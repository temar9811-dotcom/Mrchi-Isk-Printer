# FILE: app/ui/widgets/blacklist_dialog.py
# VERSION: 1.0.0

import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QLabel,
)
from PySide6.QtCore import Qt

from app.db.database import Database
from app.db.trade_blacklist_repository import TradeBlacklistRepository


class BlacklistDialog(QDialog):
    """
    Manage the trade blacklist: view and remove blocked items.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("app.ui.widgets.blacklist_dialog")
        self.repo = TradeBlacklistRepository(db)

        self.setWindowTitle("Trade Blacklist")
        self.setModal(False)
        self.setMinimumSize(480, 380)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Blacklisted items are never suggested by the trade "
            "calculator. They still appear in the Market Browser.",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8f9baa;")
        layout.addWidget(hint)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Type", "Added"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.tree, 1)

        btn_layout = QHBoxLayout()
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.btn_remove)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        entries = self.repo.get_all()
        for e in entries:
            self.tree.addTopLevelItem(QTreeWidgetItem([
                e["type_name"], (e["added_at"] or "")[:19],
            ]))
            self.tree.topLevelItem(
                self.tree.topLevelItemCount() - 1
            ).setData(0, Qt.ItemDataRole.UserRole, e["type_id"])
        self.logger.debug("Blacklist dialog shows %s items", len(entries))

    def remove_selected(self) -> None:
        for item in self.tree.selectedItems():
            type_id = item.data(0, Qt.ItemDataRole.UserRole)
            if type_id is not None:
                self.repo.remove(int(type_id))
        self.refresh()