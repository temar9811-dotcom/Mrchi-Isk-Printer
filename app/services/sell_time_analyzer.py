# FILE: app/services/sell_time_analyzer.py
# VERSION: 1.0.0
import logging
from typing import Dict, Any
from app.db.database import Database

logger = logging.getLogger("app.services.sell_time_analyzer")


class SellTimeAnalyzer:
    """
    Analyzes historical sell times for completed batch items to inform trade calculators.
    """

    def __init__(self, db: Database):
        self.db = db

    def get_sell_time_stats(self) -> Dict[int, Dict[str, Any]]:
        """
        Query all completed batch items where time_to_sell_days is not null.
        Group by type_id and calculate:
        - avg_time_to_sell: mean of time_to_sell_days
        - median_time_to_sell: median of time_to_sell_days (or approximation)
        - sample_count: number of completed sales for this type
        Only include types with at least 3 samples for statistical relevance.
        Returns dict mapping type_id -> {avg_time_to_sell, median_time_to_sell, sample_count}.
        """
        try:
            rows = self.db.query(
                """
                SELECT type_id, time_to_sell_days
                FROM trade_batch_items
                WHERE time_to_sell_days IS NOT NULL AND status = 'sold'
                """
            )
            if not rows:
                return {}

            grouped = {}
            for r in rows:
                tid = r["type_id"]
                val = r["time_to_sell_days"]
                if val is not None:
                    grouped.setdefault(tid, []).append(float(val))

            stats = {}
            for tid, vals in grouped.items():
                if len(vals) >= 3:
                    sorted_vals = sorted(vals)
                    count = len(sorted_vals)
                    avg = sum(sorted_vals) / count
                    if count % 2 == 1:
                        median = sorted_vals[count // 2]
                    else:
                        median = (sorted_vals[(count // 2) - 1] + sorted_vals[count // 2]) / 2.0
                    stats[tid] = {
                        "avg_time_to_sell": avg,
                        "median_time_to_sell": median,
                        "sample_count": count,
                    }
            return stats
        except Exception as exc:
            logger.warning("Failed to analyze sell times: %s", exc)
            return {}
