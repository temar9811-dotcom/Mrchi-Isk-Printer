# FILE: app/ui/widgets/isk_spinbox.py
# VERSION: 1.0.0

from PySide6.QtWidgets import QDoubleSpinBox

from app.utils.formatting import fmt_num

MULTIPLIERS = {
    "t": 1_000,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
}


class IskSpinBox(QDoubleSpinBox):
    """
    A QDoubleSpinBox that displays ISK amounts with t/M/B suffixes
    and parses typed suffixes back into raw values.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0.0, 10_000_000_000_000.0)
        self.setDecimals(2)
        self.setSingleStep(1_000_000.0)

    def textFromValue(self, value: float) -> str:
        return fmt_num(value)

    def valueFromText(self, text: str) -> float:
        cleaned = text.strip().replace(",", "").replace(" ", "")
        if not cleaned:
            return 0.0

        suffix = cleaned[-1].lower()
        if suffix in MULTIPLIERS:
            try:
                base = float(cleaned[:-1])
            except ValueError:
                return 0.0
            return base * MULTIPLIERS[suffix]

        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def validate(self, text: str, pos: int):
        # Allow free typing of suffixes; final parse happens on focus-out
        from PySide6.QtGui import QValidator
        return QValidator.State.Acceptable, text, pos