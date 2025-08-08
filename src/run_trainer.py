from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from .utils import load_env, setup_logging, prompt_api_key_and_user_id
from .state import db as db_state
from .api import TornClient
from .trainer import Trainer


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Torn trainer (read-only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--simulate-money", action="store_true")
        sp.add_argument("--dry-run", action="store_true")
        sp.add_argument("--max-requests-per-min", type=int, default=int(os.getenv("MAX_REQUESTS_PER_MIN", "60")))
        sp.add_argument("--energy-threshold", type=int, default=int(os.getenv("ENERGY_THRESHOLD", "90")))
        sp.add_argument("--nerve-threshold", type=int, default=int(os.getenv("NERVE_THRESHOLD", "30")))
        sp.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
        sp.add_argument("--market-watch", action="append", default=[], help="ITEM_ID:BUY:SELL (repeatable)")

    sp_start = sub.add_parser("start", help="Run continuous trainer")
    add_common(sp_start)
    sp_start.add_argument("--interval", type=float, default=30.0)

    sp_once = sub.add_parser("run-once", help="Run a single decision loop")
    add_common(sp_once)

    sp_status = sub.add_parser("status", help="Show latest snapshots/actions")
    sp_status.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))

    sp_dry = sub.add_parser("dry-run", help="Alias to run-once with --dry-run")
    add_common(sp_dry)

    return p.parse_args(argv)


def _parse_market_watch(conn, items: list[str]) -> None:
    for spec in items:
        try:
            item_id_s, buy_s, sell_s = spec.split(":")
            item_id = int(item_id_s)
            buy_th = float(buy_s)
            sell_th = float(sell_s)
            db_state.upsert_market_watch(conn, item_id, buy_th, sell_th)
        except Exception:
            print(f"Invalid --market-watch spec: {spec}. Expected ITEM_ID:BUY:SELL")


def _build_client(args, log):
    api_key = os.getenv("API_KEY")
    user_id = os.getenv("USER_ID")
    if not api_key or not user_id:
        ak, uid = prompt_api_key_and_user_id()
        api_key = api_key or ak
        user_id = user_id or uid
    if not api_key or not user_id:
        print("API key and USER ID are required.")
        sys.exit(2)
    conn = db_state.get_connection(os.getenv("DB_PATH"))
    client = TornClient(
        api_key=api_key,
        user_id=user_id,
        conn=conn,
        max_requests_per_min=min(100, max(1, args.max_requests_per_min)),
        min_spacing_seconds=float(os.getenv("SAFE_SPACING_SECONDS", "1.0")),
        log=log,
    )
    return client, conn


async def _run_start(args):
    load_env()
    log = setup_logging(args.log_level)
    client, conn = _build_client(args, log)
    _parse_market_watch(conn, args.market_watch)
    trainer = Trainer(
        client=client,
        conn=conn,
        energy_threshold=args.energy_threshold,
        nerve_threshold=args.nerve_threshold,
        log=log,
    )
    await trainer.run_forever(interval_seconds=args.interval, simulate_money=args.simulate_money, dry_run=args.dry_run)


async def _run_once(args, force_dry: bool = False):
    load_env()
    log = setup_logging(args.log_level)
    client, conn = _build_client(args, log)
    _parse_market_watch(conn, args.market_watch)
    trainer = Trainer(
        client=client,
        conn=conn,
        energy_threshold=args.energy_threshold,
        nerve_threshold=args.nerve_threshold,
        log=log,
    )
    try:
        res = await trainer.decide_and_recommend(simulate_money=args.simulate_money, dry_run=args.dry_run or force_dry)
        alerts = await trainer.watch_market()
        print({"recommendations": res.get("recommendations"), "alerts": alerts})
    finally:
        await client.aclose()


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    if args.cmd == "status":
        load_env()
        log = setup_logging(args.log_level)
        conn = db_state.get_connection(os.getenv("DB_PATH"))
        last = db_state.get_last_snapshot(conn)
        print({"last_snapshot": last})
        return

    import asyncio

    if args.cmd == "start":
        asyncio.run(_run_start(args))
    elif args.cmd == "run-once":
        asyncio.run(_run_once(args))
    elif args.cmd == "dry-run":
        asyncio.run(_run_once(args, force_dry=True))


if __name__ == "__main__":
    main()

