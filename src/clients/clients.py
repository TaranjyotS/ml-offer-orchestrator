from __future__ import annotations

from typing import Any, List, Optional, Sequence, TypeVar, Callable
from datetime import datetime, timezone
import asyncio
import logging
import random

import httpx
from pydantic import BaseModel

from src.features.member_features import IncomingMemberTransaction, MemberFeatures

logger = logging.getLogger("clients")


def _model_to_json(model: BaseModel) -> dict:
    """Serialize a Pydantic model to JSON-compatible dict.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[no-any-return]


def _parse_history_ts(ts: Any) -> datetime:
    """Parse timestamps returned by member_data into a tz-aware UTC datetime.

    Handles:
      - "YYYY-MM-DD HH:MM:SS"
      - ISO strings with offset
      - ISO strings ending with 'Z'

    Raises:
      ValueError: if missing/blank or unparsable.
    """
    if ts is None:
        raise ValueError("Missing lastTransactionUtcTs")

    s = str(ts).strip()
    if not s:
        raise ValueError("Missing lastTransactionUtcTs")

    # Fix invalid combined timezone marker
    s = s.replace("Z+00:00", "+00:00")

    # Convert trailing 'Z' to '+00:00' for from iso format compatibility
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # Handle "YYYY-MM-DD HH:MM:SS"
    if " " in s and "T" not in s:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


T = TypeVar("T", bound=BaseModel)


class UpstreamError(Exception):
    """Represents an upstream HTTP failure we want to handle at the edge."""

    def __init__(self, service: str, url: str, status_code: int, body: str | None = None):
        super().__init__(f"{service} upstream error {status_code} for {url}")
        self.service = service
        self.url = url
        self.status_code = status_code
        self.body = body


class BaseServiceClient:
    """Shared behavior for all HTTP clients.
    """

    def __init__(
        self,
        service_name: str,
        client: httpx.AsyncClient,
        *,
        max_retries: int = 2,
        backoff_seconds: float = 0.15,
        retry_statuses: Sequence[int] = (429, 502, 503, 504),
        semaphore: asyncio.Semaphore | None = None,
    ):
        self._service_name = service_name
        self._client = client
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._retry_statuses = set(int(x) for x in retry_statuses)
        self._sem = semaphore

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json: Optional[dict] = None,
        ok_statuses: Sequence[int] = (200,),
        allow_404_as_empty: bool = False,
    ) -> Any:
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= self._max_retries:
            attempt += 1
            try:
                if self._sem is None:
                    resp = await self._client.request(method, url, json=json)
                else:
                    async with self._sem:
                        resp = await self._client.request(method, url, json=json)

                if allow_404_as_empty and resp.status_code == 404:
                    return []

                if resp.status_code in ok_statuses:
                    try:
                        return resp.json()
                    except Exception:
                        return {}

                # Retry on transient statuses
                if resp.status_code in self._retry_statuses and attempt <= self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue

                body = None
                try:
                    body = resp.text
                except Exception:
                    body = None
                raise UpstreamError(self._service_name, str(resp.url), resp.status_code, body)

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt <= self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                raise UpstreamError(self._service_name, url, 0, str(e)) from e

        if last_exc:
            raise last_exc
        raise RuntimeError("Unreachable")

    async def _sleep_backoff(self, attempt: int) -> None:
        base = self._backoff_seconds * (2 ** max(0, attempt - 1))
        jitter = random.uniform(0, base * 0.2)
        await asyncio.sleep(base + jitter)


class AtsPrediction(BaseModel):
    prediction: float


class RespPrediction(BaseModel):
    prediction: float


class OfferRequest(BaseModel):
    ats_prediction: float
    resp_prediction: float


class OfferResponse(BaseModel):
    offer: str


class MemberDataClient(BaseServiceClient):
    def __init__(self, client: httpx.AsyncClient, **kwargs: Any):
        super().__init__("member_data", client, **kwargs)

    async def get_member_history(self, member_id: str) -> List[IncomingMemberTransaction]:
        """Fetch a member's history from the member_data service.

        Calls:
        GET /member_data/{member_id}.
        
        Returns:
        An empty list when the member is not found (404).
        
        Raises:
        UpstreamError on other HTTP failures.
        """
        data = await self._request_json(
            "GET",
            f"/member_data/{member_id}",
            ok_statuses=(200,),
            allow_404_as_empty=True,
        )

        if not isinstance(data, list):
            raise ValueError(f"Unexpected member_data response shape: {type(data)}")

        history: List[IncomingMemberTransaction] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                item["lastTransactionUtcTs"] = _parse_history_ts(item.get("lastTransactionUtcTs"))
                history.append(IncomingMemberTransaction(**item))
            except Exception:
                # Skip invalid history records
                continue

        return history

    async def store_transaction(self, tx: IncomingMemberTransaction) -> None:
        """Persist the current transaction in member_data (POST /member_data)."""
        payload = _model_to_json(tx)
        # member_data returns 200 or 201; accept both
        await self._request_json("POST", "/member_data", json=payload, ok_statuses=(200, 201))


class PredictionClient(BaseServiceClient):
    def __init__(self, client: httpx.AsyncClient, **kwargs: Any):
        super().__init__("prediction", client, **kwargs)

    async def predict_ats(self, features: MemberFeatures) -> AtsPrediction:
        payload = _model_to_json(features)
        data = await self._request_json("POST", "/ml/ats/predict", json=payload, ok_statuses=(200,))
        return AtsPrediction(prediction=float(data["prediction"]))

    async def predict_resp(self, features: MemberFeatures) -> RespPrediction:
        payload = _model_to_json(features)
        data = await self._request_json("POST", "/ml/resp/predict", json=payload, ok_statuses=(200,))
        return RespPrediction(prediction=float(data["prediction"]))


class OfferClient(BaseServiceClient):
    def __init__(self, client: httpx.AsyncClient, **kwargs: Any):
        super().__init__("offer_engine", client, **kwargs)

    async def assign_offer(self, req: OfferRequest) -> OfferResponse:
        payload = _model_to_json(req)
        data = await self._request_json("POST", "/offer/assign", json=payload, ok_statuses=(200,))
        return OfferResponse(**data)
