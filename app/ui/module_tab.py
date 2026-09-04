# FILE: app/ui/module_tab.py
# VERSION: 1.2.0

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QListWidget,
    QLabel,
)

from app.state.app_state import AppState
from app.ui.widgets.character_info_panel import CharacterInfoPanel


def build_module_tab(
    owner,
    module_name: str,
    on_char_selected,
    app_state: AppState,
    detail_panel: Optional[QWidget] = None,
) -> QWidget:
    """
    Build a module tab shell.

    Left: Character list.
    Right: CharacterInfoPanel (top) + detail_panel or placeholder (bottom).
    """
    logger = logging.getLogger("app.ui.module_tab")

    widget = QWidget(owner)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)

    splitter = QSplitter(Qt.Orientation.Horizontal, widget)

    left = QWidget(splitter)
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(4)

    left_title = QLabel("Characters", left)
    left_title.setStyleSheet("font-weight: bold; color: #7ec8ff; margin: 4px;")

    char_list = QListWidget(left)
    char_list.setObjectName(
        f"char_list_{module_name.lower().replace(' ', '_')}"
    )
    char_list.currentItemChanged.connect(
        lambda current, previous, name=module_name: on_char_selected(name, current)
    )

    left_layout.addWidget(left_title)
    left_layout.addWidget(char_list)

    right = QWidget(splitter)
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(8, 0, 0, 0)
    right_layout.setSpacing(8)

    info_panel = CharacterInfoPanel(app_state, right)
    right_layout.addWidget(info_panel)

    if detail_panel is not None:
        right_layout.addWidget(detail_panel, 1)
    else:
        info_title = QLabel(f"{module_name} details", right)
        info_title.setStyleSheet("font-weight: bold; color: #9cf29c; margin-top: 8px;")
        info_body = QLabel("Module specific content will appear here.", right)
        info_body.setWordWrap(True)
        info_body.setTextFormat(Qt.TextFormat.RichText)
        right_layout.addWidget(info_title)
        right_layout.addWidget(info_body)
        right_layout.addStretch()

    splitter.addWidget(left)
    splitter.addWidget(right)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 3)
    splitter.setSizes([280, 900])

    layout.addWidget(splitter)

    widget.char_list = char_list
    widget.info_panel = info_panel
    widget.detail_panel = detail_panel

    logger.debug("Built module tab: %s", module_name)
    return widget