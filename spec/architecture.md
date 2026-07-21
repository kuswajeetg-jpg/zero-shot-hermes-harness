# Architecture

## System Overview

A self-hosted managed platform: single-org, multi-user, cloud or on-prem deployment. One FastAPI app serves the zero-build static frontend at `/app` and the JSON API. LangGraph orchestrates the analyst pipeline. PostgreSQL is the app metadata store; live MsSQL sources are accessed via read-only sessions. Object storage holds exports for 30 days.

## Components

- **API layer** — FastAPI routes with per-user auth, upload/ask/export/sources/connections.
- **Auth layer** — email/password or SSO-backed user accounts; JWT or session cookie; row-level scoping by user.
- **Agent pipeline** — LangGraph: intake → plan → execute read-only → chart → answer.
- **LLM provider** — Google Gemini `gemini-2.0-flash`; template fallback when key is missing or slow.
- **DB layer** — SQLAlchemy 2.x with PostgreSQL for metadata/audit; pyodbc read-only for live MsSQL.
- **Parser/guard** — read-only SQL parser against risky verbs/patterns before execution.
- **Cache** — in-memory LRU for query results by normalized question + schema fingerprint.
- **Audit** — structured stdout logs + DB audit rows for queries, LLM calls, exports, auth events.
- **Frontend** — zero-build static files served by FastAPI; fetch API calls same-origin.
- **Storage** — local filesystem or S3-compatible object storage for exports; 30-day retention.

## Data Flow

```
Authenticated User
  │
  ▼
 upload_csv / connect_vault_source / ask_question
  │
  ├─ CSV ──► ingest ──► schema_inspector ──► session state
  ├─ Vault source ──► IT-provisioned MsSQL connection ──► schema
  └─ question ──► plan_node ──► sql_pandas_generator ──► read-only executor
                          │
                          ├─ parser blocks risky SQL
                          ├─ timeout 30s → timed_out=true
                          └─ cache lookup/write
  ▼
answer + chart_spec + audit row
  ▼
Render UI + export path
```

## Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI + Uvicorn
- **Agent framework:** LangGraph
- **Live source DB:** MsSQL via pyodbc + ODBC 17+
- **CSV engine:** pandas 2.x
- **LLM:** Google Gemini API, `gemini-2.0-flash`
- **Auth:** email/password or SSO; JWT/session; row-level user scoping
- **Frontend:** zero-build static (`index.html` + `styles.css` + `app.js`) served by FastAPI
- **Observability:** structlog → stdout; DB audit table
- **Migrations:** Alembic for metadata schema
- **Testing:** pytest + TestClient
- **Package manager:** uv
- **Dependencies:**
  - baseline: fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, alembic, langgraph, httpx, structlog
  - add: pandas, pyodbc, python-jose[cryptography], passlib[bcrypt], python-multipart
- **Testing:** pytest + TestClient
- **Package manager:** uv
- **Deployment:** self-hosted managed platform (container, not SaaS)

## Phase-1 Pragmatic Note

Phase 1 ships with SQLite metadata for zero-config local use and same-driver tests. Phase 2 migrates to PostgreSQL when adding multi-user auth and vault-backed sources. This keeps first-time-right on a low-config system.

## Non-Functional Defaults

- **Auth:** email/password or SSO; per-user data isolation; admin role.
- **Read-only enforcement:** read-only DB principal + SQL parser blocking risky patterns.
- **LLM fallback:** template engine for common verbs; visible badge; no silent degradation.
- **Query timeout:** 30s hard limit; partial-safe failure surfaced to user.
- **Export retention:** 30 days in object storage; manual or admin delete anytime.
- **Audit:** every question, SQL, export, and auth event is logged; raw PII never logged.
- **Spend guardrails:** per-user daily token budget; soft warning + hard block at threshold; admin override.
- **Concurrency:** one active query per user; visible queue; hard queued timeout so UI never hangs.
- **Monitoring:** alerts on parser failures, timeout spikes, vault source failures, LLM error rate, storage capacity.
