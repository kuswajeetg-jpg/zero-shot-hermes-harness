# UI

## UI Type

Web dashboard, single-page, served at `/app`. Zero-build static files with fetch API and auth flow.

## Views / Screens

### Screen: Login

**Purpose:** Email/password or SSO entry.

**Key elements:**
- Email + password form
- SSO button
- Error/loading states

**Actions available:**
- Login
- Register
- Forgot password

### Screen: Analyse

**Purpose:** One screen covers source selection, upload, schema, question, answer, and export.

**Key elements:**
- Source strip: upload zone + source chips (upload or vault-backed MsSQL).
- User/session header with logout.
- Schema card: column list with PII tags.
- Ask bar: text input with send button.
- Answer panel: answer text, data table, chart placeholder.
- Fallback badge: shows when template engine answers instead of LLM.
- Export buttons: CSV / Markdown; expiry shown.
- Queue indicator if user has another active query.

**Actions available:**
- Upload CSV
- Select vault-provisioned MsSQL source
- Submit question
- Export answer
- View own audit log
- Logout

## Error States

- Empty question → inline validation message
- Source missing → redirect with explanation
- LLM timeout/fallback → badge + partial answer or explanation
- DB timeout → explicit narrowing suggestion
- Auth expiry → redirect to login without data loss

## Tech Stack

Zero-build static files. Auth state via secure cookie or local token. Chart rendering via lightweight inline library or Canvas API if needed.
