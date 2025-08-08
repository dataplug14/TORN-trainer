import json
import os
import sqlite3
from typing import Any, Dict, Optional


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or os.getenv("DB_PATH") or "torn.db"
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL,
            payload TEXT,
            result_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            ts TEXT PRIMARY KEY,
            json TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS keys (
            id TEXT PRIMARY KEY,
            key TEXT,
            disabled_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS market_watch (
            item_id INTEGER PRIMARY KEY,
            buy_threshold REAL,
            sell_threshold REAL,
            last_seen_price REAL
        )
        """
    )
    conn.commit()


def log_action(conn: sqlite3.Connection, action_type: str, payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO actions(timestamp, action_type, payload, result_json) VALUES(datetime('now'),?,?,?)",
        (action_type, json.dumps(payload) if payload else None, json.dumps(result) if result else None),
    )
    conn.commit()


def save_snapshot(conn: sqlite3.Connection, data: Dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO snapshots(ts, json) VALUES(datetime('now'),?)",
        (json.dumps(data),),
    )
    conn.commit()


def get_last_snapshot(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT json FROM snapshots ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return None
    return json.loads(row[0])


def mark_key_disabled(conn: sqlite3.Connection, key_id: str, api_key: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO keys(id, key, disabled_at) VALUES(?,?,datetime('now'))",
        (key_id, api_key),
    )
    conn.commit()


def is_key_disabled(conn: sqlite3.Connection, key_id: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT disabled_at FROM keys WHERE id=?", (key_id,))
    row = cur.fetchone()
    return bool(row and row[0])


def upsert_market_watch(conn: sqlite3.Connection, item_id: int, buy_threshold: float, sell_threshold: float) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO market_watch(item_id,buy_threshold,sell_threshold,last_seen_price)
        VALUES(?,?,?,NULL)
        ON CONFLICT(item_id) DO UPDATE SET
            buy_threshold=excluded.buy_threshold,
            sell_threshold=excluded.sell_threshold
        """,
        (item_id, buy_threshold, sell_threshold),
    )
    conn.commit()


def update_market_last_price(conn: sqlite3.Connection, item_id: int, price: float) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE market_watch SET last_seen_price=? WHERE item_id=?",
        (price, item_id),
    )
    conn.commit()


def get_market_watch_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("SELECT item_id,buy_threshold,sell_threshold,last_seen_price FROM market_watch")
    return cur.fetchall()

