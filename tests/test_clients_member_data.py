import httpx
import pytest
import respx

from src.clients.clients import MemberDataClient


@pytest.mark.asyncio
@respx.mock
async def test_get_member_history_returns_empty_on_404():
    base_url = "http://member-data"
    respx.get(f"{base_url}/member_data/UNKNOWN").respond(404)

    async with httpx.AsyncClient(base_url=base_url) as http_client:
        client = MemberDataClient(http_client)
        history = await client.get_member_history("UNKNOWN")
        assert history == []


@pytest.mark.asyncio
@respx.mock
async def test_get_member_history_skips_only_truly_malformed_rows():
    base_url = "http://member-data"
    respx.get(f"{base_url}/member_data/A0").respond(
        200,
        json=[
            {
                "memberId": "A0",
                "lastTransactionUtcTs": "2019-01-07 02:45:38",
                "lastTransactionType": "BUY",
                "lastTransactionPointsBought": 100,
                "lastTransactionRevenueUsd": 1.0,
            },
            {
                "memberId": "A0",
                "lastTransactionUtcTs": "2019-01-07T11:50:33Z",
                "lastTransactionType": "GIFT",
                "lastTransactionPointsBought": 200,
                "lastTransactionRevenueUsd": 2.0,
            },
            {
                "memberId": "A0",
                "lastTransactionUtcTs": "2019-01-07T11:50:33Z+00:00",  # fixed by parser
                "lastTransactionType": "REDEEM",
                "lastTransactionPointsBought": -10,
                "lastTransactionRevenueUsd": 0.0,
            },
            {
                "memberId": "A0",
                "lastTransactionUtcTs": "",  # missing -> should be skipped
                "lastTransactionType": "BUY",
                "lastTransactionPointsBought": 10,
                "lastTransactionRevenueUsd": 0.1,
            },
            "not-a-dict",
        ],
    )

    async with httpx.AsyncClient(base_url=base_url) as http_client:
        client = MemberDataClient(http_client)
        history = await client.get_member_history("A0")

    assert len(history) == 3
    assert all(h.memberId == "A0" for h in history)
