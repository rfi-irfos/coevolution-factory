#!/usr/bin/env python3
"""Local Laura ship-gate CLIENT for the CoEvolution Factory.

Replaces the Hermes-MCP `mcp_laura_review_plan` bridge with a DIRECT call to
our own Laura API on Fly (https://laura-api.fly.dev). The API exposes a
keyless MCP-JSON-RPC endpoint (`/mcp`) that runs the exact same deterministic
4-lens review logic as the MCP tool — fully synchronous, local computation,
no external cost. We own the infrastructure, so the Babies call Laura directly
instead of through an agent-only proxy. This removes the single point of
failure (no dependency on the local Hermes client / Simeon's machine).

Return shape mirrors what the old `mcp_laura_review_plan` callers expect:
    {"result": {"lenses": [ {"name":..., "findings":[{"severity":"flag",...}]}, ... ]}}
and a convenience `flags` count is surfaced too.

Doctrine preserved: this is STILL Laura's gate. We are not inventing review
logic — we call Laura's own published engine. If the API is unreachable we
refuse to self-approve (return blocked), exactly like the old bridge did.
"""
import json
import urllib.request
import os

LAURA_API_URL = os.environ.get(
    "LAURA_API_URL", "https://laura-api.fly.dev/mcp"
)
# Timeout kept short so a downed API fails fast and the caller blocks
# honestly instead of hanging the cron.
_TIMEOUT = int(os.environ.get("LAURA_API_TIMEOUT", "25"))


def review_plan(text, metadata=None, title=None, **kwargs):
    """Call Laura's review_plan gate via our own Fly-hosted MCP endpoint.

    Args:
        text: the copy / proposal / plan text to review.
        metadata: optional dict (title, context, kind, slug, ...).
        title: optional convenience (folded into metadata so callers that
            pass title=... like daily_spawn keep working).

    Returns:
        dict with shape {"result": {"lenses": [...], "summary": ...},
                         "flags": <int>}  on success,
        or {"error": <str>} on transport failure (caller treats as BLOCK).
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "review_plan",
            "arguments": {
                "text": text,
                "metadata": {**(metadata or {}),
                             **({"title": title} if title else {})},
            },
        },
    }
    req = urllib.request.Request(
        LAURA_API_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            outer = json.loads(r.read().decode())
    except Exception as e:
        # API unreachable -> never self-approve. Block honestly.
        return {"error": f"laura api unreachable: {e}"}

    # JSON-RPC envelope -> result.content[0].text -> JSON string.
    try:
        content = outer.get("result", {}).get("content", [])
        inner_text = content[0]["text"] if content else "{}"
        obj = json.loads(inner_text)
    except Exception as e:
        return {"error": f"laura api bad response: {e}"}

    lenses = obj.get("lenses", [])
    flags = 0
    for l in lenses:
        for f in l.get("findings", []):
            if f.get("severity") in ("flag", "blocker"):
                flags += 1
    obj["flags"] = flags
    return obj


# Alias so existing callers (`from hermes_tools import mcp_laura_review_plan`)
# can be repointed with a one-line change.
mcp_laura_review_plan = review_plan
