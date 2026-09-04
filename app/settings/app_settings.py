# FILE: app/settings/app_settings.py
# VERSION: 1.6.0
import logging
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, Optional, Set

SETTINGS_JSON_KEY = "app_settings"
logger = logging.getLogger("app.settings.model")


@dataclass
class AppSettings:
    """
    Global application settings.
    """
    # General
    debug_mode: bool = True
    primary_character_id: Optional[int] = None

    # PI module defaults
    pi_cycle_days: int = 30
    pi_search_range_jumps: int = 5
    pi_price_mode: str = "sell"
    pi_include_raw_extractor_pi: bool = False
    pi_home_station_id: Optional[int] = None
    pi_market_station_id: Optional[int] = None

    # Market trade module defaults
    trade_cycle_days: int = 30
    trade_item_limit: int = 20
    trade_full_load_m3: int = 320_000
    trade_buy_character_id: Optional[int] = None
    trade_sell_character_id: Optional[int] = None
    trade_buy_station_id: Optional[int] = None
    trade_sell_station_id: Optional[int] = None
    trade_budget_isk: float = 0.0
    trade_use_wallet: bool = False
    trade_market_share_pct: float = 5.0
    trade_use_hubs: bool = False
    trade_buy_hub: str = "default"
    trade_sell_hub: str = "default"
    trade_auto_refresh_minutes: int = 20  # 0 = disabled
    trade_layout_width_threshold: int = 1200  # 0 = disabled
    trade_exclude_active_batches: bool = True
    trade_max_merge_attempts: int = 0  # 0 = unlimited
    trade_ignore_groups: Dict[str, bool] = field(default_factory=dict)

    # Citadel tax defaults (ESI cannot read player-set rates)
    citadel_sales_tax_pct: float = 2.0
    citadel_broker_fee_pct: float = 3.0

    # JF service hauling costs (market trade only; PI hauls separately)
    haul_per_m3_isk: float = 1000.0
    haul_min_charge_isk: float = 10_000_000.0
    haul_full_load_charge_isk: float = 300_000_000.0
    haul_jf_capacity_m3: int = 320_000

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppSettings":
        valid_names = {field.name for field in fields(cls)}
        clean_data: Dict[str, Any] = {}
        for key, value in data.items():
            if key in valid_names:
                clean_data[key] = value
            else:
                logger.debug("Ignoring unknown settings key: %s", key)
        try:
            return cls(**clean_data)
        except TypeError:
            logger.exception(
                "Failed to construct AppSettings from saved data. "
                "Falling back to default settings."
            )
            return cls()