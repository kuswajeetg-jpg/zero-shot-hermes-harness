from src.graph.agent import agentic_ai
from src.graph.edges import after_transform


def test_graph_compiles_without_env():
    # compiled at import; nodes present
    assert agentic_ai is not None
    node_names = set(agentic_ai.get_graph().nodes)
    assert {"transform_text", "handle_error", "finalize"} <= node_names


def test_error_edge_routes_to_handler():
    assert after_transform({"error": "boom"}) == "handle_error"
    assert after_transform({"error": None}) == "finalize"


def test_transform_node_surfaces_missing_key_as_error(no_keys):
    """With no key, the node returns an actionable error — it never raises."""
    from src.graph.nodes import transform_text

    out = transform_text({"input_text": "hi", "instruction": "upper"})
    assert out["error"] is not None
    assert "AGENT_" in out["error"]  # actionable: names the env vars to set
