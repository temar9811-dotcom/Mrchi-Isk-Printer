# FILE: app/ui/widgets/price_alerts_dialog.py
# VERSION: 1.0.0
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt
from app.services.price_alert_service import PriceAlertService

logger = logging.getLogger("app.ui.widgets.price_alerts_dialog")


class PriceAlertsDialog(QDialog):
    """
    Dialog displaying active price drop alerts with options to acknowledge or clear all.
    """

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = PriceAlertService(db)
        self.setWindowTitle("Unexpected Price Drop Alerts")
        self.resize(700, 400)
        self._build_ui()
        self.load_alerts()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl = QLabel("The following items have experienced sudden unexpected price drops (14d vs 90d baseline):")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Type", "Drop %", "Recent Avg", "Baseline Avg", "Detected At"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.tree)

        btn_layout = QHBoxLayout()
        self.btn_ack = QPushButton("Acknowledge Selected")
        self.btn_ack.clicked.connect(self._on_acknowledge)
        btn_layout.addWidget(self.btn_ack)

        self.btn_clear = QPushButton("Clear All Alerts")
        self.btn_clear.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def load_alerts(self) -> None:
        self.tree.clear()
        alerts = self.service.get_active_alerts()
        for a in alerts:
            item = QTreeWidgetItem([
                a.type_name,
                f"-{a.drop_pct:.1f}%",
                f"{a.current_avg:,.2f} ISK",
                f"{a.baseline_avg:,.2f} ISK",
                a.detected_at,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, a.type_id)
            self.tree.addTopLevelItem(item)

    def _on_acknowledge(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an alert to acknowledge.")
            return
        for item in selected:
            tid = item.data(0, Qt.ItemDataRole.UserRole)
            if tid:
                self.service.acknowledge_alert(tid)
        self.load_alerts()

    def _on_clear_all(self) -> None:
        self.service.clear_all_alerts()
        self.load_alerts()
        QMessageBox.information(self, "Cleared", "All active price alerts have been cleared.")
