#!/usr/bin/env python3
"""Daily autonomous-briefing cron for the 50 CENTERS.

Pipeline (mirrors daily_evolve's governance):
  1. for each center with BRIEFING_SOURCES: run_briefing() pulls NEW
     real feed items, convenes the panel, publishes a briefing record.
  2. the published briefing text is carried through mcp_laura_review_plan.
     Only if 0 FLAGs is it kept public; a flagged briefing is
     moved to blocked (not shown) and reported.
  3. cashflow snapshot appended to the daily log.

This is the autonomous OUTPUT layer: it produces market-value content
even when no human is online. Cost-aware — only NEW feed GUIDs
trigger an engine call (deduped in state.json). Never fabricates;
the panel only reasons over real fetched items.
"""
import os, sys, json, time
from pathlib import Path

HERE = Path(__file__).parent
BASE = os.environ.get("FT_BASE", "http://localhost:8091")
LOG = HERE / "briefing_log.jsonl"

sys.path.insert(0, str(HERE))
from briefing import BRIEFING_SOURCES, run_briefing, load_state, save_state


def laura_gate(text):
    """Call the REAL Laura ship gate on the published briefing copy.

    Uses the Hermes MCP when available, otherwise our OWN Laura API on Fly
    (keyless /mcp). Either way: the gate is Laura's — never self-approve.
    """
    try:
        from hermes_tools import mcp_laura_review_plan
    except Exception:
        try:
            from laura_gate_client import review_plan as mcp_laura_review_plan
        except Exception:
            mcp_laura_review_plan = None
    if mcp_laura_review_plan is None:
        return (False, "laura bridge unavailable")
    try:
        res = mcp_laura_review_plan(
            text=text,
            metadata={"title": "center autonomous briefing",
                      "context": "daily autonomous briefings — self-published public copy"})
        lenses = res.get("result", {}).get("lenses", [])
        flags = sum(
            len(l.get("findings", []))
            for l in lenses
            if any(f.get("severity") in ("flag", "blocker")
                   for f in l.get("findings", [])))
        return (flags == 0, res.get("result", {}).get("summary", ""))
    except Exception as e:
        return (False, f"laura bridge unavailable: {e}")


async def run():
    import asyncio
    from catalog import CENTERS_META
    st = load_state()
    log = {"ts": int(time.time()), "briefed": 0, "blocked": []}
    slugs = [s for s in CENTERS_META if s in BRIEFING_SOURCES]
    for slug in slugs:
        b, lg = await run_briefing(slug, st)
        if not b:
            continue
        log["briefed"] += 1
        # gate the published copy
        text = f"Center {slug} autonomous briefing:\n" + "\n".join(
            f"- {it['source']}: {it['syn'].get('note','')[:200]}"
            for it in b["items"])
        passed, summary = laura_gate(text)
        if not passed:
            # pull it back out of public briefings -> blocked
            bstore = st.get("briefings", {}).get(slug, [])
            if bstore and bstore[0] is b:
                bstore.pop(0)
                save_state(st)
            log["blocked"].append({"center": slug, "reason": summary})
            print(f"  BRIEF BLOCKED {slug}: {summary}")
        else:
            print(f"  BRIEF PUBLISHED {slug}: {lg}")
    with open(LOG, "a") as f:
        f.write(json.dumps(log) + "\n")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
