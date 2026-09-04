# FILE: app/ui/settings/fields.py
# VERSION: 1.1.0

import logging
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QLineEdit,
    QWidget,
    QHBoxLayout,
    QPushButton,
)


def create_id_line_edit(parent=None) -> QLineEdit:
    """
    Create a line edit intended for EVE IDs.
    """
    line_edit = QLineEdit(parent)
    line_edit.setMaxLength(20)
    line_edit.setPlaceholderText("EVE ID")

    return line_edit


def set_optional_id(line_edit: QLineEdit, value: Optional[int]) -> None:
    """
    Set an optional integer ID into a QLineEdit.
    """
    if value is None:
        line_edit.setText("")
    else:
        line_edit.setText(str(value))


def get_optional_id(
    line_edit: QLineEdit,
    current_value: Optional[int],
    field_name: str,
    logger: Optional[logging.Logger] = None,
) -> Optional[int]:
    """
    Parse an optional integer ID from a QLineEdit.
    """
    if logger is None:
        logger = logging.getLogger("app.ui.settings.fields")

    text = line_edit.text().strip()

    if not text:
        logger.debug("Field %s cleared", field_name)
        return None

    if not text.isdigit():
        logger.warning(
            "Field %s has invalid ID value '%s'. Keeping previous value.",
            field_name,
            text,
        )
        return current_value

    try:
        value = int(text)
        logger.debug("Field %s parsed value=%s", field_name, value)
        return value
    except ValueError:
        logger.warning(
            "Field %s could not parse '%s'. Keeping previous value.",
            field_name,
            text,
        )
        return current_value


def create_id_row(
    parent,
    line_edit: QLineEdit,
    on_use_station: Optional[Callable[[], None]] = None,
) -> QWidget:
    """
    Create an ID field row with a 'Use Docked Station' button.

    If on_use_station is provided, the button is enabled and wired to
    it. Otherwise the button stays disabled.
    """
    widget = QWidget(parent)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    use_button = QPushButton("Use Docked Station", widget)

    if on_use_station is not None:
        use_button.setEnabled(True)
        use_button.setToolTip(
            "Fetch the station/structure the currently selected "
            "character is docked at."
        )
        use_button.clicked.connect(on_use_station)
    else:
        use_button.setEnabled(False)
        use_button.setToolTip("Not available for this field.")

    layout.addWidget(line_edit, 1)
    layout.addWidget(use_button)

    return widget