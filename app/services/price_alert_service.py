# FILE: app/services/price_alert_service.py
# VERSION: 1.0.0
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any
from app.db.database import Database

logger = logging.getLogger("app.services.price_alert_service")


@dataclass
class PriceAlert:
    type_id: int
    type_name: str
    drop_pct: float
    current_avg: float
    baseline_avg: float
    detected_at: str
    active: int = 1


class PriceAlertService:
    """
    Detects sudden unexpected price drops by comparing recent price action (14d)
    against longer-term baseline (90d), and manages alert persistence.
    """

    def __init__(self, db: Database):
        self.db = db

    def scan_for_drops(self, threshold_pct: float = 15.0) -> List[PriceAlert]:
        """
        Scans market_history_cache for all types with history data.
        Compares 14d avg vs 90d avg. If (90d_avg - 14d_avg) / 90d_avg > threshold_pct,
        records or updates an alert in price_alerts table and returns the list of active alerts.
        """
        try:
            # Query all history grouped by type_id
            rows = self.db.query(
                """
                SELECT h.region_id, h.type_id, h.date, h.average, t.name as type_name
                FROM market_history_cache h
                LEFT JOIN types_cache t ON h.type_id = t.type_id
                ORDER BY h.type_id, h.date DESC
                """
            )
            if not rows:
                return []

            grouped = {}
            names = {}
            for r in rows:
                tid = r["type_id"]
                if r["type_name"]:
                    names[tid] = r["type_name"]
                grouped.setdefault(tid, []).append(r)

            detected = []
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            for tid, history_rows in grouped.items():
                # sorted desc by date
                sorted_rows = sorted(history_rows, key=lambda x: x["date"], reverse=True)
                window_14 = sorted_rows[:14]
                window_90 = sorted_rows[:90]

                if not window_14 or not window_90 or len(window_90) < 5:
                    continue

                recent_avg = sum(r["average"] for r in window_14) / len(window_14)
                baseline_avg = sum(r["average"] for r in window_90) / len(window_90)

                if baseline_avg <= 0:
                    continue

                drop_pct = ((baseline_avg - recent_avg) / baseline_avg) * 100.0
                if drop_pct >= threshold_pct:
                    t_name = names.get(tid, f"Type #{tid}")
                    alert = PriceAlert(
                        type_id=tid,
                        type_name=t_name,
                        drop_pct=drop_pct,
                        current_avg=recent_avg,
                        baseline_avg=baseline_avg,
                        detected_at=now_str,
                        active=1,
                    )
                    detected.append(alert)
                    # Upsert into price_alerts
                    self.db.execute(
                        """
                        INSERT INTO price_alerts (
                            type_id, type_name, drop_pct, current_avg, baseline_avg, detected_at, active
                        ) VALUES (?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(type_id) DO UPDATE SET
                            type_name=excluded.type_name,
                            drop_pct=excluded.drop_pct,
                            current_avg=excluded.current_avg,
                            baseline_avg=excluded.baseline_avg,
                            detected_at=excluded.detected_at,
                            active=1
                        """,
                        (tid, t_name, drop_pct, recent_avg, baseline_avg, now_str),
                    )

            logger.info("Scanned price alerts: detected %s drops >= %.1f%%", len(detected), threshold_pct)
            return self.get_active_alerts()
        except Exception as exc:
            logger.exception("Failed to scan for price drops: %s", exc)
            return self.get_active_alerts()

    def get_active_alerts(self) -> List[PriceAlert]:
        try:
            rows = self.db.query(
                """
                SELECT type_id, type_name, drop_pct, current_avg, baseline_avg, detected_at, active
                FROM price_alerts
                WHERE active = 1
                ORDER BY drop_pct DESC
                """
            )
            alerts = []
            for r in rows:
                alerts.append(PriceAlert(
                    type_id=r["type_id"],
                    type_name=r["type_name"] or f"Type #{r['type_id']}",
                    drop_pct=r["drop_pct"],
                    current_avg=r["current_avg"],
                    baseline_avg=r["baseline_avg"],
                    detected_at=r["detected_at"],
                    active=r["active"],
                ))
            return alerts
        except Exception as exc:
            logger.warning("Failed to get active price alerts: %s", exc)
            return []

    def acknowledge_alert(self, type_id: int) -> None:
        try:
            self.db.execute(
                "UPDATE price_alerts SET active = 0 WHERE type_id = ?",
                (type_id,),
            )
            logger.info("Acknowledged price alert for type_id %s", type_id)
        except Exception as exc:
            logger.warning("Failed to acknowledge price alert for %s: %s", type_id, exc)

    def clear_all_alerts(self) -> None:
        try:
            self.db.execute("UPDATE price_alerts SET active = 0")
            logger.info("Cleared all active price alerts")
        except Exception as exc:
            logger.warning("Failed to clear all price alerts: %s", exc)
