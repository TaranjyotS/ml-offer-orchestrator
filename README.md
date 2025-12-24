A production-style **FastAPI-based orchestration service** demonstrating dependency injection, retries, concurrency control, observability, and distributed system patterns, calls external **ML prediction** services, and assigns an offer via an offer engine.

The services under **src/applications/** are intentionally treated as external systems (per the assignment) and are accessed over HTTP.
---

## What the system does

For each incoming transaction (from `member_data.csv`):

1. **Ingest** a transaction (streamed from CSV)
2. **Validate** input at schema and domain levels
3. **Fetch** the member’s historical transactions from the `member_data` service
4. **Compute** a deterministic feature vector from history + current transaction
5. **Predict** (in parallel):
  - ATS prediction (expected volume)
  - RESP prediction (response probability)
6. **Assign** an offer via the `offer_engine`
7. **Persist** the current transaction back to `member_data`
8. **Return** the selected offer with a correlation `ID`

---

## Services and ports

|    Service   |                 Module                  | Port |               Purpose                |
|--------------|-----------------------------------------|------|--------------------------------------|
| Orchestrator | `src.orchestrator.orchestrator_app:app` | 8000 | Main API: `/member/offer`            |
| Member Data  | `src.applications.member_data:app`      | 8001 | History store: GET/POST transactions |
| Prediction   | `src.applications.prediction:app`       | 8002 | ML-like endpoints: ATS / RESP        |
| Offer Engine | `src.applications.offer_engine:app`     | 8003 | Assigns an offer from predictions    |

Health checks are available on `GET /health` for each service.
---

## Setup

### Install dependencies

```bash
pip install -r requirements.txt
```

> Note: `requirements.txt` includes test dependencies (`pytest`, `pytest-cov`, `pytest-asyncio`, `respx`) so CI and local runs work out of the box.

---

## Run the application

Open **4 terminals** (or use the VS Code launch configuration described below).

### Terminal 1 – Member Data

```bash
uvicorn src.applications.member_data:app --port 8001 --reload
```

### Terminal 2 – Prediction service

```bash
uvicorn src.applications.prediction:app --port 8002 --reload
```

### Terminal 3 – Offer Engine

```bash
uvicorn src.applications.offer_engine:app --port 8003 --reload
```

### Terminal 4 – Orchestrator (main API)

```bash
uvicorn src.orchestrator.orchestrator_app:app --port 8000 --reload
```

---

## Stream the CSV data into the system

Once all 4 services are running:

```bash
python stream_member_data.py
```

What you’ll see:
- The streamer prints the orchestrator response per row (the selected offer).
- Malformed CSV rows (missing required fields) are **skipped** with a short log line, so the stream keeps running (typical production ingestion behavior).

---

## API contract

### POST `/member/offer` (Orchestrator)

Request body:

```json
{
  "memberId": "A0F18FAA",
  "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
  "lastTransactionType": "GIFT",
  "lastTransactionPointsBought": 500.0,
  "lastTransactionRevenueUsd": 2.5
}
```

Response body:

```json
{
  "memberId": "A0F18FAA",
  "offer": "OFFER_A"
}
```
---

## Error Handling

The orchestrator handles errors from upstream services and invalid requests as follows:

| Scenario                            | HTTP Response            |
| ----------------------------------- | ------------------------ |
| Invalid request / domain validation | 422                      |
| Member history not found            | Treated as empty history |
| Upstream timeout / network failure  | 504                      |
| Upstream service failure            | 502                      |
| Unexpected orchestrator error       | 500                      |

---

## Tests

The `tests/` folder contains a mix of unit and integration-style tests:

### Unit tests
- Feature computation (`test_member_features.py`)
- Member data client parsing + resilience (`test_clients_member_data.py`)
- CSV parsing/validation for ingestion (`test_stream_member_data.py`)

### Integration tests
- Orchestrator happy path + FastAPI validation (`test_orchestrator_offer.py`)
- Orchestrator failure paths mapped to stable API errors (`test_orchestrator_failure_paths.py`)
- Health endpoint coverage (`test_health_endpoints.py`)

### Production tests
- Correlation / request-id propagation (`test_request_correlation.py`)
- Retry behavior for transient upstream failures (`test_retry_behavior.py`)
- Contract assertions + best-effort persistence (`test_contracts_and_best_effort.py`)

Run:

```bash
pytest -q
```

---

## CI/CD

The project can be validated using a **local Jenkins pipeline** running on Windows.

### Prerequisites
- Windows
- Python installed (same version used locally)
- Docker Desktop installed and running
- Java 17 installed on Windows (for the Jenkins agent)

### Start Jenkins (Docker)

```bash
docker run -d --name jenkins-local -p 8080:8080 -p 50000:50000 jenkins/jenkins:lts

---

## Project layout

```
.
├─ src/
│  ├─ orchestrator/          # orchestrator API, DI, services, middleware
│  ├─ clients/               # reusable HTTP clients + retry logic
│  ├─ features/              # feature computation
│  └─ applications/          # external services
├─ tests/                    # unit + integration + resilience tests
├─ member_data.csv           # input data
├─ stream_member_data.py     # CSV ingestion script
├─ requirements.txt
├─ Jenkinsfile
├─ GUIDELINES.md
└─ README.md
```
