# Capability: Live MsSQL Read-Only Source

## What It Does
Connects to a live MsSQL database using read-only credentials, introspects available tables, and executes parameterized queries with timeouts.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| connection_config | dict | UI connection form | yes |
| allowed_tables | list[str] | admin config | yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| schema_by_table | dict[str, list[SchemaColumn]] | agent state |
| connection_health | bool | UI badge |

## External Calls
- pyodbc read-only connection with `SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED` optional.
- All queries wrapped in 30-second timeout.

## Business Rules
- Allowed tables list is enforced before execution. No dynamic table wildcard.
- Credentials are never logged; connection string redacted in structured logs.
- `sp_` and extended-stored-procedure prefixes are blocked.

## Success Criteria
- [ ] Connection succeeds against local test MsSQL container and returns table metadata.
- [ ] Query against disallowed table returns explicit access-denied message.
- [ ] Long-running query triggers timeout with `timed_out=true` and partial-safe response.
