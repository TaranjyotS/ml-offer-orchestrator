from pydantic import BaseModel
from src.applications.base_application import BaseApplication


class OfferRequest(BaseModel):
    ats_prediction: float
    resp_prediction: float


def get_offer(prediction: OfferRequest) -> dict:
    if prediction.ats_prediction * prediction.resp_prediction >= 200:
        result = "50% Discount"
    else:
        result = "35% Bonus"
    return {"offer": result}


app = BaseApplication()
app.add_api_route("/offer/assign", get_offer, methods=["POST"])
