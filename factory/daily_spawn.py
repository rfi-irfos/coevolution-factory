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
# connected. Outside that context we call our OWN Laura API on Fly directly
# (keyless /mcp endpoint) so the Babies self-govern without an agent proxy.
# Either way, the gate is Laura's — never self-approve.
try:
    from hermes_tools import mcp_laura_review_plan
except Exception:
    try:
        from laura_gate_client import review_plan as mcp_laura_review_plan
    except Exception:
        mcp_laura_review_plan = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_spawn_agent as F
import runtime as R


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
    # ── self-correction hook (active learning): before Laura sees it, the
    #    firm re-reads its memory and de-fangs known mistake patterns. ──────
    try:
        import firm_foundation as FF
        notes = FF.apply_self_correction(R.state, cand.get("parent") or cand.get("slug"), cand)
        if notes:
            print(f"[self-review] {cand.get('slug')}: {notes}", flush=True)
            R.save_state(R.state)
    except Exception as _e:
        print(f"[self-review] hook failed: {_e}", flush=True)
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
        passed = len(flags) == 0
        # learning hook: Laura blocked this candidate -> capture why
        if not passed:
            try:
                import firm_foundation as FF
                FF.learn_from_laura_block(
                    R.state, cand.get("parent") or cand.get("slug"), cand, flags)
                R.save_state(R.state)
            except Exception as _e:
                print(f"[learning] laura-block hook failed: {_e}", flush=True)
        return passed
    except Exception:
        return False  # Laura error -> no spawn


async def batch_gate_candidates(cands):
    """ONE Laura MCP call reviewing all staged candidates. Returns {slug: bool}.

    Falls back to per-candidate gate_candidate on any exception (so a single
    Laura error does not kill the whole batch -- the old serial path still works).

    Accepts two Laura response shapes:
      - {"verdicts": {slug: {"flags": [...]}}}  -> per-candidate verdict
      - {"flags": [...]}                          -> top-level list (conservative:
                                                     all-or-nothing -- any flag blocks
                                                     every candidate)
    """
    if mcp_laura_review_plan is None:
        return {s: False for s in cands}  # Laura offline -> no spawn
    try:
        res = mcp_laura_review_plan(
            title="AutoCenter spawn batch review",
            text=json.dumps([
                {
                    "slug": s,
                    "name": c.get("name"),
                    "mandate": c.get("mandate"),
                    "uncovered_signals": c.get("uncovered_signals", []),
                }
                for s, c in cands.items()
            ], indent=2),
            metadata={"kind": "factory-spawn-batch", "count": len(cands)},
        )
        if isinstance(res, dict) and "verdicts" in res:
            verdicts = res["verdicts"]
            return {
                s: (verdicts.get(s, {}).get("flags", []) == [])
                for s in cands
            }
        # single top-level flags list -> all-or-nothing (conservative)
        flags = res.get("flags", []) if isinstance(res, dict) else []
        return {s: (len(flags) == 0) for s in cands}
    except Exception:
        # fallback: per-candidate (serial) so one Laura error doesn't kill all
        return {s: await gate_candidate(c) for s, c in cands.items()}


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
    from runtime import CENTERS, CENTER_SLUGS, CENTER_NETWORK
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
    CENTER_SLUGS.append(slug)
    CENTER_NETWORK.setdefault(slug, [])
    st.setdefault("centers", {})[slug] = {"version": 1, "is_daughter": True}
    st.setdefault("daughter_centers", {})[slug] = spec
    # learning hook: a Laura-passed offering shipped -> success lesson
    try:
        import firm_foundation as FF
        FF.learn_from_launch(st, cand.get("parent") or slug, cand)
        FF.ensure_foundation(st, slug)
        st.setdefault("firm_foundation", {}).setdefault(slug, {})
        st["firm_foundation"][slug]["launches"] = \
            st["firm_foundation"][slug].get("launches", 0) + 1
        st["firm_foundation"][slug]["reflection_score"] = round(
            min(0.98, st["firm_foundation"][slug].get("reflection_score", 0.35) + 0.05), 3)
        R.save_state(st)
    except Exception as _e:
        print(f"[learning] launch hook failed: {_e}", flush=True)
    return True


def capacity_ok():
    """True if we may promote more daughters this cycle.

    Respects the VF_MAX_DAUGHTERS cap (default 10) and refuses while any
    center is in 0-status (engine unreachable) so we never scale into a
    degraded state. The env var is read live (not cached at import) so it
    can be toggled per-test / per-deployment.
    """
    max_daughters = int(os.environ.get("VF_MAX_DAUGHTERS", "10"))
    daughters = len(R.state.get("daughter_centers", {}))
    if daughters >= max_daughters:
        return False
    # refuse if any center is in 0-status (engine down)
    for rec in R.state.get("center_status", {}).values():
        if rec.get("status") == "0-status":
            return False
    return True


def network_daughters(parent, new_slugs):
    """Link co-spawned daughters to each other (bidirectional) and to the
    parent in CENTER_NETWORK (adjacency is bidirectional). Idempotent:
    re-running with the same slugs never duplicates an edge."""
    for s in new_slugs:
        R.CENTER_NETWORK.setdefault(s, [])
        # daughter <-> parent
        if parent:
            if parent not in R.CENTER_NETWORK[s]:
                R.CENTER_NETWORK[s].append(parent)
            if s not in R.CENTER_NETWORK.setdefault(parent, []):
                R.CENTER_NETWORK[parent].append(s)
        # daughter <-> daughter (co-spawned in this cycle)
        for o in new_slugs:
            if o != s and o not in R.CENTER_NETWORK[s]:
                R.CENTER_NETWORK[s].append(o)


# Module-level alias so scale_out() can call run_spawn_agent() and tests can
# monkeypatch `DS.run_spawn_agent` directly.
run_spawn_agent = F.run_spawn_agent


async def scale_out():
    """Autonomous scale-out orchestrator (turntable: serial engine calls).

    Full loop:
        scan -> collect staged candidates -> if capacity_ok():
        batch_gate_candidates -> for each passed: promote(st, cand),
        set status 'born', laura_pass=True, apply_second_reviewer(cand)
        -> collect new_slugs -> network_daughters(parent, new_slugs)
        for each parent -> save_state -> return report.

    Laura stays the FINAL gate (batch_gate_candidates refuses when she is
    unavailable). capacity_ok() guards engine health + the daughter cap.
    """
    # 1. scan (stages candidates via the spawn agent).
    scan_res = await run_spawn_agent()

    # Operate on the live in-memory state (R.state), which is what the
    # running process and tests mutate; save_state() persists it afterward.
    st = R.state

    # 2. collect staged candidates only.
    staged = {
        s: c for s, c in st.get("spawn_candidates", {}).items()
        if c.get("status") == "staged"
    }

    promoted, blocked, new_slugs = [], [], []

    if staged and capacity_ok():
        # 3. single batch Laura gate over all staged candidates.
        passmap = await batch_gate_candidates(staged)
        for slug, cand in staged.items():
            if passmap.get(slug):
                ok = promote(st, cand)
                cand["status"] = "born" if ok else "duplicate"
                cand["laura_pass"] = True
                # HITL second-reviewer SLOT (additive; Laura remains gate #1).
                apply_second_reviewer(cand)
                if ok:
                    promoted.append(slug)
                    new_slugs.append(slug)
            else:
                cand["status"] = "blocked_pending_laura"
                blocked.append(slug)

        # 4. auto-network co-spawned daughters to each other + their parent.
        parents = {c.get("parent") for c in staged.values()}
        for p in parents:
            network_daughters(p, new_slugs)

    # 5. persist + report.
    save_state(st)
    return {
        "scan": scan_res,
        "promoted": promoted,
        "blocked_pending_laura": blocked,
        "capacity_ok": capacity_ok(),
    }


async def main():
    report = await scale_out()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
