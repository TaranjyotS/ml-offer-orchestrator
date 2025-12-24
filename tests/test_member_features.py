from datetime import datetime, timezone

from src.features.member_features import IncomingMemberTransaction, compute_member_features


def _tx(member_id: str, ts_iso: str, ttype: str, points: float, revenue: float) -> IncomingMemberTransaction:
    dt = datetime.fromisoformat(ts_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return IncomingMemberTransaction(
        memberId=member_id,
        lastTransactionUtcTs=dt,
        lastTransactionType=ttype,
        lastTransactionPointsBought=points,
        lastTransactionRevenueUsd=revenue,
    )


def test_compute_member_features_basic_stats_and_percentages():
    member_id = "A0"
    history = [
        _tx(member_id, "2019-01-01T00:00:00+00:00", "BUY", 100.0, 10.0),
        _tx(member_id, "2019-01-02T00:00:00+00:00", "GIFT", 200.0, 0.0),
        _tx(member_id, "2019-01-03T00:00:00+00:00", "REDEEM", -50.0, 0.0),
    ]
    current = _tx(member_id, "2019-01-04T00:00:00+00:00", "BUY", 300.0, 30.0)

    # implementation computes aggregates over (history + current)
    features = compute_member_features(history, current, now=datetime(2019, 1, 5, tzinfo=timezone.utc))

    assert features.AVG_POINTS_BOUGHT == (100.0 + 200.0 - 50.0 + 300.0) / 4
    assert features.AVG_REVENUE_USD == (10.0 + 0.0 + 0.0 + 30.0) / 4

    # last 3 are the most recent three among (history + current): Jan2, Jan3, Jan4
    assert features.LAST_3_TRANSACTIONS_AVG_POINTS_BOUGHT == (200.0 - 50.0 + 300.0) / 3
    assert features.LAST_3_TRANSACTIONS_AVG_REVENUE_USD == (0.0 + 0.0 + 30.0) / 3

    # percentages also over (history + current)
    assert features.PCT_BUY_TRANSACTIONS == 2 / 4
    assert features.PCT_GIFT_TRANSACTIONS == 1 / 4
    assert features.PCT_REDEEM_TRANSACTIONS == 1 / 4

    # now is Jan 5, latest tx is Jan 4 -> 1 day
    assert features.DAYS_SINCE_LAST_TRANSACTION == 1
