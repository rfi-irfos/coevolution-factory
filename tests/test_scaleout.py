"""Scale-out Task 1: batched Laura gate over staged candidates.

ONE Laura MCP call reviews all staged candidates and returns a {slug: bool}
pass-map. Falls back to per-candidate gate_candidate if Laura errors.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import daily_spawn as DS


def test_batch_gate_returns_passmap(monkeypatch):
    """One Laura call reviewing all staged candidates returns {slug: bool}.
    Fake Laura flags candidate 'b' only -> {a: True, b: False}."""
    cands = {
        "a": {"name": "A", "mandate": "x", "uncovered_signals": []},
        "b": {"name": "B", "mandate": "y", "uncovered_signals": []},
    }

    def fake(text, title, metadata, **kw):
        # ONE call carries the whole batch; return per-slug verdicts.
        rows = json.loads(text)
        return {
            "verdicts": {
                row["slug"]: {"flags": ["x"] if row["slug"] == "b" else []}
                for row in rows
            }
        }

    monkeypatch.setattr(DS, "mcp_laura_review_plan", fake)
    out = asyncio.run(DS.batch_gate_candidates(cands))
    assert out == {"a": True, "b": False}
