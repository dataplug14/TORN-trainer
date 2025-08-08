import asyncio
import os

import httpx
import pytest
import respx

from src.api import TornClient, TORN_BASE
from src.state import db as db_state
from src.utils import TokenBucketLimiter


@pytest.mark.asyncio
async def test_rate_limiter_fast_spacing():
    limiter = TokenBucketLimiter(capacity=10, refill_rate_per_sec=100, min_spacing=0.01)
    # Should be able to acquire several quickly
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()


@pytest.mark.asyncio
async def test_user_request_building(tmp_path):
    conn = db_state.get_connection(str(tmp_path / "test.db"))
    client = TornClient(api_key="TEST", user_id="123", conn=conn, max_requests_per_min=100, min_spacing_seconds=0.01)
    route = respx.get(f"{TORN_BASE}/user/123").mock(return_value=httpx.Response(200, json={"bars": {"energy": {"current": 50}, "nerve": {"current": 20}}}))
    with respx.mock:
        data = await client.get_user("bars,profile")
        assert route.called
        assert "bars" in data
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_on_429(tmp_path):
    conn = db_state.get_connection(str(tmp_path / "test.db"))
    client = TornClient(api_key="TEST", user_id="123", conn=conn, max_requests_per_min=100, min_spacing_seconds=0.0)
    calls = {"n": 0}

    def responder(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": {"code": 5}})
        return httpx.Response(200, json={"ok": True})

    route = respx.get(f"{TORN_BASE}/user/123").mock(side_effect=responder)
    with respx.mock:
        data = await client.get_user("bars")
        assert data.get("ok") is True
        assert route.call_count >= 3
    await client.aclose()

