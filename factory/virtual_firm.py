#!/usr/bin/env python3
"""Virtual Firm R0hne — pipeline orchestrator (Task 4).

IMPORTANT LABEL: this is a VIRTUAL FIRM (agentic, data-processing only). It
routes REAL inbound leads into an offering pipeline of ideas the agent panels
deliberate on. NO real-world company is replaced or taken over, and NO physical
product is produced. Every output is labelled accordingly.

Pipeline (reuses runtime primitives, no reimplementation):

    idea  ->  debate  ->  prototype  ->  staged  ->  launched
     ^                                      ^            ^
  seed_offering                       spawn-agent     LAURA GATE #1
  (from a real lead)                  stages this    (daily_spawn only)

Doctrine wired here:
  * ``route_lead_to_pipeline`` turns a real lead into an offering at the
    'idea' stage (one per center per calendar year — idempotent), and advances
    idea -> debate -> prototype as evidence (debate resolution) accrues.
  * The staged -> launched transition is NEVER performed here. Launch requires
    the existing Laura-gated spawn path (factory_spawn_agent stages a
    candidate; daily_spawn.gate_candidate runs Laura as FINAL gate #1). This
    module refuses to set 'launched' and says so explicitly.
"""
import os
import time

import daily_spawn as DS  # noqa: E402  (promote + second-reviewer gate)
import runtime as R  # noqa: E402
from runtime import CENTER_SLUGS  # noqa: E402  (mutable registry for launch/rollback)

LABEL = "VIRTUAL FIRM (agentic, data-processing only)"

# Opt-in auto-launch (Simeon/Laura 2026-07-17): a staged offering may launch
# ITSELF only when EVERY gate is true — see launch_staged_offering(). Off by
# default; requires explicit VF_AUTO_LAUNCH=1 + HITL_SECOND_REVIEWER + laura_pass.
_AUTO_LAUNCH = os.environ.get("VF_AUTO_LAUNCH", "0") == "1"
_SECOND_REVIEWER = bool(os.environ.get("HITL_SECOND_REVIEWER"))


def _snapshot_for_rollback(oid, slug):
    """Capture pre-launch CENTERS keys so a launch is reversible. Stored under
    state['rollback'][oid]; rollback_launch() restores exactly this state."""
    R.state.setdefault("rollback", {})[oid] = {
        "slug": slug,
        "centers_keys": list(R.CENTERS.keys()),
        "at": int(time.time()),
    }


def rollback_launch(oid):
    """Reverse a launch: remove the promoted center and drop the offering back
    to 'staged'. Reversible ONLY for launches this module performed (oid in
    state['rollback']). Returns {ok, reason}."""
    rb = R.state.get("rollback", {}).get(oid)
    if not rb:
        return {"ok": False, "reason": "no rollback record for this offering"}
    slug = rb["slug"]
    # remove from the running registry (mirror of daily_spawn.promote)
    R.CENTERS.pop(slug, None)
    if slug in CENTER_SLUGS:
        CENTER_SLUGS.remove(slug)
    R.CENTER_NETWORK.pop(slug, None)
    R.state.get("centers", {}).pop(slug, None)
    R.state.get("daughter_centers", {}).pop(slug, None)
    rec = R.state.get("pipeline", {}).get(oid)
    if rec is not None:
        rec["stage"] = "staged"
        rec["updated"] = int(time.time())
    R.save_state(R.state)
    return {"ok": True, "reason": f"rolled back launch of {slug}", "slug": slug}


def _year(ts=None):
    return time.gmtime(ts or time.time()).tm_year


def _offering_for(center, year=None):
    """Return (oid, rec) for this center's offering in the given calendar year,
    or (None, None) if none exists yet."""
    year = year or _year()
    for oid, rec in R.state.get("pipeline", {}).items():
        if rec.get("center") != center:
            continue
        if _year(rec.get("created")) == year:
            return oid, rec
    return None, None


def route_lead_to_pipeline(center, lead):
    """Route a REAL lead (from state['leads'][center]) into the offering
    pipeline.

    1. Seed an offering at 'idea' if the center has none for the current year
       (idempotent — one seed per center per year, so repeated leads reuse it).
    2. On a resolved inbound debate (lead kind == 'debate'), advance the
       offering idea -> debate, and if it is already at 'debate', -> prototype.

    Returns a dict {offering_id, stage, seeded, advanced, label}.
    The staged -> launched hop is intentionally NOT reachable here.
    """
    oid, rec = _offering_for(center)
    seeded = False
    if oid is None:
        # An honest, non-PII idea label derived from the lead's outcome.
        idea = (f"{LABEL}: offering seeded from real {lead.get('kind','?')} "
                f"lead ({lead.get('question_hash','')[:12]}), "
                f"outcome={lead.get('outcome')}")
        oid = R.seed_offering(center, idea)
        rec = R.state["pipeline"][oid]
        seeded = True

    advanced = False
    # Advance only on real debate evidence; a bare session lead just seeds.
    rec = R.state["pipeline"][oid]
    if lead.get("kind") == "debate":
        stage = rec.get("stage")
        if stage == "idea":
            R.advance_pipeline(oid, "debate")
            advanced = True
        elif stage == "debate":
            R.advance_pipeline(oid, "prototype")
            advanced = True
        # prototype -> staged is owned by the spawn-agent; staged -> launched
        # is owned by the Laura gate. Neither happens here.

    return {
        "offering_id": oid,
        "stage": R.state["pipeline"][oid]["stage"],
        "seeded": seeded,
        "advanced": advanced,
        "label": LABEL,
    }


def _debate_resolved_for(center):
    """True if the center has at least one RESOLVED debate (real evidence)."""
    for rec in R.state.get("debates", {}).values():
        if rec.get("center") == center and rec.get("status") == "resolved":
            return True
    return False


# Readiness threshold: a prototype only stages once REAL demand is evidenced.
# Doctrine: no auto-promotion on thin air — needs a resolved debate AND a
# minimum of real leads. Tunable via env without a code change.
import os as _os
STAGE_MIN_LEADS = int(_os.environ.get("VF_STAGE_MIN_LEADS", "3"))


def promote_prototype_to_staged(center):
    """Close the loop: a 'prototype' offering advances to 'staged' ONLY when
    real demand is evidenced (a resolved debate AND >= STAGE_MIN_LEADS real
    leads for the center). Staging registers a spawn_candidate so Laura's
    daily_spawn gate (#1) can consider it. This function NEVER launches.

    Returns {advanced: bool, offering_id, stage, reason}.
    """
    oid, rec = _offering_for(center)
    if oid is None or rec is None:
        return {"advanced": False, "offering_id": None, "stage": None,
                "reason": "no offering for center"}
    if rec.get("stage") != "prototype":
        return {"advanced": False, "offering_id": oid,
                "stage": rec.get("stage"),
                "reason": "no prototype-stage offering"}

    lead_count = len(R.state.get("leads", {}).get(center, []))
    if not _debate_resolved_for(center):
        return {"advanced": False, "offering_id": oid, "stage": "prototype",
                "reason": "no resolved debate yet (need real deliberation)"}
    if lead_count < STAGE_MIN_LEADS:
        return {"advanced": False, "offering_id": oid, "stage": "prototype",
                "reason": f"only {lead_count}/{STAGE_MIN_LEADS} real leads"}

    R.advance_pipeline(oid, "staged")

    # Register a spawn_candidate for the Laura gate. status='staged' is exactly
    # what daily_spawn.gate_candidate() looks for. laura_pass stays False until
    # Laura clears it — this module never self-approves.
    cands = R.state.setdefault("spawn_candidates", {})
    cand_slug = f"{center}-vf-{oid[-6:]}"
    cands[cand_slug] = {
        "name": f"{R.CENTERS.get(center, {}).get('name', center)} — Virtual Firm offering",
        "mandate": rec.get("idea", "")[:200],
        "parent": center,
        "status": "staged",
        "laura_pass": False,
        "source": "virtual_firm_pipeline",
        "offering_id": oid,
        "uncovered_signals": [f"{lead_count} real leads", "resolved debate"],
        "created": int(time.time()),
    }
    R.save_state(R.state)
    return {"advanced": True, "offering_id": oid, "stage": "staged",
            "reason": f"staged: resolved debate + {lead_count} leads; "
                      f"spawn_candidate '{cand_slug}' queued for Laura gate",
            "candidate": cand_slug}


def launch_staged_offering(oid):
    """Autonomously LAUNCH a staged offering — REVERSIBLY — but ONLY when every
    gate is true:

      * VF_AUTO_LAUNCH=1  (explicit opt-in, off by default)
      * HITL_SECOND_REVIEWER set (OQ2 second human slot present)
      * candidate.laura_pass == True  (Laura gate #1 cleared; the FINAL ship gate)

    If any gate is false, this returns {launched: False, reason} and leaves the
    offering at 'staged' for the human/Laura path. When all gates pass, it:
      1. snapshots pre-launch CENTERS keys (rollback record),
      2. promotes the candidate to a real standing center (daily_spawn.promote),
      3. stamps second-reviewer presence + laura_pass on the record,
      4. sets the offering stage to 'launched' + records the rollback oid.

    Rollback: rollback_launch(oid) reverses all of the above.

    Doctrine: LAURA STAYS GATE #1. Without laura_pass this NEVER launches, even
    with auto-launch + second reviewer set. Reversible by design.
    """
    rec = R.state.get("pipeline", {}).get(oid)
    if rec is None:
        return {"launched": False, "reason": "unknown offering"}
    if rec.get("stage") != "staged":
        return {"launched": False, "reason": f"not staged (stage={rec.get('stage')})"}

    # resolve the spawn_candidate this offering registered
    cand = None
    cand_slug = None
    for slug, c in R.state.get("spawn_candidates", {}).items():
        if c.get("offering_id") == oid and c.get("source") == "virtual_firm_pipeline":
            cand = c
            cand_slug = slug
            break
    if cand is None:
        return {"launched": False, "reason": "no staged candidate for offering"}

    # ── gate checks ──────────────────────────────────────────────────────────
    if not _AUTO_LAUNCH:
        return {"launched": False, "reason": "VF_AUTO_LAUNCH not enabled (opt-in)"}
    if not _SECOND_REVIEWER:
        return {"launched": False, "reason": "HITL_SECOND_REVIEWER not set"}
    if not cand.get("laura_pass"):
        return {"launched": False,
                "reason": "Laura gate #1 not cleared (laura_pass=False)"}

    # ── all gates true -> launch, reversibly ──────────────────────────────────
    _snapshot_for_rollback(oid, cand_slug)
    ok = DS.promote(R.state, cand)
    if not ok:
        # slug already present (e.g. re-run) — still mark launched, no double-add
        R.state.get("rollback", {}).pop(oid, None)
        return {"launched": False, "reason": f"slug {cand_slug} already exists"}

    DS.apply_second_reviewer(cand)  # stamp second-reviewer presence
    cand["status"] = "launched"
    cand["launched_at"] = int(time.time())
    rec["stage"] = "launched"
    rec["launched_candidate"] = cand_slug
    rec["rollback_oid"] = oid
    rec["updated"] = int(time.time())
    R.save_state(R.state)
    return {"launched": True, "slug": cand_slug, "rollback_oid": oid,
            "reason": "all gates true (auto-launch + second-reviewer + Laura); "
                      "reversible via rollback_launch(oid)"}


def stage_counts(center=None):
    """Count offerings per pipeline stage (optionally filtered to a center)."""
    counts = {s: 0 for s in R.PIPELINE_STAGES}
    for rec in R.state.get("pipeline", {}).values():
        if center and rec.get("center") != center:
            continue
        st = rec.get("stage")
        if st in counts:
            counts[st] += 1
    return counts


def orchestrate(center):
    """Drive + report the Virtual Firm pipeline for a center.

    Routes every un-routed real lead for the center into the pipeline, then
    returns an honest status dict. Never launches: staged -> launched stays
    behind the Laura gate (daily_spawn).
    """
    leads = R.state.get("leads", {}).get(center, [])
    for lead in leads:
        route_lead_to_pipeline(center, lead)

    # Close the loop: try to advance a ready prototype -> staged (readiness-
    # gated: resolved debate + real leads). Never launches; staging only
    # queues a spawn_candidate for the Laura gate.
    stage_result = promote_prototype_to_staged(center)

    counts = stage_counts(center)
    last_offering = None
    center_offerings = [
        (oid, rec) for oid, rec in R.state.get("pipeline", {}).items()
        if rec.get("center") == center
    ]
    if center_offerings:
        oid, rec = sorted(
            center_offerings, key=lambda kv: kv[1].get("created", 0))[-1]
        last_offering = {"offering_id": oid, "stage": rec.get("stage"),
                         "created": rec.get("created")}

    return {
        "center": center,
        "label": LABEL,
        "stage_counts": counts,
        "offerings_total": len(center_offerings),
        "last_offering": last_offering,
        "stage_transition": stage_result,
        "launch_gate": "staged->launched requires Laura (gate #1); "
                       "never auto-launched by the Virtual Firm orchestrator",
    }
