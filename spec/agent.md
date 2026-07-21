# Agent

## Agent Architecture Pattern

> **Assumed:** Single-agent loop with conditional tool-use nodes is enough for this product. Multi-agent router is unnecessary because the analyst flow is serial: parse → plan → execute → visualize.

| Pattern | Use when |
|---------|----------|
| Single-agent loop | One LLM drives a deterministic tool-call loop. |
| Graph (LangGraph) | Multi-step pipeline with conditional edges. |
| Multi-agent | Specialized sub-agents with distinct roles. |
| Supervisor | One dispatches to workers. |
| Human-in-the-loop | Execution pauses for user review. |

**Chosen:** Graph (LangGraph). This project has a multi-step analyst pipeline with conditional branches: schema-aware planning, read-only execution guard, optional charting path.

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|--------------|----------|----------|-----------|
| `plan_node` | Google Gemini | `gemini-2.0-flash` | Low latency, low cost, strong instruction following |
| `sql_generator` | Google Gemini | `gemini-2.0-flash` | Single call per question; cost-efficient |
| `answer_node` | Google Gemini | `gemini-2.0-flash` | Summarization + chart guidance |

**Fallback behaviour:** If the Gemini API is unreachable or rate-limited, a deterministic template engine handles common analyst questions (top-N, counts, averages, trends) without raising an exception. Errors and fallback mode are surfaced in the UI via a badge.

**Prompt strategy:** System prompts per node, one JSON tool-call intent per LLM call. Output schema enforced with Pydantic. No prompt includes raw row values.

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `inspect_schema` | Introspect uploaded CSV or DB table metadata | `source_id`, optional `table_name` | Column list, types, pii flags | DB metadata query |
| `execute_query` | Run one read-only query against the current source | `sql_or_pandas_expr`, `source_id`, `limit` | `rows`, `columns`, `timed_out` | Read-only resultset |
| `generate_chart` | Produce chart metadata for renderer | `query_result`, `chart_type` | `chart_spec` | None |
| `append_history` | Persist/reload conversation state | `run_id`, `turn` | `context_summary` | DB read/write |

**Tool selection strategy:** LLM chooses tool by intent token in a constrained JSON response. Fallback path uses a router table for known verbs: `top`, `count`, `average`, `compare`, `trend`.

**Tool failure handling:** Failures raise a tool_result with `error`. The graph routes to `answer_node` with a human-readable explanation. DB timeouts raise a partial result with `timed_out=true`; the answer node reports truncated output explicitly.

## Agent State

```python
class AgentState(TypedDict):
    # Identity
    run_id: int                          # set at initialisation

    # Input
    user_message: str                    # raw question
    source_id: str                       # uploaded file or live DB source identifier

    # Pipeline data
    schema: list[dict[str, str]]         # columns + types + pii flag
    plan: dict | None                   # chosen tool, filters, group-bys
    query_result: dict | None            # rows + columns + elapsed_ms
    chart_spec: dict | None             # chart type + encodings
    history: list[dict]                 # prior turns for context threading

    # Output
    answer_text: str | None
    error: str | None                    # surface error for UI
    checkpoint: str | None              # last completed node
```

## Nodes / Steps

### `intake_node`

**Reads from state:** `user_message`, `source_id`
**Writes to state:** `checkpoint`
**LLM call:** No
**External calls:** schema cache lookup
**Behaviour:** Validates the source exists; if schema is missing, returns a structured “Provide data” message and stops the graph early.

### `plan_node`

**Reads from state:** `user_message`, `schema`
**Writes to state:** `plan`
**LLM call:** Yes. Prompt summary: classify intent, select tool, identify target columns.
**External calls:** None
**Behaviour:** Maps plain-English needs to one structured plan. On failure, routes to `answer_node` with “I didn’t understand — try simpler phrasing.”

### `execute_read_only`

**Reads from state:** `plan`, `source_id`
**Writes to state:** `query_result`
**LLM call:** No
**External calls:** `inspect_schema`, `execute_query`
**On Failure:** Fatal error set; route to `answer_node` with error message.
**Behaviour:** Executes exactly one read-only query. Pandas backend for CSVs; SQL Server via pyodbc read-only session for live DB. Hard limit on rows returned.

### `chart_node`

**Reads from state:** `query_result`, `plan`
**Writes to state:** `chart_spec`
**LLM call:** Yes. Prompt summary: given result shape, recommend chart type.
**External calls:** None
**Behaviour:** Produces JSON chart spec. If result shape is unsuitable, returns `chart_spec=None`.

### `answer_node`

**Reads from state:** `query_result`, `chart_spec`, `error`
**Writes to state:** `answer_text`, `checkpoint`
**LLM call:** Yes. Prompt summary: format answer + embed chart spec in a machine-readable envelope.
**External calls:** `append_history`
**Behaviour:** Final natural-language answer for UI render.

### `handle_error`

**Reads from state:** `error`, `run_id`
**Writes to state:** `answer_text`, `checkpoint`
**External calls:** structured log with run_id
**Behaviour:** Maps fatal errors to readable messages. Terminates graph.

## Graph / Flow Topology

```
START
  │
  ▼
intake_node
  ├─(source missing)──► answer_node(provide_data)
  │
  ▼
plan_node
  ├─(error)──► answer_node(plan_failed)
  │
  ▼
execute_read_only
  ├─(error)──► answer_node(query_failed)
  │
  ▼
chart_node
  ▼
answer_node
  │
  ▼
END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `intake_node` | `source_id` invalid | `answer_node` |
| `plan_node` | `plan is None or error` | `answer_node` |
| `execute_read_only` | `query_result is None or error` | `answer_node` |

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | All in-progress data |
| **Across runs** | DB query result cache | Last query result by hash |
| **Conversation** | Domain `history` row | Turn summary |

**Context window management:** Schema and plan are the only structured payloads into the prompt. Result rows are never included in prompts. Histories are summarized before inclusion.

## Human-in-the-Loop Checkpoints

> **Assumed:** Not required for Phase 1. Future phase may add query preview approval for power users.

## Error Handling & Recovery

- Node-level: every node catches exceptions and routes to `answer_node` with a human-readable message.
- `handle_error` node is unnecessary in the current happy-path graph because errors are absorbed at each node, but retained in pseudocode in case future nodes need centralized failure handling.

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One trace per run, one span per node | stdlog |
| **LLM calls** | Prompt size, latency, fallback mode | structured log |
| **Tool calls** | Tool name, source_id, row count, timeout flag | structured log |
| **Run outcome** | Status, total duration, fallback mode | DB + structured log |

## Concurrency Model

- **Run isolation:** run_id-scoped reads. Warming cache is atomic by key hash.
- **Parallel nodes within a run:** none in Phase 1. Future phase may parallelize schema lookup + advisor.
- **Checkpointing:** none required. State is small and entirely in-memory within a run.

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)

graph.add_node("intake_node", intake_node)
graph.add_node("plan_node", plan_node)
graph.add_node("execute_read_only", execute_read_only)
graph.add_node("chart_node", chart_node)
graph.add_node("answer_node", answer_node)

graph.set_entry_point("intake_node")
graph.add_edge("intake_node", "plan_node")
graph.add_conditional_edges("plan_node", route_plan, {"ok": "execute_read_only", "fail": "answer_node"})
graph.add_conditional_edges("execute_read_only", route_execute, {"ok": "chart_node", "fail": "answer_node"})
graph.add_edge("chart_node", "answer_node")
graph.add_edge("answer_node", END)

compiled_graph = graph.compile()
```
