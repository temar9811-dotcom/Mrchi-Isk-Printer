# FILE: app/ui/theme.py
# VERSION: 1.1.0


DARK_QSS = """
QWidget {
    background-color: #14171c;
    color: #d7dde6;
    font-size: 13px;
}

QMainWindow::separator {
    background: #1d222b;
    width: 4px;
    height: 4px;
}

QTabWidget::pane {
    border: 1px solid #29313d;
    background: #171b21;
    border-radius: 6px;
}

QTabBar::tab {
    background: #1b2027;
    color: #a9b4c4;
    padding: 8px 16px;
    border: 1px solid #29313d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #233042;
    color: #7ec8ff;
    border-bottom: 2px solid #3da5ff;
}

QTabBar::tab:hover {
    background: #222834;
    color: #e8eef7;
}

QListWidget {
    background: #181d24;
    border: 1px solid #29313d;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background: #264563;
    color: #dff1ff;
}

QListWidget::item:hover {
    background: #232a35;
}

QLabel {
    background: transparent;
}

QMenuBar {
    background: #171b21;
    border-bottom: 1px solid #29313d;
}

QMenuBar::item {
    padding: 6px 10px;
    background: transparent;
}

QMenuBar::item:selected {
    background: #233042;
    color: #7ec8ff;
    border-radius: 4px;
}

QMenu {
    background: #181d24;
    border: 1px solid #29313d;
}

QMenu::item {
    padding: 6px 24px;
}

QMenu::item:selected {
    background: #264563;
    color: #dff1ff;
}

QDockWidget::title {
    background: #1b2027;
    padding: 6px;
    border: 1px solid #29313d;
}

QPlainTextEdit,
QTextEdit,
QLineEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox {
    background: #101317;
    border: 1px solid #29313d;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #264563;
}

QPushButton {
    background: #22303f;
    border: 1px solid #2f4257;
    border-radius: 6px;
    padding: 6px 12px;
    color: #d9e7f6;
}

QPushButton:hover {
    background: #2a3d51;
    border-color: #3da5ff;
}

QPushButton:pressed {
    background: #1d2836;
}

QScrollBar:vertical {
    background: #14171c;
    width: 12px;
}

QScrollBar::handle:vertical {
    background: #2b3441;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #3da5ff;
}

QScrollBar:horizontal {
    background: #14171c;
    height: 12px;
}

QScrollBar::handle:horizontal {
    background: #2b3441;
    border-radius: 5px;
    min-width: 24px;
}

QStatusBar {
    background: #171b21;
    color: #8f9baa;
    border-top: 1px solid #29313d;
}

/* --- Trees and tables (PI colonies, future market tables) --- */

QTreeWidget,
QTreeView,
QTableWidget,
QTableView {
    background: #181d24;
    alternate-background-color: #1e242d;
    color: #d7dde6;
    border: 1px solid #29313d;
    border-radius: 6px;
    padding: 4px;
    gridline-color: #29313d;
    selection-background-color: #264563;
    selection-color: #dff1ff;
}

QTreeWidget::item,
QTableWidget::item {
    padding: 4px;
    border-radius: 2px;
}

QTreeWidget::item:selected,
QTableWidget::item:selected {
    background: #264563;
    color: #dff1ff;
}

QTreeWidget::item:hover,
QTableWidget::item:hover {
    background: #232a35;
}

QHeaderView {
    background: #171b21;
    border: none;
}

QHeaderView::section {
    background: #1b2027;
    color: #a9b4c4;
    padding: 6px;
    border: none;
    border-right: 1px solid #29313d;
    border-bottom: 1px solid #29313d;
    font-weight: bold;
}

QHeaderView::section:hover {
    background: #222834;
    color: #e8eef7;
}

QTreeWidget QToolTip,
QTableWidget QToolTip {
    background: #1b2027;
    color: #d7dde6;
    border: 1px solid #29313d;
}
"""


def apply_dark_theme(app) -> None:
    """
    Apply the global dark theme to the QApplication instance.
    """
    app.setStyleSheet(DARK_QSS)