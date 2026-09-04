# FILE: app/ui/widgets/trade_panel_calc.py
# VERSION: 1.1.0
import logging
from typing import List, Set
from app.models.trade_batch import TradeBatchRecommendation, TradeSuggestion
from app.db.trade_batch_repository import TradeBatchRepository
from app.db.wallet_repository import WalletRepository

logger = logging.getLogger("app.ui.widgets.trade_panel_calc")


def get_active_batch_exclusions(
    db, buy_char_id: int, sell_char_id: int
) -> Set[int]:
    """
    Get type_ids from active batches that haven't been fully bought/sold.
    """
    repo = TradeBatchRepository(db)
    wallet_repo = WalletRepository(db)
    active_batches = repo.get_active_batches()
    
    exclusions = set()
    for batch in active_batches:
        # Only check batches for the same buy/sell characters
        if batch.buy_char_id != buy_char_id or batch.sell_char_id != sell_char_id:
            continue
        
        for item in batch.items:
            # Check if item is fully completed
            if item.bought_qty >= item.quantity and item.sold_qty >= item.quantity:
                continue
            
            # Check wallet to see if actually bought/sold
            if buy_char_id:
                bought_qty, _ = wallet_repo.sums(
                    buy_char_id, item.type_id, is_buy=True, since=batch.created_at
                )
                if bought_qty < item.quantity:
                    exclusions.add(item.type_id)
                    continue
            
            if sell_char_id:
                sold_qty, _ = wallet_repo.sums(
                    sell_char_id, item.type_id, is_buy=False, since=batch.created_at
                )
                if sold_qty < item.quantity:
                    exclusions.add(item.type_id)
    
    logger.debug("Excluding %d type_ids from active batches", len(exclusions))
    return exclusions


def group_into_batches_smart(
    suggestions: List[TradeSuggestion],
    max_batches: int,
    capacity: float,
    budget: float,
    max_merge_attempts: int = 0,
) -> List[TradeBatchRecommendation]:
    """
    Bin-packing algorithm to maximize batch utilization.
    Tries to fit items into existing batches before creating new ones.
    """
    # Sort by profit/m3 descending
    sorted_suggestions = sorted(
        suggestions, key=lambda s: s.profit_per_m3, reverse=True
    )
    
    batches: List[TradeBatchRecommendation] = []
    
    # First pass: try to fit each item into existing batches
    for suggestion in sorted_suggestions:
        placed = False
        
        # Try to fit into existing batch
        for batch in batches:
            would_exceed_volume = batch.total_volume + suggestion.total_volume > capacity
            would_exceed_budget = budget > 0 and batch.total_buy + suggestion.buy_cost > budget
            
            if not would_exceed_volume and not would_exceed_budget:
                batch.items.append(suggestion)
                batch.total_volume += suggestion.total_volume
                batch.total_profit += suggestion.net_profit
                batch.total_buy += suggestion.buy_cost
                placed = True
                break
        
        # If couldn't fit, create new batch
        if not placed and len(batches) < max_batches:
            new_batch = TradeBatchRecommendation(
                batch_name=f"Recommended Batch {len(batches) + 1}"
            )
            new_batch.items.append(suggestion)
            new_batch.total_volume = suggestion.total_volume
            new_batch.total_profit = suggestion.net_profit
            new_batch.total_buy = suggestion.buy_cost
            batches.append(new_batch)
    
    # Second pass: try to merge small batches
    if max_merge_attempts > 0:
        attempts = 0
        i = 0
        while i < len(batches) and attempts < max_merge_attempts:
            merged = False
            for j in range(i + 1, len(batches)):
                combined_volume = batches[i].total_volume + batches[j].total_volume
                combined_budget = batches[i].total_buy + batches[j].total_buy
                
                if combined_volume <= capacity and (budget <= 0 or combined_budget <= budget):
                    # Merge batch j into batch i
                    batches[i].items.extend(batches[j].items)
                    batches[i].total_volume = combined_volume
                    batches[i].total_profit += batches[j].total_profit
                    batches[i].total_buy = combined_budget
                    batches.pop(j)
                    merged = True
                    attempts += 1
                    break
            
            if not merged:
                i += 1
    
    return batches