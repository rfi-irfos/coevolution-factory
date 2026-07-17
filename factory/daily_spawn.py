#!/usr/bin/env python3
"""Daily FACTORY-FACTORY cron — promote staged spawn candidates.

Pipeline (honest, Laura-gated, no self-approve):
  1. run_spawn_agent() scans real feeds, detects gaps, STAGES candidates.
  2. For each staged candidate: call mcp_laura_review_plan (if available).
     - 0-FLAG -> set laura_pass=True.
     - any FLAG -> leave staged, log the block.
  3. Only laura_pass candidates get promoted to a real standing center
     (registered in CENTERS + rehydrated on boot, same as /evolve).
  4. If Laura is unavailable (mcp tool missing/offline), we DO NOT spawn.
     The candidate waits — doctrine: Laura = FINAL ship gate.

Run via fly.toml [deploy.schedule] (daily, before daily_evolve).
"""
import asyncio, json, time, sys, os
from pathlib import Path

# Hermes runtime provides mcp_laura_review_plan when the Laura tool is
# connected. Outside that context (e.g. direct `python daily_spawn.py`)
# we treat Laura as UNAVAILABLE and refuse to spawn.
try:
    from hermes_tools import mcp_laura_review_plan
except Exception:
    mcp_laura_review_plan = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_spawn_agent as F


def load_state():
    p = Path(os.environ.get("FT_STATE_DIR", ".")) / "state.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_state(st):
    p = Path(os.environ.get("FT_STATE_DIR", ".")) / "state.json"
    p.write_text(json.dumps(st, indent=2))


async def gate_candidate(cand):
    """Return True only if Laura passes (or Laura is the FINAL gate and
    unavailable -> we return False, never self-approve)."""
    if mcp_laura_review_plan is None:
        return False  # Laura offline -> no spawn
    try:
        res = mcp_laura_review_plan(
            title=f"AutoCenter spawn candidate: {cand['name']}",
            text=json.dumps({
                "name": cand["name"],
                "mandate": cand["mandate"],
                "uncovered_signals": cand.get("uncovered_signals", []),
            }, indent=2),
            metadata={"kind": "factory-spawn", "slug": cand["slug"]},
        )
        # 0-FLAG required (doctrine: any flag -> block)
        flags = (res or {}).get("flags") or (res or {}).get("verdicts") or []
        return len(flags) == 0
    except Exception:
        return False  # Laura error -> no spawn


def apply_second_reviewer(cand):
    """HITL second-reviewer SLOT (OQ2). Laura stays gate #1; this is an
    ADDITIVE second human sign-off slot, never a bypass.

    Reads env HITL_SECOND_REVIEWER. If set (e.g. a nominated person's id),
    stamp the (already Laura-passed) candidate record with
    ``second_reviewer_present=True`` and return an honest log line. If unset,
    return a 'pending_nomination' log line and stamp nothing — no fake
    reviewer, no auto-approve. Simeon/Laura nominate the real person later.

    Returns the log string (also used as the test observation point).
    """
    reviewer = os.environ.get("HITL_SECOND_REVIEWER")
    if reviewer:
        cand["second_reviewer_present"] = True
        msg = (f"second_reviewer: present (slot='{reviewer}') — additive to "
               f"Laura gate #1")
    else:
        cand["second_reviewer_present"] = False
        msg = "second_reviewer: pending_nomination"
    print(f"[governance] {cand.get('slug','?')}: {msg}", flush=True)
    return msg


def promote(st, cand):
    """Register the candidate as a real standing center (mirrors
    /evolve apply: CENTERS + CENTERS_SLUGS + daughter_centers + network)."""
    from runtime import CENTERS, CENTERS_SLUGS, CENTER_NETWORK
    slug = cand["slug"]
    if slug in CENTERS:
        return False
    spec = {
        "name": cand["name"],
        "mandate": cand["mandate"],
        "disciplines": ["auto-spawned"],
        "panel": [],  # to be populated from uncovered-signal agents
        "free": 3, "price": 0.2,
        "sample_question": "What is our exposure on this new signal?",
        "value_prop": "Spawned autonomously when a real regulatory/trend "
                     "signal fell outside every standing center's coverage.",
        "resilient": "Factory-formed from observed real-world gaps; "
                     "re-scanned daily.",
        "standing_prompt": cand["mandate"],
        "cross_center": [], "feeds_into": [],
        "is_daughter": True, "parent": None,
    }
    CENTERS[slug] = spec
    CENTERS_SLUGS.append(slug)
    CENTER_NETWORK.setdefault(slug, [])
    st.setdefault("centers", {})[slug] = {"version": 1, "is_daughter": True}
    st.setdefault("daughter_centers", {})[slug] = spec
    return True


async def main():
    # 1. scan + stage
    scan_res = await F.run_spawn_agent()
    st = load_state()
    cands = st.get("spawn_candidates", {})
    promoted, blocked = [], []
    for slug, cand in cands.items():
        if cand.get("status") != "staged":
            continue
        passed = await gate_candidate(cand)
        if passed:
            ok = promote(st, cand)
            cand["status"] = "born" if ok else "duplicate"
            cand["laura_pass"] = True
            # HITL second-reviewer SLOT (additive; Laura remains gate #1).
            apply_second_reviewer(cand)
            if ok:
                promoted.append(slug)
        else:
            cand["status"] = "blocked_pending_laura"
            blocked.append(slug)
    save_state(st)
    print(json.dumps({
        "scan": scan_res,
        "candidates_total": len(cands),
        "promoted": promoted,
        "blocked_pending_laura": blocked,
        "laura_available": mcp_laura_review_plan is not None,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
