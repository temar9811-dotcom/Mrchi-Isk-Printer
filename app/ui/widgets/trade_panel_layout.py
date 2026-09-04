# FILE: app/ui/widgets/trade_panel_layout.py
# VERSION: 1.0.0
import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget

logger = logging.getLogger("app.ui.widgets.trade_panel_layout")


class ResponsiveLayoutManager:
    """
    Manages responsive layout switching between wide and narrow modes.
    Wide mode: combines rows 1+2 and rows 3+4 side-by-side using QHBoxLayout.
    Narrow mode: 4 separate vertical rows.
    """

    def __init__(self, parent: QWidget, threshold: int = 1200):
        self.parent_widget = parent
        self.threshold = threshold
        self._is_wide = None

        self.stacked_widget = QStackedWidget(parent)
        self.narrow_container = QWidget(parent)
        self.wide_container = QWidget(parent)

    def setup_layouts(self, row_layouts: list) -> None:
        if len(row_layouts) < 4:
            return
        r1, r2, r3, r4 = row_layouts

        # Narrow container: 4 separate vertical rows
        narrow_layout = QVBoxLayout(self.narrow_container)
        narrow_layout.setContentsMargins(0, 0, 0, 0)
        narrow_layout.setSpacing(6)
        narrow_layout.addLayout(r1)
        narrow_layout.addLayout(r2)
        narrow_layout.addLayout(r3)
        narrow_layout.addLayout(r4)

        # Wide container: 2 combined rows (r1+r2 on top, r3+r4 on bottom)
        wide_layout = QVBoxLayout(self.wide_container)
        wide_layout.setContentsMargins(0, 0, 0, 0)
        wide_layout.setSpacing(6)

        c1 = QHBoxLayout()
        c1.setContentsMargins(0, 0, 0, 0)
        c1.addLayout(r1)
        c1.addSpacing(16)
        c1.addLayout(r2)
        wide_layout.addLayout(c1)

        c2 = QHBoxLayout()
        c2.setContentsMargins(0, 0, 0, 0)
        c2.addLayout(r3)
        c2.addSpacing(16)
        c2.addLayout(r4)
        wide_layout.addLayout(c2)

        self.stacked_widget.addWidget(self.narrow_container)  # index 0
        self.stacked_widget.addWidget(self.wide_container)    # index 1

        # Set initial state
        initial_width = self.parent_widget.width() if self.parent_widget else 1200
        self.update_on_resize(initial_width)

    def update_on_resize(self, width: int) -> None:
        if self.threshold <= 0:
            return
        should_be_wide = width >= self.threshold
        if should_be_wide != self._is_wide:
            self._is_wide = should_be_wide
            if should_be_wide:
                self.stacked_widget.setCurrentIndex(1)
                logger.debug("Switched trade panel layout to WIDE mode (width=%d)", width)
            else:
                self.stacked_widget.setCurrentIndex(0)
                logger.debug("Switched trade panel layout to NARROW mode (width=%d)", width)

    def get_active_container(self) -> QWidget:
        if self._is_wide:
            return self.wide_container
        return self.narrow_container


