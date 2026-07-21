# Capability: Export + Caching

## What It Does
Caches repeated queries and exports answers to CSV/PDF for reports.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_hash | str | runtime | yes |
| export_format | enum["csv","md"] | UI button | no |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| cache_hit | bool | metrics |
| export_url | str | UI download |

## External Calls
- In-memory cache; DB-backed eviction in Phase 3.

## Business Rules
- Cache key is normalized SQL question + schema fingerprint.
- Export size hard-limited to 100k rows.

## Success Criteria
- [ ] Re-run identical question returns cached result with observed latency drop.
- [ ] Exportas CSV matches schema for heterogeneous types.
