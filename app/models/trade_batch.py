# FILE: app/models/trade_batch.py
# VERSION: 1.10.0
from dataclasses import dataclass, field
from typing import List

@dataclass
class TradeSuggestion:
    type_id: int
    type_name: str
    volume_per_unit: float
    buy_price: float
    sell_price: float
    quantity: int
    est_sellable: int
    total_volume: float
    buy_cost: float
    sell_revenue: float
    hauling_cost: float
    tax_cost: float
    net_profit: float
    profit_per_m3: float
    sell_mode: str = "placed"  # "placed" or "instant"
    shift_ratio: float = 1.0

@dataclass
class TradeBatchRecommendation:
    batch_name: str = "Recommended Batch"
    total_volume: float = 0.0
    total_profit: float = 0.0
    total_buy: float = 0.0
    items: List[TradeSuggestion] = field(default_factory=list)

@dataclass
class TradeBatchItem:
    item_id: int = 0
    batch_id: int = 0
    type_id: int = 0
    type_name: str = ""
    quantity: int = 0
    buy_price: float = 0.0
    sell_price: float = 0.0
    status: str = "pending"
    bought_qty: int = 0
    sold_qty: int = 0
    buy_spent: float = 0.0
    sell_received: float = 0.0
    status_override: str = ""
    sell_mode: str = "placed"  # "placed" or "instant"
    sold_at: str = ""
    time_to_sell_days: float = 0.0

@dataclass
class TradeBatch:
    batch_id: int = 0
    buy_char_id: int = 0
    sell_char_id: int = 0
    status: str = "active"
    created_at: str = ""
    completed_at: str = ""
    expected_profit: float = 0.0
    actual_profit: float = 0.0
    notes: str = ""
    haul_state: str = ""
    items: List[TradeBatchItem] = field(default_factory=list)

@dataclass
class PiBatchSuggestion:
    planet_name: str
    action: str
    estimated_value: float = 0.0
    estimated_volume: float = 0.0
    details: str = ""
