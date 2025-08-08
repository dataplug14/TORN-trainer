from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, Optional

from .api import TornClient
from .state import db as db_state
from .utils import safe_sleep


DEFAULT_ENERGY_THRESHOLD = 90
DEFAULT_NERVE_THRESHOLD = 30


class Trainer:
    def __init__(
        self,
        client: TornClient,
        conn,
        energy_threshold: int = DEFAULT_ENERGY_THRESHOLD,
        nerve_threshold: int = DEFAULT_NERVE_THRESHOLD,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.client = client
        self.conn = conn
        self.energy_threshold = energy_threshold
        self.nerve_threshold = nerve_threshold
        self.log = log or logging.getLogger("torn_trainer")

    async def decide_and_recommend(self, simulate_money: bool = False, dry_run: bool = True) -> Dict[str, Any]:
        recs: list[Dict[str, Any]] = []
        # Fetch user bars and cooldowns
        user = await self.client.get_user("bars,profile")
        cooldowns = await self.client.get_user("cooldowns")

        bars = user.get("bars", {}) if isinstance(user, dict) else {}
        energy = bars.get("energy", {}).get("current", 0)
        nerve = bars.get("nerve", {}).get("current", 0)

        if simulate_money:
            # Lightweight synthetic overlay for money sim
            user.setdefault("money", {}).setdefault("onhand", 1_000_000)

        # Gym recommendation
        if energy >= self.energy_threshold:
            rec = {
                "type": "gym",
                "message": f"Energy {energy} >= {self.energy_threshold} — recommend gym: slot 1",
                "slot": 1,
                "points": min(energy, 150),
            }
            recs.append(rec)
            await self.client.do_train(slot=rec["slot"], points=rec["points"], dry_run=dry_run)

        # Crime recommendation
        if nerve >= self.nerve_threshold and _crimes_allowed(cooldowns):
            crimes = await self.client.get_crime_info()
            best = _best_crime_by_cash_per_nerve(crimes)
            if best:
                recs.append({
                    "type": "crime",
                    "message": f"Nerve {nerve} >= {self.nerve_threshold} — recommend crime: {best['name']} (cpn={best['cash_per_nerve']:.2f})",
                    "crime": best,
                })

        snapshot = {"user": user, "cooldowns": cooldowns, "recommendations": recs}
        db_state.save_snapshot(self.conn, snapshot)
        return {"recommendations": recs}

    async def watch_market(self) -> list[Dict[str, Any]]:
        alerts: list[Dict[str, Any]] = []
        rows = db_state.get_market_watch_all(self.conn)
        for row in rows:
            item_id = int(row["item_id"])
            buy_th = float(row["buy_threshold"]) if row["buy_threshold"] is not None else None
            sell_th = float(row["sell_threshold"]) if row["sell_threshold"] is not None else None
            info = await self.client.get_market_item(item_id)
            price = _extract_lowest_bazaar_price(info)
            if price is not None:
                db_state.update_market_last_price(self.conn, item_id, price)
                if buy_th is not None and price <= buy_th:
                    msg = f"Market BUY alert for item {item_id}: price {price} <= {buy_th}"
                    alerts.append({"item_id": item_id, "type": "buy", "message": msg, "price": price})
                if sell_th is not None and price >= sell_th:
                    msg = f"Market SELL alert for item {item_id}: price {price} >= {sell_th}"
                    alerts.append({"item_id": item_id, "type": "sell", "message": msg, "price": price})
        for alert in alerts:
            db_state.log_action(self.conn, "market_alert", {"alert": alert}, {"notified": True})
        return alerts

    async def run_forever(self, interval_seconds: float = 30.0, simulate_money: bool = False, dry_run: bool = True) -> None:
        try:
            while True:
                try:
                    results = await self.decide_and_recommend(simulate_money=simulate_money, dry_run=dry_run)
                    alerts = await self.watch_market()
                    if results.get("recommendations"):
                        self.log.info("Recommendations: %s", results["recommendations"])
                    if alerts:
                        self.log.info("Market alerts: %s", alerts)
                except Exception:
                    self.log.exception("Decision loop error")
                await safe_sleep(interval_seconds)
        finally:
            await self.client.aclose()


def _crimes_allowed(cooldowns: Dict[str, Any]) -> bool:
    cd = cooldowns.get("cooldowns", {}) if isinstance(cooldowns, dict) else {}
    crimes_cd = cd.get("crimes", 0)  # seconds remaining
    return crimes_cd == 0


def _best_crime_by_cash_per_nerve(crimes_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Torn crimes payload under `crimes` selection is a dict of crimes keyed by id
    crimes = (crimes_payload or {}).get("crimes")
    if not isinstance(crimes, dict):
        return None
    best: Optional[Dict[str, Any]] = None
    for cid, c in crimes.items():
        nerve = c.get("nerve") or c.get("nerve_required") or c.get("nerveCost")
        # Try money ranges if available
        min_cash = c.get("money_min") or c.get("min_cash") or 0
        max_cash = c.get("money_max") or c.get("max_cash") or 0
        cash = (min_cash + max_cash) / 2 if (min_cash or max_cash) else c.get("value") or 0
        if not nerve or nerve <= 0:
            continue
        cpn = float(cash) / float(nerve)
        current = {
            "id": cid,
            "name": c.get("name", f"crime_{cid}"),
            "nerve": nerve,
            "cash_per_nerve": cpn,
        }
        if best is None or current["cash_per_nerve"] > best["cash_per_nerve"]:
            best = current
    return best


def _extract_lowest_bazaar_price(info: Dict[str, Any]) -> Optional[float]:
    # `market/{item_id}?selections=bazaar` returns a list under bazaar
    bazaar = info.get("bazaar") if isinstance(info, dict) else None
    if isinstance(bazaar, list) and bazaar:
        try:
            prices = [float(entry.get("price")) for entry in bazaar if entry.get("price") is not None]
            return min(prices) if prices else None
        except Exception:
            return None
    return None

