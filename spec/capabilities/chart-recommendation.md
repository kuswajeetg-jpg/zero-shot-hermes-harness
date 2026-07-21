# Capability: Chart Metadata

## What It Does
Suggests chart types and encodings from result shapes for zero-build static renderer.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_result | QueryResult | prior node | yes |
| question | str | user input | yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| chart_spec | dict | UI renderer |

## External Calls
- LLM call for recommendation.

## Business Rules
- Bar chart default for categorical aggregates. Line chart default for time series. None if shape is arbitrary.
- Chart spec is descriptive only; any renderer failure degrades to table.

## Success Criteria
- [ ] Time series result returns line chart recommendation.
- [ ] Two-column categorical result returns bar chart recommendation.
- [ ] 20x20 arbitrary matrix returns `chart_spec=None` without error.
