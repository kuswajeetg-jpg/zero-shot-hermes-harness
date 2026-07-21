# API

## API Style

REST + multipart/form-data uploads. SPA at `/app`. Per-request auth via cookie or Authorization header.

## Authentication

Email/password or SSO. Protected endpoints require a valid session/JWT. Row-level scoping: users see only their own sessions/uploads/query runs unless role=admin.

## Endpoints / Commands

### `POST /api/auth/register`

**Purpose:** Create user account.

**Request:**
```json
{"email": "str", "password": "str"}
```

**Response:**
```json
{"user_id": "uuid", "email": "str"}
```

### `POST /api/auth/login`

**Purpose:** Issue session/JWT.

**Request:**
```json
{"email": "str", "password": "str"}
```

**Response:**
```json
{"access_token": "str", "token_type": "bearer"}
```

### `POST /api/upload`

**Purpose:** Accept one CSV, infer schema, persist upload.

**Request:** multipart/form-data `file` + `session_token`

**Response:**
```json
{"upload_id": "uuid", "schema": [{"name": "str", "type": "str", "pii": "bool"}], "rows": "int", "warnings": ["str"]}
```

### `POST /api/ask`

**Purpose:** Submit analyst question for one active source.

**Request:**
```json
{"session_token": "str", "source_id": "str", "question": "str"}
```

**Response:**
```json
{"run_id": "uuid", "answer_text": "str", "query_result": {"columns": ["str"], "rows": [{}], "timed_out": "bool"}, "chart_spec": {"type": "str", "encoding": {}}, "fallback_mode": "bool", "latency_ms": "int"}
```

### `GET /api/sessions`

**Purpose:** List current user’s sessions.

### `POST /api/sessions`

**Purpose:** Create a new analysis session tied to a source.

### `POST /api/connect/vault`

**Purpose:** Register an IT-provisioned MsSQL source for the current user.

**Request:**
```json
{"source_id": "str", "display_name": "str", "allowed_tables": ["str"]}
```

**Response:**
```json
{"source_id": "str", "connection_health": "bool", "tables": [{"name": "str", "schema": []}]}
```

**Note:** No password/connection-string fields. Vault linkage only.

### `POST /api/export`

**Purpose:** Export last query result to CSV or Markdown with 30-day retention.

**Request:**
```json
{"query_run_id": "uuid", "format": "enum[csv,md]"}
```

**Response:**
```json
{"export_id": "uuid", "url": "str", "expires_at": "datetime"}
```

### `GET /api/audit/me`

**Purpose:** Current user’s audit events.

**Error cases:**

| Status | Condition |
|--------|-----------|
| 401 | Missing/invalid auth |
| 403 | Admin-only endpoint |
| 404 | Source/session missing |
| 422 | Duplicate headers, bad encoding |
| 500 | Pipeline failure with human-readable message |
