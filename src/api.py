from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any, Dict, Optional

import httpx
import logging
import requests

from .utils import TokenBucketLimiter, small_jitter
from .state import db as db_state


TORN_BASE = "https://api.torn.com"


class TornAPIError(Exception):
    pass


def _redact_query(url: str) -> str:
    # Redact key param
    if "key=" in url:
        return url.split("key=")[0] + "key=REDACTED"
    return url


class TornClient:
    def __init__(
        self,
        api_key: str,
        user_id: Optional[str] = None,
        conn=None,
        max_requests_per_min: int = 60,
        min_spacing_seconds: float = 1.0,
        log: Optional[logging.Logger] = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_key = api_key
        self.user_id = user_id
        self.conn = conn or db_state.get_connection(os.getenv("DB_PATH"))
        self.log = log or logging.getLogger("torn_trainer")
        self.timeout = timeout_seconds
        # Token bucket
        capacity = min(100, max(1, max_requests_per_min))
        refill_rate = capacity / 60.0
        self.limiter = TokenBucketLimiter(
            capacity=capacity,
            refill_rate_per_sec=refill_rate,
            min_spacing=min_spacing_seconds,
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        self._auth_failures = 0

    async def _request(self, section: str, id_part: Optional[str], selections: Optional[str], extra_params: Optional[dict] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise TornAPIError("API key required")
        if db_state.is_key_disabled(self.conn, self.user_id or "default"):
            raise TornAPIError("API key marked disabled. Aborting.")

        params = {"key": self.api_key}
        if selections:
            params["selections"] = selections
        if extra_params:
            params.update(extra_params)

        path = f"/{section}"
        if id_part:
            path += f"/{id_part}"
        url = f"{TORN_BASE}{path}"

        # Retries with exponential backoff for 429/5xx
        attempt = 0
        max_attempts = 5
        base_backoff = 1.0
        while True:
            await self.limiter.acquire()
            try:
                resp = await self._client.get(url, params=params)
            except Exception as exc:  # network error
                attempt += 1
                if attempt >= max_attempts:
                    self._log_api(url, -1, {"error": str(exc)})
                    raise
                await asyncio.sleep(small_jitter(base_backoff * (2 ** (attempt - 1))))
                continue

            status = resp.status_code
            text = resp.text
            self._log_api(resp.request.url.__str__(), status, _safe_json(text))

            if status == 429 or 500 <= status < 600:
                attempt += 1
                if attempt >= max_attempts:
                    resp.raise_for_status()
                # Retry
                await asyncio.sleep(small_jitter(base_backoff * (2 ** (attempt - 1))))
                continue

            if status in (401, 403):
                self._auth_failures += 1
                if self._auth_failures >= 3:
                    db_state.mark_key_disabled(self.conn, self.user_id or "default", self.api_key)
                resp.raise_for_status()

            # Torn may return 200 with error payload; check
            data = _safe_json(text)
            if isinstance(data, dict) and data.get("error"):
                code = data["error"].get("code")
                if code in (1, 2, 10, 11):  # common auth/permission codes
                    self._auth_failures += 1
                    if self._auth_failures >= 3:
                        db_state.mark_key_disabled(self.conn, self.user_id or "default", self.api_key)
                return data
            return data

    def _log_api(self, url: str, status: int, result: Dict[str, Any]) -> None:
        redacted = _redact_query(url)
        self.log.info(f"API {status} GET {redacted}")
        try:
            db_state.log_action(self.conn, "api_request", {"url": redacted}, {"status": status, "result": result})
        except Exception:
            self.log.exception("Failed to log API response")

    async def get_user(self, selections: str = "bars,profile") -> Dict[str, Any]:
        uid = self.user_id
        if not uid:
            raise TornAPIError("USER_ID required for user endpoint")
        return await self._request("user", str(uid), selections, None)

    async def get_gym(self) -> Dict[str, Any]:
        uid = self.user_id
        if not uid:
            raise TornAPIError("USER_ID required for gym endpoint")
        # According to docs, gym info is on user endpoint with selections=gym
        return await self._request("user", str(uid), "gym", None)

    async def get_crime_info(self) -> Dict[str, Any]:
        # crimes are under `torn` section with selections=crimes
        return await self._request("torn", None, "crimes", None)

    async def get_crime_cooldowns(self) -> Dict[str, Any]:
        uid = self.user_id
        if not uid:
            raise TornAPIError("USER_ID required for cooldowns endpoint")
        return await self._request("user", str(uid), "cooldowns", None)

    async def get_market_item(self, item_id: int, selections: str = "bazaar") -> Dict[str, Any]:
        return await self._request("market", str(item_id), selections, None)

    async def do_train(self, slot: int, points: int, dry_run: bool = True) -> Dict[str, Any]:
        # Read-only: we only plan and log
        plan = {
            "action": "train",
            "slot": slot,
            "points": points,
            "dry_run": dry_run,
            "curl": f"curl '{TORN_BASE}/user/{self.user_id}?selections=gym&key=REDACTED' # example read-only gym fetch",
        }
        db_state.log_action(self.conn, "plan_train", plan, {"planned": True})
        return plan

    async def aclose(self) -> None:
        await self._client.aclose()


class TornClientSync:
    def __init__(self, api_key: str, user_id: Optional[str] = None, timeout_seconds: float = 15.0) -> None:
        self.api_key = api_key
        self.user_id = user_id
        self.timeout = timeout_seconds

    def _request(self, section: str, id_part: Optional[str], selections: Optional[str], extra_params: Optional[dict] = None) -> Dict[str, Any]:
        params = {"key": self.api_key}
        if selections:
            params["selections"] = selections
        if extra_params:
            params.update(extra_params)
        path = f"/{section}"
        if id_part:
            path += f"/{id_part}"
        url = f"{TORN_BASE}{path}"
        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return _safe_json(r.text)

    def get_user(self, selections: str = "bars,profile") -> Dict[str, Any]:
        if not self.user_id:
            raise TornAPIError("USER_ID required")
        return self._request("user", str(self.user_id), selections, None)

    def get_market_item(self, item_id: int, selections: str = "bazaar") -> Dict[str, Any]:
        return self._request("market", str(item_id), selections, None)


def _safe_json(text: str) -> Dict[str, Any] | Any:
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text[:500]}

