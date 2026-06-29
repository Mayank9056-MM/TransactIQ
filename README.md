# TransactIQ

An asynchronous financial transaction processing pipeline. Upload a raw CSV, get back cleaned transactions, detected anomalies, AI-generated categories, and a structured spending report — all processed in the background.

Built with **FastAPI · PostgreSQL · Celery · Redis · Google Gemini · Docker**.

---
 
## Table of Contents
 
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Processing Pipeline](#processing-pipeline)
- [Data Model](#data-model)
- [Example curl Requests](#example-curl-requests)
- [Design Decisions](#design-decisions)
---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │               Docker Network             │
                    │                                         │
  HTTP Request      │  ┌──────────┐     ┌─────────────────┐  │
 ──────────────────►│  │  FastAPI  │────►│     Redis       │  │
                    │  │  :8000   │     │  (Task Queue)   │  │
                    │  └────┬─────┘     └────────┬────────┘  │
                    │       │                    │            │
                    │       ▼                    ▼            │
                    │  ┌──────────┐     ┌─────────────────┐  │
                    │  │ PostgreSQL│◄────│  Celery Worker  │  │
                    │  │  :5432   │     │  (Processing)   │  │
                    │  └──────────┘     └────────┬────────┘  │
                    │                            │            │
                    └────────────────────────────┼────────────┘
                                                 │
                                                 ▼
                                      ┌─────────────────────┐
                                      │   Google Gemini API  │
                                      │  (Classification +  │
                                      │     Narrative)      │
                                      └─────────────────────┘
```

### Request Lifecycle
 
1. Client `POST /jobs/upload` with a CSV file
2. FastAPI validates columns, saves the file to a shared Docker volume, creates a `Job` record in PostgreSQL (`status=pending`), and returns a `job_id` immediately
3. The job ID is pushed onto the Redis queue via Celery
4. The Celery worker picks up the task, runs the full pipeline (clean → detect → classify → summarise), and writes results back to PostgreSQL
5. Client polls `GET /jobs/{job_id}/status` until `completed`
6. Client calls `GET /jobs/{job_id}/results` to retrieve the full structured output
---

## Tech Stack
 
| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic |
| Validation | Pydantic v2 |
| Database | PostgreSQL 16 |
| Task Queue | Celery 5 + Redis 7 |
| Data Processing | Pandas |
| LLM | Google Gemini 1.5 Flash |
| Containerisation | Docker + Docker Compose |
| Package Manager | uv |
 
---

## Project Structure
 
```
transactiq/
├── app/
│   ├── api/
│   │   ├── deps.py              # DB session dependency
│   │   └── routes/
│   │       └── jobs.py          # All job endpoints
│   ├── core/
│   │   └── config.py            # Pydantic settings
│   ├── db/
│   │   └── database.py          # Engine, session factory, Base
│   ├── models/
│   │   ├── job.py               # Job ORM model + JobStatus enum
│   │   ├── transaction.py       # Transaction ORM model
│   │   └── job_summary.py       # JobSummary ORM model
│   ├── schemas/
│   │   ├── job.py               # Request/response schemas
│   │   ├── transaction.py
│   │   ├── job_summary.py
│   │   └── results.py           # Full results response schema
│   ├── services/
│   │   ├── csv_processor.py     # Cleaning + normalisation
│   │   ├── anomaly_detector.py  # Statistical + rule-based flagging
│   │   └── llm_service.py       # Gemini calls with retry logic
│   ├── workers/
│   │   ├── celery_app.py        # Celery configuration
│   │   └── tasks.py             # process_job task
│   └── main.py                  # FastAPI app + lifespan
├── migrations/                  # Alembic migration scripts
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```
 
---


## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- A free Google Gemini API key — get one at [aistudio.google.com](https://aistudio.google.com/)

### 1. Clone the repository

```bash
git clone https://github.com/Mayank9056-MM/TransactIQ
cd TransactIQ
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set your Gemini key:
 
```dotenv
DATABASE_URL=postgresql+psycopg://transactiq:transactiq@db:5432/transactiq
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
UPLOAD_DIR=/app/uploads
```

### 3. Start all services
 
```bash
docker compose up --build
```

This starts four containers: `api`, `worker`, `db`, `redis`.

### 4. Run database migrations

```bash
docker compose exec api uv run alembic upgrade head
```

### 5. Open the docs

```
http://localhost:8000/docs
```

## Environment Variables
 
| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://transactiq:transactiq@db:5432/transactiq` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `GEMINI_API_KEY` | Google Gemini API key | *(required)* |
| `GEMINI_MODEL` | Gemini model name | `gemini-1.5-flash` |
| `UPLOAD_DIR` | Path inside container for CSV uploads | `/app/uploads` |
 
---

## API Reference

### `POST /jobs/upload`
 
Upload a CSV file and enqueue a processing job. Returns immediately with a `job_id`.
 
**Request:** `multipart/form-data` with field `file` (`.csv` only)
 
**Response `202`:**
```json
{
  "job_id": 1,
  "status": "pending",
  "filename": "transactions.csv"
}
```
 
**Validation errors:** missing required columns → `422`, empty file → `400`, non-CSV → `400`
 
---

### `GET /jobs/{job_id}/status`
 
Poll the status of a job.
 
**Response `200`:**
```json
{
  "job_id": 1,
  "status": "completed",
  "summary": {
    "row_count_clean": 87,
    "total_spend_inr": 142300.50,
    "total_spend_usd": 240.00,
    "anomaly_count": 4,
    "risk_level": "medium"
  }
}
```
 
`summary` is `null` while the job is `pending` or `processing`.
 
**Status values:** `pending` → `processing` → `completed` | `failed`
 
---
 
 ### `GET /jobs/{job_id}/results`
 
Retrieve the full output of a completed job. Returns `409` if the job is not yet completed.
 
**Response `200`:**
```json
{
  "job_id": 1,
  "row_count_raw": 92,
  "row_count_clean": 87,
  "transactions": [ ... ],
  "anomalies": [ ... ],
  "category_breakdown": {
    "Food": { "total_amount": 12400.00, "transaction_count": 18 },
    "Transport": { "total_amount": 4300.00, "transaction_count": 9 }
  },
  "summary": {
    "total_spend_inr": 142300.50,
    "total_spend_usd": 240.00,
    "top_merchants": {
      "Swiggy": 8400.00,
      "Amazon": 22100.00,
      "Uber": 3200.00
    },
    "anomaly_count": 4,
    "narrative": "Spending was concentrated in Shopping and Food categories...",
    "risk_level": "medium"
  }
}
```
 
---

### `GET /jobs`
 
List all jobs ordered by creation time. Supports filtering.
 
**Query params:** `?status=pending|processing|completed|failed`
 
**Response `200`:**
```json
[
  {
    "id": 1,
    "filename": "transactions.csv",
    "status": "completed",
    "row_count_raw": 92,
    "created_at": "2025-01-15T10:30:00Z"
  }
]
```
 
---

## Example curl Requests
 
**Upload a CSV:**
```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "file=@Backend_DevOps_Assignment/transactions.csv"
```
 
**Poll status:**
```bash
curl http://localhost:8000/jobs/1/status
```
 
**Get full results:**
```bash
curl http://localhost:8000/jobs/1/results | python3 -m json.tool
```
 
**List all completed jobs:**
```bash
curl "http://localhost:8000/jobs?status=completed"
```
 
**Health check:**
```bash
curl http://localhost:8000/health
```
 
---

## Processing Pipeline

When a job is dequeued by the Celery worker, the following steps execute in order:

### 1. Data Cleaning

| Raw Problem | Fix Applied |
|---|---|
| Mixed date formats (`DD-MM-YYYY`, `YYYY/MM/DD`) | Normalised to `YYYY-MM-DD` (ISO 8601) |
| Currency symbols (`$1,200`) | Stripped, coerced to `float` |
| Inconsistent casing (`inr`, `success`) | Uppercased |
| Blank `category` | Filled with `Uncategorised` |
| Blank `txn_id` | Kept as `null` |
| Exact duplicate rows | Removed |
| Unrecoverable rows (no date, amount, or merchant) | Dropped |
 
### 2. Anomaly Detection
 
Two rule-based checks run across every cleaned transaction:
 
- **Statistical outlier** — amount exceeds 3× the median for that `account_id`
- **Currency mismatch** — a domestic-only merchant (Swiggy, Ola, IRCTC, Zomato, etc.) is charged in USD
Flagged rows get `is_anomaly=true` and a human-readable `anomaly_reason`.
 
### 3. LLM Classification
 
Uncategorised transactions are sent to Gemini in a single batch call (not one call per row). The model assigns one of: `Food`, `Shopping`, `Travel`, `Transport`, `Utilities`, `Cash Withdrawal`, `Entertainment`, or `Other`.
 
Failed LLM calls are retried up to **3 times with exponential backoff** (1 s, 2 s, 4 s). If all retries fail, the batch is marked `llm_failed=true` and the pipeline continues — the job itself is never failed due to an LLM error.
 
### 4. Narrative Summary
 
A single LLM call generates a structured JSON report containing total spend by currency, top 3 merchants, anomaly count, a 2–3 sentence spending narrative, and a `risk_level` of `low` / `medium` / `high`.
 
If this call fails, a fallback summary is computed directly from the data.
 
---

## Data Model
 
```
Job
├── id, filename, file_path
├── status (pending | processing | completed | failed)
├── row_count_raw, row_count_clean
├── error_message
└── created_at, completed_at
 
Transaction (FK → Job)
├── txn_id, date, merchant, amount, currency
├── status, category, account_id, notes
├── is_anomaly, anomaly_reason
└── llm_category, llm_raw_response, llm_failed
 
JobSummary (FK → Job, one-to-one)
├── total_spend_inr, total_spend_usd
├── top_merchants (JSON)
├── anomaly_count
├── narrative
└── risk_level
```
 
---