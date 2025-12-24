from __future__ import annotations

import asyncio
import logging
from typing import Tuple

from src.features.member_features import IncomingMemberTransaction, MemberFeatures, compute_member_features
from src.clients.clients import (
    MemberDataClient,
    PredictionClient,
    OfferClient,
    OfferRequest,
    OfferResponse,
)
from src.orchestrator.instrumentation import timed

logger = logging.getLogger("orchestrator")


class OrchestratorService:
    """Business logic for /member/offer.
    """

    def __init__(
        self,
        member_client: MemberDataClient,
        prediction_client: PredictionClient,
        offer_client: OfferClient,
        *,
        prediction_concurrency: asyncio.Semaphore | None = None,
    ):
        self._member_client = member_client
        self._prediction_client = prediction_client
        self._offer_client = offer_client
        self._pred_sem = prediction_concurrency

    @timed(logger, "history_fetch")
    async def _fetch_history(self, member_id: str):
        return await self._member_client.get_member_history(member_id)

    @timed(logger, "features_compute")
    async def _compute_features(self, history, tx: IncomingMemberTransaction) -> MemberFeatures:
        return compute_member_features(history, tx)

    @timed(logger, "predictions_fanout")
    async def _predict(self, features: MemberFeatures):
        async def _predict_ats():
            if self._pred_sem:
                async with self._pred_sem:
                    return await self._prediction_client.predict_ats(features)
            return await self._prediction_client.predict_ats(features)

        async def _predict_resp():
            if self._pred_sem:
                async with self._pred_sem:
                    return await self._prediction_client.predict_resp(features)
            return await self._prediction_client.predict_resp(features)

        ats_task = asyncio.create_task(_predict_ats())
        resp_task = asyncio.create_task(_predict_resp())
        return await asyncio.gather(ats_task, resp_task)

    @timed(logger, "offer_assign")
    async def _assign_offer(self, ats_pred, resp_pred):
        offer_req = OfferRequest(
            ats_prediction=ats_pred.prediction,
            resp_prediction=resp_pred.prediction,
        )
        return await self._offer_client.assign_offer(offer_req)

    async def assign_offer(self, tx: IncomingMemberTransaction) -> Tuple[OfferResponse, MemberFeatures, int]:
        """Compute offer for a member.

        Returns: (offer_response, computed_features, history_len)
        """
        history = await self._fetch_history(tx.memberId)
        features = await self._compute_features(history, tx)
        ats_pred, resp_pred = await self._predict(features)
        offer = await self._assign_offer(ats_pred, resp_pred)
        return offer, features, len(history)

    async def store_transaction_best_effort(self, tx: IncomingMemberTransaction) -> None:
        """Persist transaction without failing the main request.

        Rationale: write-path failures shouldn't prevent returning the computed offer.
        """
        try:
            await self._member_client.store_transaction(tx)
        except Exception as exc:
            logger.exception("transaction_store_failed memberId=%s error=%s", tx.memberId, str(exc))
