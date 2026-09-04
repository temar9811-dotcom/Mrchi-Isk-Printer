# FILE: app/services/trade_shift.py
# VERSION: 1.0.0
from typing import List

SHIFT_MIN = 0.5
SHIFT_MAX = 2.0


def calculate_shift_ratio(history: List) -> float:
    """
    Calculate a shift ratio comparing recent price action (14d) to longer-term baseline (90d).
    Returns a clamped float between 0.5 and 2.0:
    - > 1.0 : buy pressure (prices rising)
    - < 1.0 : sell pressure (prices falling)
    - == 1.0 : neutral / insufficient data
    """
    if not history:
        return 1.0
    rows = sorted(history, key=lambda r: r.date, reverse=True)
    window_14 = rows[:14]
    window_90 = rows[:90]
    if not window_14 or not window_90:
        return 1.0
    recent_avg = sum(r.average for r in window_14) / len(window_14)
    longterm_avg = sum(r.average for r in window_90) / len(window_90)
    if longterm_avg <= 0:
        return 1.0
    ratio = recent_avg / longterm_avg
    return max(SHIFT_MIN, min(SHIFT_MAX, ratio))
