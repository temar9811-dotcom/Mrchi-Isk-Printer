# FILE: app/ui/settings/hauling_page.py
# VERSION: 1.1.0

import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
)

from app.state.app_state import AppState


class HaulingSettingsPage(QWidget):
    """
    JF service hauling cost defaults (market trade only).
    """

    def __init__(self, app_state: AppState):
        super().__init__()

        self.logger = logging.getLogger("app.ui.settings.hauling_page")
        self.app_state = app_state

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self.per_m3 = QDoubleSpinBox(self)
        self.per_m3.setRange(0.0, 100_000.0)
        self.per_m3.setDecimals(2)
        self.per_m3.setSingleStep(10.0)
        self.per_m3.setSuffix(" ISK/m3")

        self.min_charge = QDoubleSpinBox(self)
        self.min_charge.setRange(0.0, 10_000_000_000.0)
        self.min_charge.setDecimals(0)
        self.min_charge.setSingleStep(1_000_000.0)
        self.min_charge.setSuffix(" ISK")

        self.full_load_charge = QDoubleSpinBox(self)
        self.full_load_charge.setRange(0.0, 10_000_000_000.0)
        self.full_load_charge.setDecimals(0)
        self.full_load_charge.setSingleStep(1_000_000.0)
        self.full_load_charge.setSuffix(" ISK")

        self.jf_capacity = QSpinBox(self)
        self.jf_capacity.setMinimum(0)
        self.jf_capacity.setMaximum(10_000_000)
        self.jf_capacity.setSingleStep(1000)
        self.jf_capacity.setSuffix(" m3")

        form.addRow("Cost per m3", self.per_m3)
        form.addRow("Minimum load charge", self.min_charge)
        form.addRow("Full load charge", self.full_load_charge)
        form.addRow("JF capacity", self.jf_capacity)

        layout.addLayout(form)
        layout.addStretch()

    def load_settings(self) -> None:
        settings = self.app_state.settings

        self.per_m3.setValue(settings.haul_per_m3_isk)
        self.min_charge.setValue(settings.haul_min_charge_isk)
        self.full_load_charge.setValue(settings.haul_full_load_charge_isk)
        self.jf_capacity.setValue(settings.haul_jf_capacity_m3)

        self.logger.debug("Hauling settings loaded into UI")

    def apply_to_settings(self) -> None:
        settings = self.app_state.settings

        settings.haul_per_m3_isk = self.per_m3.value()
        settings.haul_min_charge_isk = self.min_charge.value()
        settings.haul_full_load_charge_isk = self.full_load_charge.value()
        settings.haul_jf_capacity_m3 = self.jf_capacity.value()

        self.logger.debug("Hauling settings applied")