# FILE: app/ui/widgets/pnl_history_widget.py
# VERSION: 1.0.0
import logging
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QWidget
)
from PySide6.QtCore import Qt
from app.state.app_state import AppState
from app.db.trade_batch_repository import TradeBatchRepository
from app.utils.formatting import fmt_num

logger = logging.getLogger("app.ui.widgets.pnl_history_widget")


class PnlHistoryWidget(QGroupBox):
    """
    Displays historical P&L data for completed trade batches along with summary statistics.
    """

    def __init__(self, app_state: AppState, parent=None):
        super().__init__("P&L History & Profit Trends", parent)
        self.app_state = app_state
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        # Summary panel
        summary_box = QWidget(self)
        sum_layout = QHBoxLayout(summary_box)
        sum_layout.setContentsMargins(4, 4, 4, 4)

        self.lbl_total_batches = QLabel("Total Batches: 0")
        self.lbl_total_expected = QLabel("Expected: 0 ISK")
        self.lbl_total_actual = QLabel("Actual: 0 ISK")
        self.lbl_avg_profit = QLabel("Avg Profit: 0 ISK")
        self.lbl_success_rate = QLabel("Success Rate: 0.0%")

        for lbl in (
            self.lbl_total_batches, self.lbl_total_expected,
            self.lbl_total_actual, self.lbl_avg_profit, self.lbl_success_rate
        ):
            lbl.setStyleSheet("font-weight: bold; color: #d0d0d0;")
            sum_layout.addWidget(lbl)

        sum_layout.addStretch()
        self.btn_refresh = QPushButton("Refresh P&L")
        self.btn_refresh.clicked.connect(self.refresh)
        sum_layout.addWidget(self.btn_refresh)

        layout.addWidget(summary_box)

        # Tree widget
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([
            "Batch ID", "Completed Date", "Items", "Expected Profit",
            "Actual Profit", "Variance", "Status"
        ])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.tree, 1)

    def refresh(self) -> None:
        self.tree.clear()
        try:
            repo = TradeBatchRepository(self.app_state.db)
            summary = repo.get_pnl_summary()
            completed = repo.get_completed_batches(limit=100)

            self.lbl_total_batches.setText(f"Total Batches: {summary['total_batches']}")
            self.lbl_total_expected.setText(f"Expected: {fmt_num(summary['total_expected'])} ISK")
            self.lbl_total_actual.setText(f"Actual: {fmt_num(summary['total_actual'])} ISK")
            self.lbl_avg_profit.setText(f"Avg Profit: {fmt_num(summary['avg_profit'])} ISK")
            self.lbl_success_rate.setText(f"Success Rate: {summary['success_rate']:.1f}%")

            for batch in completed:
                variance = batch.actual_profit - batch.expected_profit
                item_count = len(batch.items)
                
                item = QTreeWidgetItem([
                    f"#{batch.batch_id}",
                    batch.completed_at or batch.created_at,
                    str(item_count),
                    f"{fmt_num(batch.expected_profit)} ISK",
                    f"{fmt_num(batch.actual_profit)} ISK",
                    f"{fmt_num(variance)} ISK",
                    batch.status.capitalize(),
                ])
                
                # Color coding actual profit / variance
                if batch.actual_profit > 0:
                    item.setForeground(4, Qt.GlobalColor.green)
                else:
                    item.setForeground(4, Qt.GlobalColor.red)

                if variance >= 0:
                    item.setForeground(5, Qt.GlobalColor.green)
                else:
                    item.setForeground(5, Qt.GlobalColor.red)

                self.tree.addTopLevelItem(item)
        except Exception as exc:
            logger.exception("Failed to load P&L history")
