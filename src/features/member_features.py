from datetime import datetime, timezone
from typing import List, Literal
from pydantic import BaseModel


class IncomingMemberTransaction(BaseModel):
    memberId: str
    lastTransactionUtcTs: datetime
    lastTransactionType: Literal["BUY", "GIFT", "REDEEM"]
    lastTransactionPointsBought: float
    lastTransactionRevenueUsd: float


class MemberFeatures(BaseModel):
    AVG_POINTS_BOUGHT: float
    AVG_REVENUE_USD: float
    LAST_3_TRANSACTIONS_AVG_POINTS_BOUGHT: float
    LAST_3_TRANSACTIONS_AVG_REVENUE_USD: float
    PCT_BUY_TRANSACTIONS: float
    PCT_GIFT_TRANSACTIONS: float
    PCT_REDEEM_TRANSACTIONS: float
    DAYS_SINCE_LAST_TRANSACTION: int


def compute_member_features(
    history: List[IncomingMemberTransaction],
    current_tx: IncomingMemberTransaction,
    now: datetime | None = None,
) -> MemberFeatures:
    """
    Compute the features required by the prediction service, using both
    historical transactions and the current incoming transaction.
    """
    all_txs = history + [current_tx]
    n = len(all_txs)

    total_points = sum(t.lastTransactionPointsBought for t in all_txs)
    total_revenue = sum(t.lastTransactionRevenueUsd for t in all_txs)

    avg_points = total_points / n if n else 0.0
    avg_revenue = total_revenue / n if n else 0.0

    # Last 3 transactions (by timestamp, most recent first)
    sorted_txs = sorted(all_txs, key=lambda t: t.lastTransactionUtcTs, reverse=True)
    last3 = sorted_txs[:3]
    n3 = len(last3)

    last3_avg_points = (
        sum(t.lastTransactionPointsBought for t in last3) / n3 if n3 else 0.0
    )
    last3_avg_revenue = (
        sum(t.lastTransactionRevenueUsd for t in last3) / n3 if n3 else 0.0
    )

    # Transaction type percentages
    buy_count = sum(1 for t in all_txs if t.lastTransactionType == "BUY")
    gift_count = sum(1 for t in all_txs if t.lastTransactionType == "GIFT")
    redeem_count = sum(1 for t in all_txs if t.lastTransactionType == "REDEEM")

    pct_buy = buy_count / n if n else 0.0
    pct_gift = gift_count / n if n else 0.0
    pct_redeem = redeem_count / n if n else 0.0

    # Days since last transaction
    latest_tx_time = max(t.lastTransactionUtcTs for t in all_txs)
    now = now or datetime.now(timezone.utc)
    days_since_last = (now.date() - latest_tx_time.date()).days

    return MemberFeatures(
        AVG_POINTS_BOUGHT=avg_points,
        AVG_REVENUE_USD=avg_revenue,
        LAST_3_TRANSACTIONS_AVG_POINTS_BOUGHT=last3_avg_points,
        LAST_3_TRANSACTIONS_AVG_REVENUE_USD=last3_avg_revenue,
        PCT_BUY_TRANSACTIONS=pct_buy,
        PCT_GIFT_TRANSACTIONS=pct_gift,
        PCT_REDEEM_TRANSACTIONS=pct_redeem,
        DAYS_SINCE_LAST_TRANSACTION=days_since_last,
    )
