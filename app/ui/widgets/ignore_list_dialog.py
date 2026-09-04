# FILE: app/ui/widgets/ignore_list_dialog.py
# VERSION: 1.0.0
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
)
from PySide6.QtCore import Qt
from app.state.app_state import AppState
from app.services.ignore_groups import get_ignore_group_names

logger = logging.getLogger("app.ui.widgets.ignore_list_dialog")


class IgnoreListDialog(QDialog):
    """
    Dialog for configuring which predefined ignore groups to exclude from trade calculations.
    """

    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setWindowTitle("Trade Ignore List Groups")
        self.resize(350, 250)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl = QLabel("Select item groups to ignore during trade calculation:")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.checkboxes = {}
        group_names = get_ignore_group_names()
        current_settings = self.app_state.settings.trade_ignore_groups

        for name in group_names:
            chk = QCheckBox(name.title())
            chk.setChecked(current_settings.get(name, False))
            layout.addWidget(chk)
            self.checkboxes[name] = chk

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save & Close")
        btn_save.clicked.connect(self._save_and_close)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _save_and_close(self) -> None:
        s = self.app_state.settings
        if not s.trade_ignore_groups:
            s.trade_ignore_groups = {}
        for name, chk in self.checkboxes.items():
            s.trade_ignore_groups[name] = chk.isChecked()
        self.app_state.save_settings()
        logger.info("Saved trade ignore list groups settings")
        self.accept()
