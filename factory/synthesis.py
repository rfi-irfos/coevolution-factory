# factory/synthesis.py — center-level cross-synthesis.
#
# Two modes:
#  - local_synthesize(): deterministic aggregation of the panel's OWN findings
#    (always available, no engine call, never fabricates). Good enough to show
#    posture, flags, notes and discipline conflicts.
#  - engine_synthesize(): when the REAL engine key is configured, sends the
#    convened findings to a meta-synthesis pass so a center-level judgment is
#    produced by the engine itself (richer than local aggregation). Falls back
#    to local_synthesize() on any error — never fakes.
import asyncio
from aiohttp import ClientSession, ClientError, ClientTimeout


def local_synthesize(upstream, panel):
    """Deterministic synthesis of the panel's OWN findings. Does not invent
    anything: aggregates real severities, surfaces conflicts between
    disciplines, reports a center-level posture. No LLM call.

    NOTE on matching: the engine returns each response keyed by the agent's
    *display name* (e.g. "GDPR", "Privacy Law"), not its registry slug
    ("risk-gdpr"). So we match a response to a panel member when the slug or
    the slugified name appears in the engine's agent label.
    """
    responses = upstream.get("responses", []) if isinstance(upstream, dict) else []
    def norm(s):
        return s.lower().replace("-", "").replace("_", "")
    panel_norm = {norm(a): a for a in panel}
    flags, notes = [], []
    fired, silent = set(), []
    for r in responses:
        label = r.get("agent", "")
        member = None
        for pn, orig in panel_norm.items():
            if pn in norm(label) or norm(label) in pn or norm(label) == pn:
                member = orig
                break
        if member is None:
            member = label
        if not r.get("findings"):
            if member in panel:
                silent.append(member)
            continue
        fired.add(member)
        for f in r.get("findings", []) if isinstance(r.get("findings"), list) else []:
            sev = f.get("severity")
            item = {"agent": member, "severity": sev,
                    "description": f.get("description", ""),
                    "evidence": f.get("evidence", "")}
            (flags if sev == "flag" else notes).append(item)
    conflicts = []
    flag_ev = {f["evidence"] for f in flags if f["evidence"]}
    for n in notes:
        if n["evidence"] and n["evidence"] in flag_ev:
            conflicts.append({
                "evidence": n["evidence"],
                "flag_by": [f["agent"] for f in flags if f["evidence"] == n["evidence"]],
                "note_by": n["agent"],
                "tension": "one discipline flags this, another clears it — escalate to Laura/human",
            })
    posture = "stable"
    if len(flags) >= 3:
        posture = "elevated"
    elif len(flags) >= 1:
        posture = "watch"
    return {
        "posture": posture,
        "mode": "local",
        "panel_size": len(panel),
        "disciplines_fired": len(fired),
        "disciplines_silent": silent,
        "flags": flags,
        "notes": notes,
        "conflicts": conflicts,
        "flag_count": len(flags),
        "note_count": len(notes),
    }


async def engine_synthesize(upstream, panel, engine_url, engine_key):
    """Optional richer synthesis through the REAL engine. Sends the convened
    findings as a single meta-prompt; expects {synthesis: {...}} or falls back
    to local. Never fakes — any failure returns local_synthesize()."""
    base = local_synthesize(upstream, panel)
    try:
        meta = {
            "text": "Synthesize the following interdisciplinary panel findings "
                    "into a single center-level judgment (posture, top tensions, "
                    "recommended next step). Findings:\n" +
                    "\n".join(f"- [{f['agent']}/{f['severity']}] {f['description']}"
                               for f in base["flags"] + base["notes"]),
            "agents": ["chief-strategy-officer", "chief-risk-officer"],
        }
        headers = {"Authorization": f"Bearer {engine_key}",
                   "Content-Type": "application/json"}
        async with ClientSession() as s:
            async with s.post(f"{engine_url}/pool/team", headers=headers,
                              json=meta,
                              timeout=ClientTimeout(total=600)) as r:
                if r.status != 200:
                    return base
                meta_up = await r.json()
        meta_responses = meta_up.get("responses", [])
        judgment = " ".join(
            str(x.get("findings", "")) for x in meta_responses if x.get("findings"))
        base["mode"] = "engine"
        base["center_judgment"] = judgment[:2000] if judgment else None
    except (ClientError, asyncio.TimeoutError, Exception):
        # any failure -> keep the honest local synthesis, do NOT fake
        base["mode"] = "local"
    return base


def propagate_tensions(slug, synth, network):
    """Cross-center resolution (metadata only, no fabrication).

    For every conflict/tension a center's panel surfaced, find the adjacent
    centers (real feeds_into adjacency) and tag the tension as SHARED CONTEXT
    for them. This is what makes the 50 centers a network, not 50 silos: a
    tension in GDPRGuard is visible to its adjacent centers (BreachReady,
    AIActGuard, ChildSafety, …) so they can weigh it in their own convenings.
    Returns a list of {evidence, from_center, shared_with[]}."""
    if not synth.get("conflicts"):
        return []
    adjacent = network.get(slug, [])
    shared = []
    for c in synth["conflicts"]:
        shared.append({
            "evidence": c.get("evidence"),
            "tension": c.get("tension"),
            "flag_by": c.get("flag_by"),
            "note_by": c.get("note_by"),
            "shared_with": adjacent,
        })
    return shared


def detect_emergence(center_slug, synth, registry):
    """Emergence detection: decide whether the panel's findings reveal a
    capability gap that no existing center covers — i.e. a signal that a new
    intra-company team (or, eventually, a new daughter center) should form.

    Heuristic, honest, no fabrication:
      - if a finding's evidence mentions a domain/lane with NO agent currently
        in this center's panel AND no adjacent center -> emergence signal.
      - if the engine returned a 'capability_gap' note -> emergence signal.
    Returns {signal: bool, gap_domains: [...], suggested_agents: [...]}.

    NOTE: cross-discipline tensions are NOT emergence (they're resolved via
    propagate_tensions). Emergence is about a *new* competence surfacing that
    the standing panel cannot convene.
    """
    if registry is None:
        return {"signal": False, "gap_domains": [], "suggested_agents": []}
    panel = set(synth.get("disciplines_silent", [])) | set()
    # which lanes does this center already cover (its own + adjacent panels)?
    covered_lanes = set()
    for a in synth.get("disciplines_silent", []):
        pass  # silent agents have no lane info here; use notes/flags instead
    gap_domains = []
    suggested = []
    # look at evidence text for domain keywords not represented in panel
    evidence_text = " ".join(
        f.get("evidence", "") + " " + f.get("description", "")
        for f in synth.get("flags", []) + synth.get("notes", [])
    ).lower()
    # candidate gap domains from registry lanes
    seen_lanes = set()
    for slug, meta in registry.items():
        lane = meta.get("lane", "")
        if lane and lane not in seen_lanes:
            seen_lanes.add(lane)
    # if a finding's agent lane is absent from the panel's disciplines, it's a gap
    panel_disciplines = set(synth.get("disciplines_fired_names", [])) if isinstance(
        synth.get("disciplines_fired_names"), list) else set()
    # pragmatic: any flag whose agent is NOT in this center's known panel
    center_panel = set(synth.get("center_panel", []))
    for f in synth.get("flags", []) + synth.get("notes", []):
        ag = f.get("agent", "")
        if ag and ag not in center_panel and ag not in panel_disciplines:
            # this finding came from an agent outside the standing panel ->
            # emergence signal if that agent's domain isn't covered
            gap_domains.append(ag)
            if ag in registry and ag not in suggested:
                suggested.append(ag)
    signal = len(suggested) > 0
    return {"signal": signal, "gap_domains": gap_domains,
            "suggested_agents": suggested[:6]}


def propose_daughter(center_slug, center_state, registry, threshold=3):
    """Daughter-center formation from emergence telemetry (the full
    autonomous loop): if a center keeps spawning the SAME gap team over and
    over, that's a recurring competence need no standing center covers — so
    we propose a NEW daughter center built from the most-frequently-spawned
    agents.

    This is a PROPOSAL only. It becomes real only after the Laura gate
    (see /evolve in runtime.py) — never auto-instantiated. Honest: we report
    the recurrence signal + the proposed panel; we do NOT invent a mandate.

    Returns {propose: bool, reason, proposed_slug, proposed_panel[], spawn_count}.
    """
    log = center_state.get("spawned_teams_log", [])
    if len(log) < threshold:
        return {"propose": False, "reason": "insufficient spawn history",
                "spawn_count": len(log)}
    # count agent frequency across all spawns
    freq: dict = {}
    for entry in log:
        for a in entry.get("agents", []):
            freq[a] = freq.get(a, 0) + 1
    # the recurring core: agents spawned in >= half of all spawns
    core = sorted([a for a, n in freq.items() if n >= max(2, len(log) // 2)])
    if len(core) < 2:
        return {"propose": False, "reason": "no recurring agent cluster",
                "spawn_count": len(log)}
    # validate against registry (never propose a fabricated agent)
    core = [a for a in core if a in registry] if registry else core
    if len(core) < 2:
        return {"propose": False, "reason": "recurring agents not in registry",
                "spawn_count": len(log)}
    slug = f"{center_slug}-daughter-{len(log)}"
    return {"propose": True,
            "reason": f"center spawned {len(log)} teams; agents {core} recur",
            "proposed_slug": slug, "proposed_panel": core[:6],
            "spawn_count": len(log),
            "agent_frequency": freq}


