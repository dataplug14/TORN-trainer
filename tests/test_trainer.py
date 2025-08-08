import httpx
import pytest
import respx

from src.api import TornClient, TORN_BASE
from src.state import db as db_state
from src.trainer import Trainer


@pytest.mark.asyncio
async def test_decision_logic_recommends_gym_and_crime(tmp_path):
    conn = db_state.get_connection(str(tmp_path / "test.db"))
    client = TornClient(api_key="TEST", user_id="123", conn=conn, max_requests_per_min=100, min_spacing_seconds=0.0)

    with respx.mock:
        # bars/profile
        respx.get(f"{TORN_BASE}/user/123", params={"selections": "bars,profile", "key": "TEST"}).mock(return_value=httpx.Response(200, json={
            "bars": {"energy": {"current": 100}, "nerve": {"current": 50}}
        }))
        # crimes
        respx.get(f"{TORN_BASE}/torn").mock(return_value=httpx.Response(200, json={
            "crimes": {
                "1": {"name": "Crime A", "nerve": 5, "money_min": 1000, "money_max": 3000},
                "2": {"name": "Crime B", "nerve": 10, "money_min": 2500, "money_max": 2600}
            }
        }))
        respx.get(f"{TORN_BASE}/market/108").mock(return_value=httpx.Response(200, json={
            "bazaar": [{"price": 50000}, {"price": 40000}]
        }))
        # cooldowns OK
        respx.get(f"{TORN_BASE}/user/123", params={"selections": "cooldowns", "key": "TEST"}).mock(return_value=httpx.Response(200, json={"cooldowns": {"crimes": 0}}))

        db_state.upsert_market_watch(conn, 108, 45000, 60000)

        trainer = Trainer(client=client, conn=conn, energy_threshold=90, nerve_threshold=30)
        res = await trainer.decide_and_recommend(simulate_money=False, dry_run=True)
        alerts = await trainer.watch_market()
        assert any(r.get("type") == "gym" for r in res.get("recommendations", []))
        assert any(r.get("type") == "crime" for r in res.get("recommendations", []))
        assert any(a.get("type") == "buy" for a in alerts)
    await client.aclose()

