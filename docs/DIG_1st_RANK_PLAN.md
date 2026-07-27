# DIG Technical 1st Rank Plan — UP Police Analytics Agent

## Competition reality
- ~1,000 participants submitting similar agents.
- Evaluator: IPS Officer (DIG Technical). Evaluation criteria: **usefulness, relevance, accuracy, speed, robustness**.
- Rejection reason: “totally waste of time,” “not providing useful/related information,” “charts/details meaningless.”

## Winning formula
1. **First 10 seconds matter most:** show real police insight immediately after upload, before the evaluator can get bored.
2. **Never show fake/placeholder data:** empty results → show empty state with schema, never `Region North`.
3. **Every section must be police-domain first:** district/zone concentration, crime type leadership, disposal delay, charge-sheet rate, property recovery, Mahila caseload.
4. **Schema-agnostic guarantee:** any police CSV in India (UP format, NCRB format, state-specific format, future formats) must work without code changes.
5. **Zero external dependency risk:** if LLM API key is missing/expired, rule-based fallback must still produce domain insights in <10s.

## What changed vs rejected version

| Before rejection | After 1st-rank plan |
|---|---|
| Fake fallback rows on empty query | Real-data-only; empty rows shown with explicit “No data” state |
| Hardcoded Quick-Ask pills (City/Salary/Age) | Schema-aware pills generated from actual uploaded columns |
| Advisor often null | Always-on executive briefing panel with 6 police KPIs |
| Charts ignore asked dimension | Question keyword → metric/axis binding; charts reflect asked dimension |
| Multi-file upload corrupted | Unique storage paths per upload; collision-free |
| No export | Backend-first CSV/Markdown export with client fallback |
| Generic analytics language | Police-domain phrasing: district concentration, charge-sheet rate, disposal delay |

## Demo script for DIG Technical (2 minutes)

### Step 1 — Upload (30s)
```
Upload 3 files at once:
  dummy_police_fir_data_2000.csv
  final_reports (1).csv
  fir_registrations.csv
```
**What to point out:** “Multi-file ingestion with unique storage; no overwrite even if filenames collide.”

### Step 2 — Executive Briefing (20s)
**What to point out:** “Agent auto-generates 6 police KPIs from schema, no prompts needed:”
- Highest caseload district / PS
- Leading crime type by share
- Charge-sheet rate %
- Property recovery rate %
- Mahila Thana load %
- Avg disposal delay + coverage period

### Step 3 — Quick-Ask pills (20s)
**What to point out:** “Pills derive from live schema, not hardcoded. Click any pill → immediate answer + chart + structured table.”

### Step 4 — Ask a police question (30s)
```
Question: “Show disposal delay and charge sheet rate by district”
```
**What to point out:** “Answer uses asked dimension (district), not generic default. Chart type chosen by intent. No fake rows.”

### Step 5 — Export for daily briefing (20s)
**What to point out:** “One-click Markdown report for daily briefing; works even if LLM key is missing because fallback is rule-based.”

## Competitive differentiation (why this wins)

| Factor | Most participants | This agent |
|---|---|---|
| Empty-result behavior | Fake rows or blank screen | Explicit empty state with schema + export |
| Multi-file upload | Overwrite or fail | Unique paths; collision-free |
| Advisor insights | Generic “no notable anomalies” | Police KPIs: charge-sheet rate, disposal delay, etc. |
| Fallback without API key | Crashes or meaningless charts | Rule-based + keyword axes + police-domain grouping |
| Frontend binding | Hardcoded pills | Schema-aware pills + executive briefing card |
| Export | Missing | Backend-first CSV/MD export |
| Test coverage | Manual | Live regression 0 issues + 33 unit tests |
| Data scale performance | Not demonstrated | DuckDB in-memory; handles 20MB+ instantly |

## Technical safeguards for live demo

### Before demo
```bash
cd D:\zero-shot-hermes-harness\zero-shot-hermes-harness
netstat -ano | grep ':8001' | awk '{print $NF}' | sort -u | xargs -r taskkill /F 2>/dev/null
uv run python -m src
```

### Health check
```bash
curl -s http://localhost:8001/health
# Must return: {"status":"ok","provider":"stub","model":"rule-based_fallback"}
```

### Regression gate
```bash
uv run pytest tests/unit -q
uv run python tests/live_dashboard_regression.py
# Must show: 33 passed, 0 failed; 0 issues
```

### Data hygiene
- Sample datasets live in `Sample data/` (never delete).
- Uploaded CSVs go to `data/uploads/` with unique names.
- No hardcoded schema anywhere in backend or frontend.

## Risk mitigation

| Risk | Mitigation |
|---|---|
| Server not running at demo time | Pre-start script + health check |
| Port 8001 conflict | Kill script before start |
| LLM API key expired | Default to stub/rule-based fallback; agent still produces police insights |
| Browser cache stale | Hard refresh or incognito |
| Large file (>100MB) | Backend rejects with clear message |
| Unexpected column names | Keyword bias + generic fallback still works |

## Why this is 1st-rank material
1. **Immediate value:** 10s from upload to insight.
2. **Zero configuration:** works on any police CSV without schema mapping.
3. **Police-domain language:** officer sees district, charge-sheet, disposal delay — not generic “average by category.”
4. **Robustness:** unit tests + live regression + multi-file test + export test all green.
5. **Production-ready:** export, multi-file, schema-aware pills, advisor, real-data-only.

## Submission checklist
- [ ] Run `uv run pytest tests/unit -q` → 33 passed
- [ ] Run `uv run python tests/live_dashboard_regression.py` → 0 issues
- [ ] Start server: `uv run python -m src`
- [ ] Health check: `curl http://localhost:8001/health` → `status=ok`
- [ ] Upload 3 sample files, verify Executive Briefing appears
- [ ] Verify Quick-Ask pills match uploaded schema
- [ ] Ask 1 police question, verify answer/chart/table all use asked dimension
- [ ] Verify export button exists and returns file
- [ ] Screenshot Executive Briefing + Quick-Ask + answer panel for submission form
