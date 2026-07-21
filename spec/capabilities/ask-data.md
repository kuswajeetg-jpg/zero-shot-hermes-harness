# Capability: Natural Language Questions

## What It Does
Translates analyst questions into a single safe read-only query or pandas pipeline against the active source and returns a formatted answer.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | UI chat input | yes |
| source_id | str | UI state | yes |
| source_type | enum["csv","mssql"] | UI state | yes |
| schema | list[SchemaColumn] | capability prior | yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| answer_text | str | UI message bubble |
| query_result | QueryResult | agent state |
| chart_spec | ChartSpec | UI renderer |

## External Calls
- Local OpenAI-compatible endpoint for intent/sql/answer generation. Template fallback if endpoint is unreachable.

## Business Rules
- Exactly one SELECT-class query per turn. No CTE with write intent. No `INTO OUTFILE`.
- Row limit enforced server-side; default 1000, max 5000 unless user override is explicit and justified.
- SQL generation uses parameterized queries when a primary-key filter is present.

## Success Criteria
- [ ] Happy-path test asks one aggregating question and asserts row count + value with real fixture >50k rows.
- [ ] Empty question returns 400 with validation error.
- [ ] PII-bearing table returns only aggregated/column-selected results; no raw PII row count in the prompt payload.
- [ ] A prompt-spy assertion confirms raw rows are absent from every LLM prompt.
- [ ] Disallowed SQL verb returns `query_result.failed=true` with human message, never 500.
