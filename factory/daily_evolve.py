#!/usr/bin/env python3
"""Daily recursive-evolve cron for the 50 CENTERS. Runs in the Hermes agent
context so it can call the REAL mcp_laura_review_plan ship gate (doctrine:
no self-approve).

Pipeline per run:
  1. POST /evolve?all=1  -> stages data-grounded panel proposals (tested on
     live engine)
  2. for each staged proposal: call mcp_laura_review_plan on the self-authored
     spec change text. If 0 FLAGs -> POST /evolve/apply {laura_pass:true}.
     If any FLAG -> leave blocked, report to Simeon.
  3. GET /observatory -> append a cashflow snapshot to the daily log.

This is the recursion driver: every day the centers re-optimize their panels,
gated by Laura, and the next day's telemetry measures the improvement.
"""
import os, sys, json, time, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
BASE = os.environ.get("FT_BASE", "http://localhost:8091")
LOG = HERE / "evolve_log.jsonl"


def post(path, data=None):
    req = urllib.request.Request(BASE + path,
        data=json.dumps(data or {}).encode() if data is not None else None,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def laura_gate(changelog_text):
    """Call the REAL Laura ship gate. Returns (passed: bool, summary: str)."""
    try:
        from hermes_tools import mcp_laura_review_plan
        res = mcp_laura_review_plan(
            text=changelog_text,
            metadata={"title": "center recursive self-improvement",
                      "context": "autonomous daily evolve — self-authored panel spec change"})
        lenses = res.get("result", {}).get("lenses", [])
        flags = sum(len(l.get("findings", [])) for l in lenses
                    if any(f.get("severity") in ("flag", "blocker")
                           for f in l.get("findings", [])))
        summary = res.get("result", {}).get("summary", "")
        return (flags == 0, summary)
    except Exception as e:
        # if the bridge is unavailable, DO NOT auto-approve — block.
        return (False, f"laura bridge unavailable: {e}")


def main():
    log = {"ts": int(time.time()), "proposed": 0, "applied": 0, "blocked": []}
    # 1. propose
    ev = post("/evolve?all=1")
    proposals = [p for p in ev.get("proposals", []) if p.get("staged")]
    log["proposed"] = len(proposals)
    # 2. gate + apply
    for p in proposals:
        slug = p["center"]
        text = f"Center {slug} self-improvement proposal: " + "; ".join(p["changelog"])
        passed, summary = laura_gate(text)
        if passed:
            r = post("/evolve/apply", {"center": slug, "laura_pass": True})
            log["applied"] += 1
            print(f"  APPLIED {slug}: {r.get('applied')}")
        else:
            log["blocked"].append({"center": slug, "reason": summary})
            print(f"  BLOCKED {slug}: {summary}")
    # 3. cashflow snapshot
    obs = get("/observatory")
    log["cashflow"] = {"total_sessions": obs.get("total_sessions"),
                       "total_paid_eur": obs.get("total_paid_eur"),
                       "total_revenue_eur": obs.get("total_revenue_eur")}
    with open(LOG, "a") as f:
        f.write(json.dumps(log) + "\n")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
