# FILE: app/ui/widgets/trade_panel_actions.py
# VERSION: 1.0.0
from PySide6.QtWidgets import QMessageBox, QMenu
from PySide6.QtCore import Qt
from app.services.trade_calculator import TradeCalculator
from app.services.tax_service import TaxService
from app.esi.market_service import MarketService
from app.db.trade_batch_repository import TradeBatchRepository
from app.db.trade_blacklist_repository import TradeBlacklistRepository
from app.models.trade_batch import TradeBatch, TradeBatchItem, TradeBatchRecommendation, TradeSuggestion
from app.ui.widgets.trade_worker import TradeWorker
from app.ui.widgets.blacklist_dialog import BlacklistDialog
from app.ui.widgets.trade_panel_calc import get_active_batch_exclusions, group_into_batches_smart
from app.services.ignore_groups import get_ignore_group_names, get_type_ids_for_groups, add_type_to_group
from app.ui.widgets.ignore_list_dialog import IgnoreListDialog


class TradePanelActions:
    def open_blacklist(self) -> None:
        dialog = BlacklistDialog(self.app_state.db, self)
        dialog.exec()
        dialog.deleteLater()

    def open_ignore_list(self) -> None:
        dialog = IgnoreListDialog(self.app_state, self)
        if dialog.exec():
            self.start_calculation()
        dialog.deleteLater()

    def _add_to_ignore_group(self, type_id: int, group_name: str) -> None:
        add_type_to_group(type_id, group_name)
        self.status_label.setText(f"Added type {type_id} to '{group_name}' ignore group.")

    def _tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None: return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, TradeSuggestion): return
        
        menu = QMenu(self)
        bl_action = menu.addAction(f"Blacklist {data.type_name}")
        
        ignore_menu = menu.addMenu("Add to ignore group")
        for group_name in get_ignore_group_names():
            act = ignore_menu.addAction(group_name.title())
            act.triggered.connect(lambda checked, g=group_name, t=data.type_id: self._add_to_ignore_group(t, g))

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == bl_action:
            TradeBlacklistRepository(self.app_state.db).add(data.type_id, data.type_name)
            self.status_label.setText(f"{data.type_name} blacklisted.")

    def _resolve_budget(self) -> float:
        if not self.chk_use_wallet.isChecked(): return self.spin_budget.value()
        buy_id = self.app_state.settings.trade_buy_character_id
        char = self.app_state.get_character(buy_id)
        if char is None:
            self.status_label.setText("No buy character set - wallet budget ignored.")
            return self.spin_budget.value()
        client = self.app_state.get_esi_client(char)
        if client is None: return self.spin_budget.value()
        try:
            balance = float(client.get_wallet_balance())
            self.spin_budget.setValue(balance)
            return balance
        except Exception as exc:
            self.status_label.setText(f"Wallet fetch failed: {str(exc)[:40]}")
            return self.spin_budget.value()

    def start_calculation(self) -> None:
        self.btn_calc.setEnabled(False)
        self.status_label.setText("Calculating from cache...")
        self.tree.clear()
        self._save_trade_controls()
        budget = self._resolve_budget()
        buy_loc, sell_loc, buy_region, sell_region = self._effective_locations()
        s = self.app_state.settings

        buy_client = self.app_state.get_esi_client(self.app_state.get_character(s.trade_buy_character_id)) if s.trade_buy_character_id else None
        sell_client = self.app_state.get_esi_client(self.app_state.get_character(s.trade_sell_character_id)) if s.trade_sell_character_id else None
        tax = TaxService(self.app_state.get_universe_resolver(), s, buy_client, sell_client)
        try:
            buy_fee = tax.buy_leg_fee_frac(buy_loc, placed=not self.chk_instant_buy.isChecked())
            sell_fee = tax.sell_leg_fee_frac(sell_loc, placed=not self.chk_instant_sell.isChecked())
        except Exception as exc:
            self.logger.warning("Fee calc failed, using 0: %s", exc)
            buy_fee, sell_fee = 0.0, 0.0

        blacklist = TradeBlacklistRepository(self.app_state.db).get_ids()
        if self.chk_exclude_active.isChecked():
            active_exclusions = get_active_batch_exclusions(self.app_state.db, s.trade_buy_character_id or 0, s.trade_sell_character_id or 0)
            blacklist = blacklist.union(active_exclusions)

        enabled_groups = {name for name, enabled in s.trade_ignore_groups.items() if enabled}
        if enabled_groups:
            ignored_ids = get_type_ids_for_groups(enabled_groups)
            blacklist = blacklist.union(ignored_ids)
            self.logger.info("Excluding %d type_ids from ignore groups", len(ignored_ids))

        params = {
            "buy_region": buy_region, "buy_loc": buy_loc, "sell_region": sell_region, "sell_loc": sell_loc,
            "cycle_days": self.spin_cycle.value(), "max_items": self.spin_items.value(),
            "haul_per_m3": self.spin_haul_m3.value(), "haul_min_charge": self.spin_haul_min.value(),
            "haul_full_load": self.spin_haul_full.value(), "haul_capacity": s.haul_jf_capacity_m3,
            "budget_isk": budget, "market_share_pct": self.spin_share.value(),
            "buy_fee_frac": buy_fee, "sell_fee_frac": sell_fee,
            "exclude_types": set(), "blacklist": blacklist,
            "access_token": self.app_state.get_primary_token(),
            "instant_buy": self.chk_instant_buy.isChecked(), "instant_sell": self.chk_instant_sell.isChecked(),
            "invert": self.chk_invert.isChecked(), "cache_only": True,
        }
        market_service = MarketService(self.app_state.db)
        resolver = self.app_state.get_universe_resolver()
        calculator = TradeCalculator(market_service, resolver)
        worker = TradeWorker(calculator, params)
        worker.finished.connect(lambda res, w=worker: self._on_finished(w, res))
        worker.error.connect(lambda msg, w=worker: self._on_error(w, msg))
        self._active_workers.add(worker)
        worker.start()

    def _on_finished(self, worker, results: list) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        if not self._active_workers: self.btn_calc.setEnabled(True)
        if not results:
            self.status_label.setText("No trades in cache. Press Refresh Market to pull fresh data.")
            self.btn_accept.setEnabled(False)
            return
        
        s = self.app_state.settings
        all_suggestions = []
        for batch in results: all_suggestions.extend(batch.items)
        regrouped = group_into_batches_smart(all_suggestions, self.spin_items.value(), s.haul_jf_capacity_m3, self._resolve_budget(), s.trade_max_merge_attempts)
        
        is_all_negative = regrouped[0].items[0].net_profit <= 0 if regrouped and regrouped[0].items else False
        if is_all_negative:
            self.status_label.setText("No profitable trades found. Showing top 5 least-negative trades.")
            self.btn_accept.setEnabled(False)
            text_color = Qt.GlobalColor.red
        else:
            self.status_label.setText(f"Found {len(regrouped)} recommended JF batches.")
            self.btn_accept.setEnabled(True)
            text_color = Qt.GlobalColor.green

        for batch in regrouped:
            batch_item = self.tree.invisibleRootItem() # Placeholder for structure
            from PySide6.QtWidgets import QTreeWidgetItem
            batch_item = QTreeWidgetItem([f"{batch.batch_name} ({batch.total_volume:,.0f} m3, spend {batch.total_buy:,.2f} ISK)", "", "", "", "", "", "", "", f"{batch.total_profit:,.2f} ISK", "", ""])
            batch_item.setData(0, Qt.ItemDataRole.UserRole, batch)
            batch_item.setForeground(0, text_color)
            for r in batch.items:
                prefix = "⚡ " if hasattr(r, 'sell_mode') and r.sell_mode == "instant" else "  "
                shift_display = f"{r.shift_ratio:.2f}" if hasattr(r, 'shift_ratio') else "1.00"
                child = QTreeWidgetItem([f"{prefix}{r.type_name}", f"{r.quantity:,}", f"{r.est_sellable:,}", f"{r.buy_price:,.2f}", f"{r.sell_price:,.2f}", f"{r.total_volume:,.1f}", f"{r.hauling_cost:,.2f}", f"{r.tax_cost:,.2f}", f"{r.net_profit:,.2f}", f"{r.profit_per_m3:,.2f}", shift_display])
                child.setData(0, Qt.ItemDataRole.UserRole, r)
                if is_all_negative: child.setForeground(0, Qt.GlobalColor.red)
                batch_item.addChild(child)
            batch_item.setExpanded(True)
            self.tree.addTopLevelItem(batch_item)

    def accept_selected(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a batch or item.")
            return
        s = self.app_state.settings
        batch = TradeBatch(buy_char_id=s.trade_buy_character_id or 0, sell_char_id=s.trade_sell_character_id or 0)
        total_expected = 0.0
        for tree_item in selected:
            data = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, TradeBatchRecommendation):
                for item in data.items:
                    batch.items.append(TradeBatchItem(type_id=item.type_id, type_name=item.type_name, quantity=item.quantity, buy_price=item.buy_price, sell_price=item.sell_price))
                    total_expected += item.net_profit
            elif isinstance(data, TradeSuggestion):
                batch.items.append(TradeBatchItem(type_id=data.type_id, type_name=data.type_name, quantity=data.quantity, buy_price=data.buy_price, sell_price=data.sell_price))
                total_expected += data.net_profit
        batch.expected_profit = total_expected
        repo = TradeBatchRepository(self.app_state.db)
        batch_id = repo.save_batch(batch)
        self.status_label.setText(f"Batch {batch_id} saved and tracked.")
        self.batch_list.refresh()
        self.tree.clear()

    def _on_error(self, worker, msg: str) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()
        if not self._active_workers: self.btn_calc.setEnabled(True)
        self.status_label.setText(f"Error: {msg[:60]}")

    def stop_workers(self) -> None:
        self.batch_list.stop_workers()
        for worker in list(self._active_workers):
            if worker.isRunning(): worker.wait(3000)
        self._active_workers.clear()