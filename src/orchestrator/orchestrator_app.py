from __future__ import annotations

import logging
import time

from fastapi import Body, Depends, HTTPException
from pydantic import BaseModel

from src.applications.base_application import BaseApplication
from src.clients.clients import UpstreamError
from src.features.member_features import IncomingMemberTransaction
from src.orchestrator.dependencies import lifespan, get_orchestrator_service
from src.orchestrator.logging_utils import configure_logging
from src.orchestrator.middleware import RequestIdMiddleware
from src.orchestrator.service import OrchestratorService

# -----------------------------------------------------------------------------#
# Logging setup
# -----------------------------------------------------------------------------#
logger = logging.getLogger("orchestrator")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)
configure_logging()

# -----------------------------------------------------------------------------#
# FastAPI app (with DI + lifecycle)
# -----------------------------------------------------------------------------#
app = BaseApplication(lifespan=lifespan)
app.add_middleware(RequestIdMiddleware, header_name="X-Request-ID")


class FinalOfferResponse(BaseModel):
    memberId: str
    offer: str


def _map_upstream_error(e: UpstreamError) -> HTTPException:
    """Map upstream failures to a stable API error for callers."""
    detail = {
        "service": e.service,
        "status_code": e.status_code,
        "message": str(e),
    }
    # 502 tells clients "your request was fine, an upstream dependency failed".
    return HTTPException(status_code=502, detail=detail)


@app.post("/member/offer", response_model=FinalOfferResponse)
async def assign_offer(
    tx: IncomingMemberTransaction = Body(...),
    orchestrator: OrchestratorService = Depends(get_orchestrator_service),
) -> FinalOfferResponse:
    """Main orchestrator endpoint.

    Flow:
      1. Fetch member history from member_data
      2. Compute features
      3. Call ATS & RESP prediction endpoints (in parallel)
      4. Call offer_engine to assign final offer
      5. Persist the current transaction to member_data (best-effort)
      6. Return {memberId, offer}
    """
    overall_start = time.perf_counter()
    logger.info("request_received memberId=%s", tx.memberId)

    try:
        offer, features, history_len = await orchestrator.assign_offer(tx)

        # Best-effort store. Failures are logged but do not fail the request.
        await orchestrator.store_transaction_best_effort(tx)

        total_ms = (time.perf_counter() - overall_start) * 1000
        logger.info(
            "request_completed memberId=%s history_len=%d offer=%s total_latency_ms=%.2f",
            tx.memberId,
            history_len,
            offer.offer,
            total_ms,
        )
        return FinalOfferResponse(memberId=tx.memberId, offer=offer.offer)

    except UpstreamError as e:
        logger.warning(
            "upstream_failure memberId=%s service=%s status=%s",
            tx.memberId,
            e.service,
            e.status_code,
        )
        raise _map_upstream_error(e) from e
    except ValueError as e:
        # unexpected upstream shape, etc.
        logger.warning("bad_data memberId=%s error=%s", tx.memberId, str(e))
        raise HTTPException(status_code=502, detail={"message": str(e)}) from e
