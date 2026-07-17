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
import time

import runtime as R

LABEL = "VIRTUAL FIRM (agentic, data-processing only)"


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
        "launch_gate": "staged->launched requires Laura (gate #1); "
                       "never auto-launched by the Virtual Firm orchestrator",
    }
