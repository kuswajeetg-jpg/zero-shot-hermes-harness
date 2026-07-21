# Capability: CSV Upload + Schema Inference

## What It Does
Accepts multiple CSV uploads, validates headers/types, and exposes a typed schema with pii/secret flags for downstream query planning.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | UploadFile or dict | HTTP multipart / body | yes |
| session_id | str | cookie / header | yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| schema | list[SchemaColumn] | agent state + UI card |
| rows | int | agent state + UI card |
| pii_flags | list[str] | agent state |

## External Calls
None.

## Business Rules
- One file per request; UI allows sequential uploads.
- Headers lowercased + deduplicated; duplicate headers rejected with error.
- Columns containing keys like `aadhaar`, `mobile`, `phone`, `pan`, `password` are auto-flagged PII.

## Success Criteria
- [ ] Upload 50k-row CSV; schema returns in <2 seconds.
- [ ] Repeat headers produce 400 with field name.
- [ ] PII column names are redacted in every structured-log payload.
- [ ] Test fixture is large enough that sampled answer ≠ full answer.
