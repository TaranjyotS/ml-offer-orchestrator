import csv
from typing import Dict, Any
from datetime import datetime, timezone
import httpx
import time

ORCHESTRATOR_URL = "http://localhost:8000/member/offer"
CSV_PATH = "member_data.csv"


def normalize_ts(ts: str) -> str:
    """Normalize timestamp to ISO-8601 with timezone.

    Accepts:
      - "YYYY-MM-DD HH:MM:SS"
      - ISO strings (with/without timezone)

    Raises:
      ValueError: if the timestamp is missing or invalid.
    """
    ts = (ts or "").strip()
    if not ts:
        raise ValueError("Missing lastTransactionUtcTs")

    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        # Fallback to CSV format: "YYYY-MM-DD HH:MM:SS"
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.isoformat()


def safe_float(value: Any, field_name: str) -> float:
    """Convert numeric fields safely.

    Raises:
      ValueError: if the value is missing/blank.
    """
    s = ("" if value is None else str(value)).strip()
    if not s:
        raise ValueError(f"Missing {field_name}")
    return float(s.replace(",", ""))


def parse_row(row: Dict[str, str]) -> Dict:
    """Convert CSV row into payload expected by /member/offer.

    Expected CSV columns:
      memberId, lastTransactionUtcTs, lastTransactionType,
      lastTransactionPointsBought, lastTransactionRevenueUSD

    Returns:
      dict: JSON payload for orchestrator

    Raises:
      ValueError: on missing required fields.
    """
    member_id = (row.get("memberId") or "").strip()
    ts = (row.get("lastTransactionUtcTs") or "").strip()
    tx_type = (row.get("lastTransactionType") or "").strip()

    if not member_id:
        raise ValueError("Missing memberId")
    if not ts:
        raise ValueError("Missing lastTransactionUtcTs")
    if not tx_type:
        raise ValueError("Missing lastTransactionType")

    return {
        "memberId": member_id,
        "lastTransactionUtcTs": normalize_ts(ts),
        "lastTransactionType": tx_type.upper(),
        "lastTransactionPointsBought": safe_float(row.get("lastTransactionPointsBought"), "lastTransactionPointsBought"),
        "lastTransactionRevenueUsd": safe_float(row.get("lastTransactionRevenueUSD"), "lastTransactionRevenueUSD"),
    }


def main():
    skipped = 0
    sent = 0
    failed = 0

    # Make timeouts explicit: orchestrator may legitimately take >5s with retries/backoff
    timeout = httpx.Timeout(
        30.0,     # overall default
        connect=5.0,
        read=30.0,
        write=10.0,
        pool=5.0,
    )

    MAX_RETRIES = 3
    BACKOFF_S = 0.5
    PACE_S = 0.02  # small pacing to avoid overwhelming local services

    with httpx.Client(timeout=timeout) as client, open(
        CSV_PATH, newline="", encoding="utf-8"
    ) as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, start=2):
            try:
                payload = parse_row(row)
            except ValueError as e:
                skipped += 1
                print(f"Skipping row {i}: {e} | memberId={row.get('memberId')}")
                continue

            attempt = 0
            while True:
                attempt += 1
                try:
                    resp = client.post(ORCHESTRATOR_URL, json=payload)

                    if resp.status_code == 422:
                        print("SENT PAYLOAD:", payload)
                        print("422 DETAIL:", resp.text)
                        return

                    # Retry transient upstream errors (optional but very practical)
                    if resp.status_code in (500, 502, 503, 504) and attempt <= MAX_RETRIES:
                        sleep_s = BACKOFF_S * (2 ** (attempt - 1))
                        print(f"[{resp.status_code}] row {i} attempt {attempt} -> retry in {sleep_s:.2f}s")
                        time.sleep(sleep_s)
                        continue

                    resp.raise_for_status()
                    sent += 1
                    print(resp.json())
                    break

                except httpx.ReadTimeout:
                    if attempt <= MAX_RETRIES:
                        sleep_s = BACKOFF_S * (2 ** (attempt - 1))
                        print(f"[TIMEOUT] row {i} attempt {attempt} -> retry in {sleep_s:.2f}s")
                        time.sleep(sleep_s)
                        continue
                    failed += 1
                    print(f"[FAIL] row {i}: ReadTimeout after {MAX_RETRIES} retries | memberId={payload.get('memberId')}")
                    break

                except httpx.HTTPError as e:
                    failed += 1
                    print(f"[FAIL] row {i}: {type(e).__name__}: {e}")
                    break

            time.sleep(PACE_S)

    print(f"Done. Sent={sent}, Skipped={skipped}, Failed={failed}")


if __name__ == "__main__":
    main()
