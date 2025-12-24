from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import Request

from src.config.settings import Settings
from src.clients.clients import MemberDataClient, PredictionClient, OfferClient
from src.orchestrator.service import OrchestratorService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def get_orchestrator_service(request: Request) -> OrchestratorService:
    return request.app.state.orchestrator_service  # type: ignore[attr-defined]


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan hook.

    - Loads settings
    - Creates shared httpx.AsyncClients
    - Wires typed service clients + service layer
    - Closes resources on shutdown

    Returns:
      Async generator yielding None.
    """
    settings = Settings.load()

    # Shared concurrency guard across all upstream I/O
    http_sem = asyncio.Semaphore(settings.http_concurrency_limit)

    # Create per-service httpx clients. Timeout is on the httpx client.
    member_http = httpx.AsyncClient(base_url=settings.member_data_base_url, timeout=settings.http_timeout_seconds)
    pred_http = httpx.AsyncClient(base_url=settings.prediction_base_url, timeout=settings.http_timeout_seconds)
    offer_http = httpx.AsyncClient(base_url=settings.offer_base_url, timeout=settings.http_timeout_seconds)

    member_client = MemberDataClient(
        member_http,
        max_retries=settings.http_max_retries,
        backoff_seconds=settings.http_retry_backoff_seconds,
        semaphore=http_sem,
    )
    prediction_client = PredictionClient(
        pred_http,
        max_retries=settings.http_max_retries,
        backoff_seconds=settings.http_retry_backoff_seconds,
        semaphore=http_sem,
    )
    offer_client = OfferClient(
        offer_http,
        max_retries=settings.http_max_retries,
        backoff_seconds=settings.http_retry_backoff_seconds,
        semaphore=http_sem,
    )

    pred_fanout_sem = asyncio.Semaphore(min(20, settings.http_concurrency_limit))

    orchestrator_service = OrchestratorService(
        member_client=member_client,
        prediction_client=prediction_client,
        offer_client=offer_client,
        prediction_concurrency=pred_fanout_sem,
    )

    app.state.settings = settings
    app.state.orchestrator_service = orchestrator_service

    try:
        yield
    finally:
        await member_http.aclose()
        await pred_http.aclose()
        await offer_http.aclose()
