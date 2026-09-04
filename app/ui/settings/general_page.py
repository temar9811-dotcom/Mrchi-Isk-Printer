# FILE: app/ui/settings/general_page.py
# VERSION: 1.2.0
import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QCheckBox,
    QComboBox,
    QLabel,
)
from app.state.app_state import AppState


class GeneralSettingsPage(QWidget):
    """
    General settings page.
    """

    def __init__(self, app_state: AppState):
        super().__init__()
        self.logger = logging.getLogger("app.ui.settings.general_page")
        self.app_state = app_state
        self._build_ui()
        # Repopulate the primary-char combo once characters finish loading
        # (the page is constructed before load_characters() runs at startup).
        self.app_state.characters_changed.connect(self._on_characters_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self.chk_debug = QCheckBox("Enable debug mode", self)
        form.addRow(self.chk_debug)

        self.primary_combo = QComboBox(self)
        form.addRow("Primary ESI character", self.primary_combo)

        hint = QLabel(
            "The primary character is used for shared ESI pulls "
            "(market books, station names, structure lookups).",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8f9baa;")
        form.addRow(hint)

        layout.addLayout(form)
        layout.addStretch()

    def _on_characters_changed(self) -> None:
        # Characters loaded (or reloaded) - refresh the combo without
        # disturbing the debug checkbox state.
        self.logger.debug("characters_changed received, repopulating combo")
        self._populate_primary_combo()

    def _populate_primary_combo(self) -> None:
        current_id = self.primary_combo.currentData()
        self.primary_combo.blockSignals(True)
        self.primary_combo.clear()
        self.primary_combo.addItem("[None]", None)
        for char in self.app_state.characters:
            self.primary_combo.addItem(char.character_name, char.character_id)
        # Restore previous selection if still present, else fall back to
        # the saved primary_character_id from settings.
        idx = -1
        if current_id is not None:
            idx = self.primary_combo.findData(current_id)
        if idx < 0:
            idx = self.primary_combo.findData(
                self.app_state.settings.primary_character_id
            )
        self.primary_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.primary_combo.blockSignals(False)

    def load_settings(self) -> None:
        settings = self.app_state.settings
        self.chk_debug.setChecked(settings.debug_mode)
        self._populate_primary_combo()
        self.logger.debug("General settings loaded into UI")

    def apply_to_settings(self) -> None:
        settings = self.app_state.settings
        settings.debug_mode = self.chk_debug.isChecked()
        settings.primary_character_id = self.primary_combo.currentData()
        self.logger.debug("General settings applied")