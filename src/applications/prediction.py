from src.applications.base_application import BaseApplication
from pydantic import BaseModel


class MemberFeatures(BaseModel):
    AVG_POINTS_BOUGHT: float
    AVG_REVENUE_USD: float
    LAST_3_TRANSACTIONS_AVG_POINTS_BOUGHT: float
    LAST_3_TRANSACTIONS_AVG_REVENUE_USD: float
    PCT_BUY_TRANSACTIONS: float
    PCT_GIFT_TRANSACTIONS: float
    PCT_REDEEM_TRANSACTIONS: float
    DAYS_SINCE_LAST_TRANSACTION: int


def predict_ats(member_features: MemberFeatures) -> dict:
    expected_volume = (
        member_features.LAST_3_TRANSACTIONS_AVG_POINTS_BOUGHT * 0.7
        + member_features.AVG_POINTS_BOUGHT * 0.3
    )
    weight = (
        member_features.PCT_BUY_TRANSACTIONS
        + member_features.PCT_GIFT_TRANSACTIONS
        - member_features.PCT_REDEEM_TRANSACTIONS
    )
    if weight < 0:
        weight = 0
    return {"prediction": abs(expected_volume * weight)}


def predict_resp(member_features: MemberFeatures) -> dict:
    product_weight = (
        member_features.PCT_BUY_TRANSACTIONS * 0.4
        + member_features.PCT_GIFT_TRANSACTIONS * 0.3
        + member_features.PCT_REDEEM_TRANSACTIONS * 0.3
    )
    revenue_weight = (
        member_features.AVG_REVENUE_USD * 0.3
        + member_features.LAST_3_TRANSACTIONS_AVG_REVENUE_USD * 0.7
    ) / 100
    day_weight = 1 / (member_features.DAYS_SINCE_LAST_TRANSACTION + 1)
    product = product_weight * revenue_weight * day_weight
    return {"prediction": min(0.9, 1000 * product)}


app = BaseApplication()
app.add_api_route("/ml/ats/predict", predict_ats, methods=["POST"])
app.add_api_route("/ml/resp/predict", predict_resp, methods=["POST"])
