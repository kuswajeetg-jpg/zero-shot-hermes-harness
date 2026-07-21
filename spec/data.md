# Data Model

## Storage Technology

- **Metadata + auth + audit:** PostgreSQL via SQLAlchemy + Alembic.
- **CSV analytical engine:** pandas in-memory per run; uploads optionally persisted for session resume.
- **Live source:** pyodbc read-only sessions to MsSQL; no app-side cache on the police DB.
- **Exports:** object storage, 30-day retention.

## Entities

### Entity: User

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | uuid | yes | Primary key |
| email | str | yes | Login / identity |
| role | enum["user","admin"] | yes | RBAC |
| password_hash | str | yes | If password auth |
| sso_provider | str | no | SSO issuer |
| created_at | datetime | yes | Account creation |

### Entity: Session

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | uuid | yes | Primary key |
| user_id | uuid | yes | FK to user |
| source_type | enum["csv","mssql"] | yes | Active data source |
| source_config | json | yes | Redacted connection or file reference |
| created_at | datetime | yes | Session start |

### Entity: Upload

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | uuid | yes | Primary key |
| session_id | uuid | yes | FK to session |
| filename | str | yes | Original filename |
| schema | json | yes | Inferred schema with pii flags |
| rows | int | yes | Row count |
| storage_path | str | no | Persisted file path if retained |
| created_at | datetime | yes | Upload time |

### Entity: QueryRun

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | uuid | yes | Primary key |
| session_id | uuid | yes | FK to session |
| user_id | uuid | yes | FK to user |
| run_id | str | yes | LangGraph run id |
| question | str | yes | Analyst question |
| query_normalized | str | yes | Generated SQL or pandas expression |
| chart_spec | json | no | Optional chart metadata |
| context_summary | str | no | Conversation summary |
| fallback_mode | bool | no | Template vs LLM |
| latency_ms | int | no | Total pipeline latency |
| status | enum["completed","failed","timed_out"] | yes | Outcome |
| created_at | datetime | yes | Request time |

### Entity: QueryCache

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query_hash | str | yes | Primary key |
| result | json | yes | QueryResult envelope |
| schema_fingerprint | str | yes | Fast invalidation trigger |
| user_id | uuid | yes | Owner |
| created_at | datetime | yes | Cache time |

### Entity: Export

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | uuid | yes | Primary key |
| query_run_id | uuid | yes | FK to query_run |
| user_id | uuid | yes | Owner |
| format | enum["csv","md"] | yes | Export format |
| storage_path | str | yes | Object key |
| expires_at | datetime | yes | 30-day TTL |
| created_at | datetime | yes | Export time |

### Entity: AuditLog

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | uuid | yes | Primary key |
| user_id | uuid | yes | Actor |
| action | str | yes | question, sql, export, login, source_connect, etc. |
| target | str | no | session/source/query id |
| metadata | json | no | Redacted context |
| ip_fingerprint | str | no | For abuse detection |
| created_at | datetime | yes | Event time |

## Relationships

- User 1→N Session
- Session 1→N Upload
- Session 1→N QueryRun
- QueryRun optionally served from QueryCache by hash
- QueryRun 1→N Export
- AuditLog belongs to User by user_id

## Data Lifecycle

- Session and QueryRun rows are created at request time; never auto-deleted in Phase 1.
- Exports expire after 30 days; object lifecycle or cron job enforces deletion.
- QueryCache is LRU-bounded; oldest entries evicted when budget exceeded.

## Sensitive Data

- Passwords: bcrypt/argon2 hash only; raw values never stored.
- MsSQL credentials: managed by IT vault; app never stores raw secrets.
- PII columns: flagged at upload/source time; names redacted in audit logs and never included raw in LLM prompts.
- QueryRun stores the generated SQL/pandas expression; raw result rows are not persisted unless explicitly exported.
- All logs are scrubbed for column values that match PII flags.
