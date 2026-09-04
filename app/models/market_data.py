# FILE: app/models/market_data.py
# VERSION: 1.0.0

from dataclasses import dataclass


@dataclass
class TypeInfo:
    """
    Cached item type info needed for market and hauling calculations.
    """
    type_id: int
    name: str = ""
    volume: float = 0.0
    market_group_id: int = 0


@dataclass
class MarketOrder:
    """
    One market order (buy or sell).
    """
    order_id: int
    type_id: int
    location_id: int
    is_buy_order: bool
    price: float
    volume_total: int
    volume_remain: int
    min_volume: int = 1
    duration: int = 0
    issued: str = ""


@dataclass
class MarketHistoryRow:
    """
    One day of market history for a type in a region.
    """
    region_id: int
    type_id: int
    date: str
    average: float
    highest: float
    lowest: float
    order_count: int
    volume: float