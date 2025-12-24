from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse

from dotenv import load_dotenv


def _must_be_http_url(value: str, field: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{field} is required")
    u = urlparse(v)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError(f"{field} must be a valid http(s) URL, got: {value!r}")
    return v.rstrip("/")


@dataclass(frozen=True)
class Settings:
    """Application settings.

    Environment variables (optional):
      - MEMBER_DATA_BASE_URL
      - PREDICTION_BASE_URL
      - OFFER_BASE_URL
      - HTTP_TIMEOUT_SECONDS
      - HTTP_MAX_RETRIES
      - HTTP_RETRY_BACKOFF_SECONDS
      - HTTP_CONCURRENCY_LIMIT
      - REQUEST_ID_HEADER
    """

    member_data_base_url: str
    prediction_base_url: str
    offer_base_url: str

    http_timeout_seconds: float
    http_max_retries: int
    http_retry_backoff_seconds: float
    http_concurrency_limit: int

    request_id_header: str

    @staticmethod
    def load(env_file: str | None = ".env") -> "Settings":
        # Load local .env if present (no-op in prod)
        if env_file:
            load_dotenv(env_file, override=False)

        member_url = _must_be_http_url(
            os.getenv("MEMBER_DATA_BASE_URL", "http://localhost:8001"),
            "MEMBER_DATA_BASE_URL",
        )
        prediction_url = _must_be_http_url(
            os.getenv("PREDICTION_BASE_URL", "http://localhost:8002"),
            "PREDICTION_BASE_URL",
        )
        offer_url = _must_be_http_url(
            os.getenv("OFFER_BASE_URL", "http://localhost:8003"),
            "OFFER_BASE_URL",
        )

        timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5.0"))
        retries = int(os.getenv("HTTP_MAX_RETRIES", "2"))
        backoff = float(os.getenv("HTTP_RETRY_BACKOFF_SECONDS", "0.15"))
        concurrency = int(os.getenv("HTTP_CONCURRENCY_LIMIT", "50"))

        request_id_header = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")

        return Settings(
            member_data_base_url=member_url,
            prediction_base_url=prediction_url,
            offer_base_url=offer_url,
            http_timeout_seconds=timeout,
            http_max_retries=retries,
            http_retry_backoff_seconds=backoff,
            http_concurrency_limit=concurrency,
            request_id_header=request_id_header,
        )
