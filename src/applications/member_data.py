from pydantic import BaseModel
from fastapi import HTTPException
from src.applications.base_application import BaseApplication
from typing import Dict, List


class MemberData(BaseModel):
    memberId: str
    lastTransactionUtcTs: str
    lastTransactionType: str
    lastTransactionPointsBought: float
    lastTransactionRevenueUsd: float


member_data_store: Dict[str, List[MemberData]] = {}


def store_member_data(data: MemberData):
    member_id = data.memberId
    if member_id not in member_data_store:
        member_data_store[member_id] = []
    member_data_store[member_id].append(data)
    return data


def get_member_data(member_id: str) -> List[MemberData]:
    if member_id not in member_data_store:
        raise HTTPException(status_code=404, detail="Member not found")
    return member_data_store[member_id]


app = BaseApplication()
app.add_api_route("/member_data", store_member_data, methods=["POST"], response_model=MemberData)
app.add_api_route("/member_data/{member_id}", get_member_data, methods=["GET"], response_model=List[MemberData])
