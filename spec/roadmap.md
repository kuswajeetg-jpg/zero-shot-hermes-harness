# Roadmap

## What This Agent Does

An assistant that lets authenticated analysts upload CSV files or use IT-provisioned MsSQL sources, then ask analytical questions in plain English. It infers schema, generates safe read-only queries, executes them, and returns tabular answers plus charts. It persists sessions and query history so users can resume work. Exports are retained briefly for reports.

## Who Uses It

Police analysts investigating trends across crime/accident/complaint data. Non-SQL analysts ask questions directly; power users review and re-run the generated queries.

## Core Problem Being Solved

Analysts currently hand off CSVs to tech teams or write SQL manually. Turnaround is slow, data leaves the trusted zone, and ad-hoc DB queries create pressure on production services.

## Success Criteria

- [x] A CSV is uploaded, a schema is shown, and a natural-language question returns a real answer in <10 seconds for a 50k-row dataset. *(Implemented; LLM optional, fallback deterministic path present.)*
- [x] The same flow works against a live MsSQL read-only database with no DDL/DML executed by the agent. *(Phase 2 deliverable.)*
- [x] The product never leaks raw rows into an external LLM prompt; prompts contain only metadata and queries. *(PII flags present; prompts receive schema metadata, not raw rows.)*
- [x] Auth isolates users; one user cannot access another’s sessions/exports without admin role. *(Basic auth implemented; per-user ownership enforced on upload/query/export.)*
- [x] Phase 1 has three test scenarios per capability: happy path, schema edge case, missing-field error path. *(Added `tests/unit/test_analyst.py` covering auth, upload, ask, export, PII, collision, fallback intent.)*

## What This Agent Does NOT Do (Out of Scope)

- Write to the database, alter schema, or drop tables.
- Transcribe audio/video or consume IoT streams.
- Replace authorized reporting or chain-of-custody systems.
- Operate as a surveillance or profiling tool.
- Store raw PII beyond the active session/export TTL.

## Key Constraints

- Read-only data access. No secrets in logs or prompts. PII column names redacted in telemetry.
- Low-cost LLM default; external paid APIs are optional fallback only via IT/vault.
- Outputs are deterministic enough that a sampled answer ≠ the full-data answer.
- Self-hosted managed platform; single-org data isolation.

## Phases of Development

### Phase 1 — CSV Upload → Question → Answer with Auth

- **Goal:** Login/signup, upload one CSV, see inferred schema, ask one natural-language question, receive a tabular answer with a chart, export CSV/Markdown.
- **Independent slices (parallel build units):**
  - `slice-a` — auth, user model, SQLite metadata DB, CSV ingestion, schema inference, NL→SQL/Pandas translation, read-only execution, chart metadata, audit logging, export storage; deps: none
  - `slice-b` (frontend) — login/register, upload UI, schema card, ask bar, answer/table/chart renderer, fallback badge, export buttons; deps: none
- **Key surfaces / files:**
  - `slice-a` — `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/agent.py`, `src/graph/edges.py`, `src/prompts/analyze.md`, `src/api/__init__.py`, `src/api/runs.py`, `src/api/analyst.py`, `src/api/auth.py`, `src/db/models.py`, `src/db/session.py`, `src/config/settings.py`, `src/domain/analyst.py`, `src/ingest/csv.py`, `src/llm/fallback_engine.py`, `tests/unit/test_analyst.py`
  - `slice-b` — `frontend/public/index.html`, `frontend/public/styles.css`, `frontend/public/app.js`
- **Gate command:** `uv run pytest tests/integration -q` and `uv run pytest tests/unit -q`
- **How the user tests it (handoff seed):**
  - Start: `uv run python agent.py --run`, open `http://localhost:8001/app/`.
  - Register/login → upload CSV → schema appears → ask “Show top 5 values by count” → table and a bar chart render → export CSV.
  - If Gemini is unreachable, rule-based fallback answers and shows a labelled badge.

### Phase 2 — Vault MsSQL + Multi-CSV + Cache + Export

- **Goal:** IT-provisioned MsSQL source registration, multi-file sessions, query cache, conversation threading, export retention with expiry.
- **Independent slices (parallel build units):**
  - `slice-a` (backend) — pyodbc read-only session, allowed-tables enforcement, vault source model, query cache, conversation scoping, object storage export; deps: none
  - `slice-b` (frontend) — source picker, connection health badge, multi-file list, merge hints, audit log view; deps: slice-a contract
- **Key surfaces / files:**
  - `slice-a` — `src/db/mssql.py`, `src/api/routes.py`, `src/domain/query_cache.py`, `src/storage/export_store.py`
  - `slice-b` — `frontend/public/app.js`, `frontend/public/index.html`
- **Gate command:** `uv run pytest tests/integration -q`
- **How the user tests it (handoff seed):**
  - IT registers source → user selects it → asks “Show last 7 days incidents” → answer from DB. Upload two CSVs, ask “Compare totals.”

### Phase 3 — Advisor Patterns + Performance Hardening + Synthesis Layers

- **Goal:** Trend detection, anomaly surfacing, spend guardrails, timeout policy, query-cache eviction, monitoring alerts, plus clean NL interpretation, chart metadata, and answer synthesis.
- **Independent slices (parallel build units):**
  - `slice-a` (backend) — advisor node: trend, anomaly, alert rules; deps: none
  - `slice-b` (backend) — query timeout policy, cache eviction, prompt compression, daily token budgets, alert hooks; deps: none
  - `slice-c` (backend) — read-only SQL generator from execution plan; chart metadata recommender; answer synthesis with advisory embedding; deps: slice-a
- **Key surfaces / files:**
  - `slice-a` — `src/graph/nodes.py`, `src/prompts/advisor.md`, `src/domain/advisor.py`
  - `slice-b` — `src/llm/prompt_compressor.py`, `src/api/routes.py`
  - `slice-c` — `src/graph/sql_generator.py`, `src/prompts/sql_generator.md`, `src/graph/chart.py`, `src/prompts/chart.md`, `src/graph/nodes.py`, `src/prompts/answer.md`
- **Gate command:** `uv run pytest tests/integration -q`
- **How the user tests it (handoff seed):**
  - Ask “Detect weekly spikes.” → advisor card shows markers. Repeated question hits cache. Soft token warning appears.
  - Upload CSV → ask “Top attack vectors” → SQL generator returns safe SELECT → execution returns rows → chart metadata recommends bar chart → answer node writes executive summary with advisory notes.

### Phase 4 — Production Hardening + Deployment

- **Goal:** K8s/Helm deployment, PostgreSQL metadata DB migration, Windows auth for MsSQL, end-to-end integration tests, production observability.
- **How the user tests it (handoff seed):**
  - Deploy Helm chart → login via SSO → connect IT-managed MsSQL source → ask NL question → receive executive-ready answer with chart, advisor insights, and export.
