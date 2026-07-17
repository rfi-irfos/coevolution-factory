# factory/runtime.py — turns the 50-center catalog into 50 LIVE, autonomous
# interdisciplinary CENTERS over the real lauras-agents engine.
#
# Design (per doctrine):
#  - 50 distinct, standing interdisciplinary centers (not document processors).
#  - Each center convenes a broad, REAL panel spanning Legal/Risk/AI-Safety/
#    Finance/Ops/Security/Exec — assembled from the real 292-agent registry.
#  - Cross-center network: centers re-synthesize across their real graph
#    adjacency (derived from agents.md feeds_into).
#  - 100% autonomous OPERATION: signup, key issue, panel session, billing,
#    content all run without a human. Human-owned: legal entity, banking,
#    Laura gate on public copy.
#  - We only track the CASHFLOW: the Observatory endpoint shows per-center
#    sessions + revenue only. No human-in-the-loop on the money path.
#
# ENGINE NOTE: FT_ENGINE_KEY is read from env (set as a REAL Fly secret in
# prod, NOT 'local'). If the key is missing/'local' AND the engine is remote,
# the service degrades to a deterministic DEMO so nothing breaks publicly; it
# never silently authorizes against a gated engine or fakes findings.
#
# Routes:
#  POST /signup?center=<slug>        -> issue entitlement key for THAT center
#  POST /api/center?center=<slug>    -> convene the panel + cross-synthesis
#  POST /api/center/scenario         -> what-if simulation through the panel
#  POST /api/center/healthcheck      -> standing posture snapshot
#  GET  /observatory                 -> cashflow only
#  GET  /network                     -> cross-center adjacency graph
#  GET  /<slug>                      -> that center's public page
#  GET  /health
#  POST /stripe/webhook              -> real Stripe webhook (WHSEC-verified)

import os, json, secrets, time, asyncio, hmac, hashlib
from pathlib import Path
from aiohttp import web, ClientSession, ClientError, ClientTimeout

from catalog import CENTERS_META, CENTER_NETWORK, _REG
from stripe_links import STRIPE_LINKS, link_for_factory
from synthesis import local_synthesize, engine_synthesize, propagate_tensions, detect_emergence, propose_daughter

HERE = Path(__file__).parent
# State lives on a mounted volume (/data) when present, so all machines share
# one cashflow/key store instead of diverging per-instance.
STATE_DIR = os.environ.get("FT_STATE_DIR", str(HERE))
DB = Path(STATE_DIR) / "state.json"
ENGINE_URL = os.environ.get("FT_ENGINE_URL", "http://localhost:8080")
ENGINE_KEY = os.environ.get("FT_ENGINE_KEY", "local")
STRIPE_WHSEC = os.environ.get("STRIPE_WHSEC", "")  # set as Fly secret in prod
# Demo mode: only when key is 'local' AND engine is remote. Never fakes gated
# engine output into a real (non-demo) answer.
DEMO_MODE = (ENGINE_KEY == "local"
             and ENGINE_URL.startswith("http"))

CENTERS = CENTERS_META
CENTER_SLUGS = list(CENTERS.keys())


JOB_TTL = int(os.environ.get("FT_JOB_TTL", "86400"))  # 24h


def load_state():
    if DB.exists():
        s = json.loads(DB.read_text())
        s.setdefault("jobs", {})
        s.setdefault("spawned_teams", {})
        return s
    return {"keys": {}, "usage": [], "jobs": {}, "spawned_teams": {}}


def prune_old(s):
    """Drop finished jobs/teams older than JOB_TTL so state.json stays bounded.
    Keeps the usage log (cashflow telemetry) and keys (auth) untouched."""
    now = time.time()
    for bucket in ("jobs", "spawned_teams"):
        if bucket not in s:
            continue
        old = [k for k, v in s[bucket].items()
               if (v.get("status") in ("done", "error"))
               and now - v.get("created", 0) > JOB_TTL]
        for k in old:
            del s[bucket][k]
    return s


def save_state(s):
    prune_old(s)
    DB.write_text(json.dumps(s, indent=2))


state = load_state()

# Rehydrate autonomous daughter centers (formed at runtime via the Laura-gated
# /evolve flow) so they survive restarts. They live in state.json, not catalog.py.
for _dslug, _dspec in state.get("daughter_centers", {}).items():
    if _dslug not in CENTERS:
        CENTERS[_dslug] = _dspec
        CENTER_SLUGS.append(_dslug)
        _parent = _dspec.get("parent")
        if _parent:
            CENTER_NETWORK.setdefault(_dslug, [_parent])
            CENTER_NETWORK.setdefault(_parent, [])
            if _parent not in CENTER_NETWORK[_dslug]:
                CENTER_NETWORK[_dslug].append(_parent)


# --------------------------------------------------------------------------
# Engine call: convene a real panel through the live engine. The engine
# returns per-agent responses; we then run a deterministic cross-synthesis
# locally (collation of the panel's own findings — no extra LLM call, no
# fabrication).
# --------------------------------------------------------------------------
async def call_engine(text, agents, scenario=None):
    payload = {"text": text, "agents": agents, "metadata": None}
    if scenario:
        payload["scenario"] = scenario
    headers = {"Authorization": f"Bearer {ENGINE_KEY}",
               "Content-Type": "application/json"}
    try:
        async with ClientSession() as s:
            async with s.post(f"{ENGINE_URL}/pool/team", headers=headers,
                              json=payload,
                              timeout=ClientTimeout(total=600)) as r:
                upstream = await r.json(); status = r.status
    except ClientError as e:
        return None, 502, str(e)
    return upstream, status, None


def cross_synthesize(upstream, panel):
    """Deterministic synthesis of the panel's OWN findings. Does not invent
    anything: it aggregates real severities, surfaces conflicts between
    disciplines, and reports a center-level posture. No LLM call.

    NOTE on matching: the engine returns each response keyed by the agent's
    *display name* (e.g. "GDPR", "Privacy Law"), not its registry slug
    ("risk-gdpr"). So we normalize: a response matches a panel member when
    the slug OR the slugified name appears in the engine's agent label.
    """
    responses = upstream.get("responses", []) if isinstance(upstream, dict) else []
    # normalize panel slugs -> a lookup that also accepts the display name
    def norm(s):
        return s.lower().replace("-", "").replace("_", "")
    panel_norm = {norm(a): a for a in panel}
    flags, notes = [], []
    fired, silent = set(), []
    for r in responses:
        label = r.get("agent", "")
        # find which panel member this response belongs to
        member = None
        for pn, orig in panel_norm.items():
            if pn in norm(label) or norm(label) in pn or norm(label) == pn:
                member = orig
                break
        if member is None:
            member = label  # engine returned an agent not in our panel list
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
    # conflict detection: same evidence flagged by one discipline, cleared by
    # another is surfaced as a tension for human/Laura review.
    conflicts = []
    flag_ev = {f["evidence"] for f in flags if f["evidence"]}
    for n in notes:
        if n["evidence"] and n["evidence"] in flag_ev:
            conflicts.append({"evidence": n["evidence"],
                              "flag_by": [f["agent"] for f in flags
                                          if f["evidence"] == n["evidence"]],
                              "note_by": n["agent"]})
    posture = "stable"
    if len(flags) >= 3:
        posture = "elevated"
    elif len(flags) >= 1:
        posture = "watch"
    return {
        "posture": posture,
        "panel_size": len(panel),
        "disciplines_fired": len(fired),
        "disciplines_silent": silent,
        "flags": flags,
        "notes": notes,
        "conflicts": conflicts,
        "flag_count": len(flags),
        "note_count": len(notes),
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
async def health(request):
    return web.json_response({
        "status": "ok", "centers": len(CENTERS),
        "engine": ENGINE_URL, "mode": "demo" if DEMO_MODE else "live",
    })


async def signup(request):
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response(
            {"error": "unknown center", "valid": CENTER_SLUGS}, status=404)
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = (data.get("email") or "").strip().lower()
    if "@" not in email:
        return web.json_response({"error": "valid email required"}, status=400)
    key = f"ct_{center}_" + secrets.token_hex(12)
    state["keys"][key] = {"center": center, "email": email,
                          "created": int(time.time()), "sessions": 0}
    save_state(state)
    return web.json_response({"key": key, "center": c["name"],
                              "free_sessions": c["free"],
                              "price_eur": c["price"]})


async def require_key(request, center):
    auth = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    acct = state["keys"].get(auth)
    if not acct or acct["center"] != center:
        return None, web.json_response(
            {"error": "invalid key for this center"}, status=401)
    return acct, None


async def center_session(request):
    """Convene the panel on a question. Returns a run_id immediately; the panel
    review runs in the background (the engine reviews agents sequentially and
    can take 30-60s). Poll /api/center/result/{run_id} for the synthesis."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_key(request, center)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "missing 'text'"}, status=400)

    panel = c["panel"]
    run_id = "run_" + secrets.token_hex(10)
    state.setdefault("jobs", {})[run_id] = {
        "center": center, "status": "queued", "created": int(time.time()),
        "text": text[:500], "panel": panel, "result": None, "error": None}
    save_state(state)
    # fire-and-forget: run the (slow) engine review off the request path
    spawn_background(run_panel_job(run_id, center, text, panel, c, acct))
    return web.json_response({"run_id": run_id, "status": "queued",
                              "poll": f"/api/center/result/{run_id}"})


async def run_panel_job(run_id, center, text, panel, c, acct):
    """Background worker: convene the panel via the engine, synthesize, store."""
    try:
        if DEMO_MODE:
            synth = {"posture": "demo", "panel_size": len(panel),
                     "disciplines_fired": 0, "disciplines_silent": panel,
                     "flags": [], "notes": [], "conflicts": [],
                     "flag_count": 0, "note_count": 0,
                     "demo_note": "engine key not configured — connect FT_ENGINE_KEY"}
            upstream_status = "demo"
        else:
            upstream, status, detail = await call_engine(text, panel)
            if upstream is None:
                state["jobs"][run_id].update(
                    {"status": "error", "error": f"engine unreachable: {detail}"})
                save_state(state)
                return
            synth = await engine_synthesize(upstream, panel, ENGINE_URL, ENGINE_KEY)
            upstream_status = status
        acct["sessions"] += 1
        cost = 0.0 if acct["sessions"] <= c["free"] else c["price"]
        state["usage"].append({"center": center, "ts": int(time.time()),
                               "cost": cost, "mode": "demo" if DEMO_MODE else "live"})
        fac_state = state.setdefault("centers", {}).setdefault(center, {"version": 1})
        fac_state.setdefault("sessions_log", []).append(
            {"ts": int(time.time()), "panel": panel, "cost": cost,
             "posture": synth.get("posture")})
        # cross-center tension propagation (metadata only, no fabrication)
        shared = propagate_tensions(center, synth, CENTER_NETWORK)
        # emergence: does this panel's findings reveal a competence gap that
        # no standing center covers? if so, surface it (a new intra-company
        # team can be spawned on demand via /api/center/spawn).
        emergence = detect_emergence(center, {**synth, "center_panel": panel},
                                      _REG if _REG else None)
        state["jobs"][run_id].update(
            {"status": "done", "synthesis": synth,
             "upstream_status": upstream_status, "demo": DEMO_MODE,
             "cross_center_tensions": shared,
             "adjacent_centers": CENTER_NETWORK.get(center, []),
             "emergence": emergence,
             "billed_eur": cost})
    except Exception as e:
        state["jobs"][run_id].update({"status": "error", "error": str(e)})
    save_state(state)


async def panel_result(request):
    """Poll endpoint for an async panel run."""
    run_id = request.match_info.get("run_id", "")
    job = state.get("jobs", {}).get(run_id)
    if not job:
        return web.json_response({"error": "unknown run_id"}, status=404)
    return web.json_response(job)


async def scenario_session(request):
    """What-if simulation: run a proposed action through the panel."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_key(request, center)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    action = (body.get("action") or "").strip()
    context = (body.get("context") or "").strip()
    if not action:
        return web.json_response({"error": "missing 'action'"}, status=400)
    text = f"PROPOSED ACTION: {action}\nCONTEXT: {context}"
    panel = c["panel"]
    if DEMO_MODE:
        synth = {"posture": "demo", "panel_size": len(panel),
                 "demo_note": "engine key not configured — connect FT_ENGINE_KEY"}
        upstream_status = "demo"
    else:
        upstream, status, detail = await call_engine(text, panel, scenario=action)
        if upstream is None:
            return web.json_response(
                {"error": "engine unreachable", "detail": detail}, status=502)
        synth = await engine_synthesize(upstream, panel, ENGINE_URL, ENGINE_KEY)
        upstream_status = status
    return web.json_response({"center": c["name"],
                              "scenario": action,
                              "upstream_status": upstream_status,
                              "synthesis": synth, "demo": DEMO_MODE})


async def healthcheck_session(request):
    """Standing posture snapshot using a center-specific standing prompt."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_key(request, center)
    if err:
        return err
    standing = (f"Standing health check for {c['name']}. Mandate: {c['mandate']}. "
                f"Assess current exposure across your disciplines.")
    panel = c["panel"]
    if DEMO_MODE:
        synth = {"posture": "demo", "panel_size": len(panel),
                 "demo_note": "engine key not configured — connect FT_ENGINE_KEY"}
        upstream_status = "demo"
    else:
        upstream, status, detail = await call_engine(standing, panel)
        if upstream is None:
            return web.json_response(
                {"error": "engine unreachable", "detail": detail}, status=502)
        synth = await engine_synthesize(upstream, panel, ENGINE_URL, ENGINE_KEY)
        upstream_status = status
    return web.json_response({"center": c["name"],
                              "upstream_status": upstream_status,
                              "synthesis": synth, "demo": DEMO_MODE})


async def spawn_session(request):
    """Autonomous emergence: when a center's panel surfaces a competence gap
    no standing center covers, spin up a NEW intra-company team on demand.
    The new team is convened through the live engine with agents drawn from
    the real 292-agent registry (matching the gap domain). Persisted as a
    spawned_team so the center can re-convene it without re-deriving.

    This is the 'true autonomous full-stack' path: centers don't just analyze,
    they assemble the expertise they're missing. New *daughter centers* (not
    just teams) still require the Laura gate (see /evolve)."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_key(request, center)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    text = (body.get("text") or "").strip()
    gap = body.get("gap_agents") or []  # explicit agent slugs to convene
    if not text:
        return web.json_response({"error": "missing 'text'"}, status=400)

    # derive the gap team: explicit slugs, else reuse the last emergence signal
    if not gap and isinstance(body.get("use_last_emergence"), bool) and body.get("use_last_emergence"):
        last = (state.get("centers", {}).get(center, {})
                .get("sessions_log", []))
        # fall back: pull suggested agents from the most recent done job
        for j in reversed(list(state.get("jobs", {}).values())):
            if j.get("center") == center and j.get("emergence", {}).get("signal"):
                gap = j["emergence"].get("suggested_agents", [])
                break
    if not gap:
        return web.json_response(
            {"error": "no gap agents specified and no emergence signal yet",
             "hint": "run /api/center first; if emergence.signal is true, pass use_last_emergence:true"},
            status=400)

    # validate slugs against the real registry (never convene a fabricated agent)
    valid = [g for g in gap if g in _REG] if _REG else []
    if not valid:
        return web.json_response({"error": "no valid agents in gap list",
                                  "rejected": gap}, status=400)

    team_id = "team_" + secrets.token_hex(8)
    state.setdefault("spawned_teams", {})[team_id] = {
        "center": center, "agents": valid, "created": int(time.time()),
        "text": text[:500], "status": "queued"}
    save_state(state)
    spawn_background(run_spawn_job(team_id, center, text, valid, c, acct))
    return web.json_response({"team_id": team_id, "status": "queued",
                              "agents": valid,
                              "poll": f"/api/center/team/{team_id}"})


async def run_spawn_job(team_id, center, text, agents, c, acct):
    """Background worker: convene the newly spawned intra-company team."""
    try:
        if DEMO_MODE:
            synth = {"posture": "demo", "panel_size": len(agents),
                     "demo_note": "engine key not configured — connect FT_ENGINE_KEY"}
            upstream_status = "demo"
        else:
            upstream, status, detail = await call_engine(text, agents)
            if upstream is None:
                state["spawned_teams"][team_id].update(
                    {"status": "error", "error": f"engine unreachable: {detail}"})
                save_state(state)
                return
            synth = await engine_synthesize(upstream, agents, ENGINE_URL, ENGINE_KEY)
            upstream_status = status
        state["spawned_teams"][team_id].update(
            {"status": "done", "synthesis": synth,
             "upstream_status": upstream_status, "demo": DEMO_MODE})
        # record that this center spawned a team (telemetry for future daughter
        # center proposals — still Laura-gated before any new center is born)
        cs = state.setdefault("centers", {}).setdefault(center, {"version": 1})
        cs.setdefault("spawned_teams_log", []).append(
            {"ts": int(time.time()), "team_id": team_id, "agents": agents,
             "posture": synth.get("posture")})
    except Exception as e:
        state["spawned_teams"][team_id].update({"status": "error", "error": str(e)})
    save_state(state)


async def team_result(request):
    """Poll endpoint for a spawned team run."""
    team_id = request.match_info.get("team_id", "")
    team = state.get("spawned_teams", {}).get(team_id)
    if not team:
        return web.json_response({"error": "unknown team_id"}, status=404)
    return web.json_response(team)


async def propose_session(request):
    """Daughter-center proposal from emergence telemetry (the full autonomous
    loop). Reads this center's spawned_teams_log and, if a recurring agent
    cluster appears, proposes a NEW daughter center.

    PROPOSAL ONLY — it is fed into /evolve (Laura-gated) to become real. We
    never auto-instantiate a new public center. Honest: reports the recurrence
    signal + proposed panel; invents no mandate."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_key(request, center)
    if err:
        return err
    cs = state.get("centers", {}).get(center, {})
    proposal = propose_daughter(center, cs, _REG if _REG else None)
    if proposal.get("propose"):
        # stage it for the Laura-gated /evolve flow
        state.setdefault("daughter_proposals", {})[proposal["proposed_slug"]] = {
            "parent": center, "panel": proposal["proposed_panel"],
            "agent_frequency": proposal.get("agent_frequency", {}),
            "spawn_count": proposal["spawn_count"], "created": int(time.time()),
            "status": "staged"}
        save_state(state)
        proposal["status"] = "staged_for_laura_gate"
        proposal["apply_via"] = "/evolve"
    return web.json_response(proposal)


async def resolve_session(request):
    """Cross-center resolution: convene the panel, then propagate any surfaced
    tensions to the center's adjacent centers (real feeds_into adjacency) as
    shared context. Makes the 50 centers a network, not 50 silos."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_key(request, center)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "missing 'text'"}, status=400)
    panel = c["panel"]
    if DEMO_MODE:
        synth = {"posture": "demo", "panel_size": len(panel),
                 "conflicts": [], "demo_note": "engine key not configured"}
        shared = []
    else:
        upstream, status, detail = await call_engine(text, panel)
        if upstream is None:
            return web.json_response(
                {"error": "engine unreachable", "detail": detail}, status=502)
        synth = await engine_synthesize(upstream, panel, ENGINE_URL, ENGINE_KEY)
        shared = propagate_tensions(center, synth, CENTER_NETWORK)
    return web.json_response({"center": c["name"],
                              "synthesis": synth,
                              "cross_center_tensions": shared,
                              "adjacent_centers": CENTER_NETWORK.get(center, []),
                              "demo": DEMO_MODE})


# --------------------------------------------------------------------------
# Stripe webhook — REAL, with signature verification when STRIPE_WHSEC set.
# --------------------------------------------------------------------------
async def stripe_webhook(request):
    raw = await request.read()
    if STRIPE_WHSEC:
        sig = request.headers.get("Stripe-Signature", "")
        # Stripe signed-payload format: t=<ts>,v1=<hmac>
        m = __import__("re").search(r"t=(\d+),v1=([0-9a-f]+)", sig or "")
        if not m:
            return web.json_response({"error": "bad signature"}, status=400)
        ts, sig_hex = m.group(1), m.group(2)
        expect = hmac.new(STRIPE_WHSEC.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig_hex):
            return web.json_response({"error": "signature mismatch"}, status=400)
    try:
        body = json.loads(raw.decode())
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    evt = body.get("type")
    if evt == "checkout.session.completed":
        obj = body.get("data", {}).get("object", {})
        amount = obj.get("amount_total") or 0
        currency = obj.get("currency", "eur")
        paid_eur = round(amount / 100.0, 2) if currency in ("eur", "usd") else 0.0
        # factory/center is set in metadata at link-creation time. To make this
        # work, the Stripe link metadata must carry the center slug — see
        # stripe_links.link_for_factory which we extend to embed metadata.
        factory = (obj.get("metadata") or {}).get("center") or \
                  (obj.get("metadata") or {}).get("factory") or "unknown"
        state.setdefault("payments", []).append({
            "ts": int(time.time()), "eur": paid_eur, "center": factory,
            "session": obj.get("id"), "link": obj.get("payment_link"),
        })
        save_state(state)
        return web.json_response(
            {"ok": True, "recorded_eur": paid_eur, "center": factory})
    return web.json_response({"ok": True, "ignored": evt})


async def observatory(request):
    # CASHFLOW ONLY. No human in the money path.
    by_center = {slug: {"name": c["name"], "sessions": 0, "revenue_eur": 0.0,
                        "paid_eur": 0.0,
                        "stripe_link": link_for_factory(slug, c["price"])}
                 for slug, c in CENTERS.items()}
    for u in state["usage"]:
        bc = by_center.get(u.get("center"))
        if bc:
            bc["sessions"] += 1
            bc["revenue_eur"] += u["cost"]
    for p in state.get("payments", []):
        bc = by_center.get(p.get("center"))
        if bc:
            bc["paid_eur"] += p["eur"]
    total_sessions = sum(b["sessions"] for b in by_center.values())
    total_rev = round(sum(b["revenue_eur"] for b in by_center.values()), 2)
    total_paid = round(sum(b["paid_eur"] for b in by_center.values()), 2)
    active = [s for s, b in by_center.items() if b["sessions"] > 0]
    return web.json_response({
        "centers_total": len(by_center),
        "centers_active": len(active),
        "total_sessions": total_sessions,
        "total_revenue_eur": total_rev,
        "total_paid_eur": total_paid,
        "stripe_account": "RFI-IRFOS (verified link pool, %d links)" % len(STRIPE_LINKS),
        "cashflow": {s: {"name": b["name"], "sessions": b["sessions"],
                         "revenue_eur": round(b["revenue_eur"], 2),
                         "paid_eur": round(b["paid_eur"], 2),
                         "stripe_link": b["stripe_link"]}
                     for s, b in by_center.items()},
    })


async def network(request):
    return web.json_response({
        "centers": CENTER_SLUGS,
        "edges": {k: v for k, v in CENTER_NETWORK.items()},
        "adjacency_count": {k: len(v) for k, v in CENTER_NETWORK.items()},
    })


def center_page(slug):
    c = CENTERS[slug]
    stripe_link = link_for_factory(slug, c["price"])
    panel_list = ", ".join(c["panel"])
    disc_list = ", ".join(c["disciplines"])
    adj = CENTER_NETWORK.get(slug, [])
    adj_links = "".join(
        f'<a href="/{a}"><b>{CENTERS[a]["name"]}</b></a>'
        for a in adj[:8])
    # typical-questions + icp-pain blocks (built as plain strings, not in
    # the f-string, to avoid nested-comprehension f-string syntax limits)
    ucs = c.get("use_cases") or []
    use_cases_html = "".join(
        '<button type=button class=uc style="display:block;width:100%;'
        'text-align:left;margin:6px 0;background:#0f141d;border:1px solid '
        '#1c2733;border-radius:8px;padding:10px 12px;color:#e6edf3;'
        'cursor:pointer;font:inherit;font-size:13px" '
        f'data-q="{uc.replace(chr(34), "&quot;")}">{uc}</button>'
        for uc in ucs) if ucs else ""
    icp_pain_html = (
        f'<div style="margin-top:12px;font-size:13px;color:#ffb38a">'
        f'⚠ {c["icp_pain"]}</div>') if c.get("icp_pain") else ""
    page = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{c['name']} — interdisciplinary center</title>
<style>body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{max-width:860px;margin:0 auto;padding:0 22px}}
nav{{border-bottom:1px solid #1c2733;padding:18px 0}}
.brand{{font-weight:600}} .ey{{color:#36d6a0;font-size:12px;letter-spacing:.12em;text-transform:uppercase}}
h1{{font-size:32px;margin:30px 0 10px;font-weight:650}}
.sub{{color:#8b98a9;font-size:16px;max-width:640px}}
.box{{background:#0f141d;border:1px solid #1c2733;border-radius:10px;padding:18px;margin-top:24px}}
button{{background:#14202e;color:#cfe6ff;border:1px solid #2c4258;border-radius:8px;padding:9px 16px;cursor:pointer}}
.buy{{background:#1b3a2a;border-color:#2c6b4a;color:#9ff0c8;text-decoration:none;display:inline-block;padding:10px 18px;border-radius:8px;margin-top:14px}}
input,textarea{{width:100%;padding:10px;background:#070b10;border:1px solid #1c2733;border-radius:8px;color:#e6edf3;margin:8px 0;font-family:inherit}}
pre{{background:#070b10;border:1px solid #1c2733;border-radius:8px;padding:12px;overflow:auto;font-size:12px;max-height:260px}}
.small{{color:#5b6675;font-size:12px}} a{{color:#4ea1ff}}
.disc{{display:inline-block;background:#11202e;border:1px solid #21384a;border-radius:14px;padding:3px 10px;margin:3px;font-size:12px;color:#9fd0ff}}
.tab{{display:inline-block;padding:8px 14px;cursor:pointer;color:#8b98a9}}
.tab.on{{color:#e6edf3;border-bottom:2px solid #36d6a0}}
.val{{background:#0f1a14;border:1px solid #1c3a2a;border-radius:8px;padding:6px 10px;font-size:12px;color:#cfe6ff;margin:4px 0}}
.out{{background:#070b10;border:1px solid #1c2733;border-radius:8px;padding:12px;margin-top:6px;font-size:13px;min-height:60px;white-space:normal;line-height:1.5}}
button:disabled{{opacity:.6;cursor:default}}
.tab{{margin-right:6px;user-select:none}}
.tab:hover{{color:#cfe6ff}}
@media(max-width:620px){{.tab{{display:block;margin:4px 0;border-bottom:none!important}}}}</style></head>
<body><nav><div class=wrap><span class=brand>{c['name']}</span> · <span class=small>a CoEvolution AI center</span></div></nav>
<div class=wrap>
<style>.val{{background:#0f1a14;border:1px solid #1c3a2a;border-radius:8px;padding:6px 10px;font-size:12px;color:#cfe6ff;margin:4px 0}}.out{{background:#070b10;border:1px solid #1c2733;border-radius:8px;padding:12px;margin-top:6px;font-size:13px;min-height:60px;white-space:normal;line-height:1.5}}button:disabled{{opacity:.6;cursor:default}}.tab{{margin-right:6px;user-select:none}}.tab:hover{{color:#cfe6ff}}@media(max-width:620px){{.tab{{display:block;margin:4px 0;border-bottom:none!important}}}}</style>
<div class=ey>standing interdisciplinary center · live engine · payments via RFI-IRFOS</div>
<h1>{c['name']}</h1>
<p class=sub>{c['mandate']}.<br><br><b>Why crisis-resistant:</b> {c['resilient']}<br><br><span style=color:#8b98a9>The engine is a decision-support tool that surfaces expert perspectives; it is not a substitute for qualified counsel.</span></p>
<div class=box style="border-color:#2c6b4a">
<div style="display:flex;gap:8px;flex-wrap:wrap">
<div class=val>🛡 <b>{len(c['panel'])} experts</b> across {len(c['disciplines'])} disciplines review your question</div>
<div class=val>🔁 simulate a decision before you ship it</div>
<div class=val>📡 continuous standing posture check</div>
</div>
<div style="margin-top:14px;font-size:13px;color:#9fd0ff">price: first {c['free']} sessions free, then <b>EUR {c['price']}/session</b> · built for {c['icp']}</div>
</div>
{icp_pain_html}
<div style="margin-top:18px"><div class=small style="color:#8b98a9;text-transform:uppercase;letter-spacing:.1em;font-size:11px">typical questions this center answers</div>
<div style="margin-top:8px">
{use_cases_html}
</div>
<div class=small style="margin-top:6px;color:#5b6675">click a question to drop it into the panel ↓</div>
</div>
<div class=box>
<div class=tab id=t1 class=on>1 · Convene panel</div><div class=tab id=t2>2 · Scenario sim</div><div class=tab id=t3>3 · Standing check</div>
<div style="margin-top:14px"><input id=email placeholder="you@company.com"><button id=su>issue key</button>
<div class=small>key: <span id=key style=color:#36d6a0>—</span> <span style=color:#5b6675>(saved on this device)</span></div></div>
<div id=ctxwrap style="display:none;margin-top:8px"><input id=ctx placeholder="optional context for the scenario"></div>
<div style="margin-top:10px"><textarea id=doc placeholder="{c['sample_question']}"></textarea>
<button id=run>convene panel</button><span id=runlabel style="display:none">convene panel</span>
<div class=small id=bill style="margin-top:8px">issue a key above — first runs are free</div></div>
<div class=small style="margin-top:14px">result</div>
<div id=out class=out>awaiting…</div>
<a class=buy href="{stripe_link}" target="_blank" rel="noopener">Sponsor this center / buy sessions →</a>
<div class=small style="margin-top:8px">Secure payment via RFI-IRFOS Stripe.</div>
</div>
<div style="margin-top:24px"><div class=small>adjacent centers (shared expertise graph):</div>
<div style="margin-top:8px">{adj_links or '—'}</div></div>
</div></body>
"""
    js = r"""const $=id=>document.getElementById(id);const slug='__SLUG__';
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
try{const k=localStorage.getItem('ct_'+slug);if(k)$('key').textContent=k;}catch(e){}
function renderSynth(s,demo){if(!s)return '<span style=color:#8b98a9>no synthesis</span>';
 const posture=s.posture||'unknown';
 const color=posture==='stable'?'#36d6a0':posture==='watch'?'#e8c14a':posture==='elevated'?'#ff8a8a':'#8b98a9';
 let h='<div style="margin:4px 0 10px"><b style="color:'+color+'">POSTURE: '+posture.toUpperCase()+'</b> · '+(s.disciplines_fired||0)+'/'+(s.panel_size||0)+' disciplines responded';
 if(demo)h+=' · <span style=color:#e8c14a>DEMO MODE (engine key not configured)</span>';h+='</div>';
 (s.flags||[]).forEach(f=>{h+='<div style="border-left:3px solid #ff8a8a;padding:6px 10px;margin:6px 0;background:#1a1014"><b>⚠ '+esc(f.agent)+'</b> <span style=color:#ff8a8a>['+esc(f.severity)+']</span><br>'+esc(f.description);if(f.evidence)h+='<div style=color:#8b98a9;font-size:12px>evidence: '+esc(f.evidence)+'</div>';h+='</div>';});
 (s.conflicts||[]).forEach(cf=>{h+='<div style="border-left:3px solid #e8c14a;padding:6px 10px;margin:6px 0;background:#1a1710"><b>Tension</b> — flagged by '+esc((cf.flag_by||[]).join(', '))+' but cleared by '+esc(cf.note_by||'')+'<div style=color:#8b98a9;font-size:12px>evidence: '+esc(cf.evidence||'')+'</div></div>';});
 (s.notes||[]).slice(0,12).forEach(n=>{h+='<div style="border-left:3px solid #2c4258;padding:6px 10px;margin:6px 0;background:#0f141d"><b>'+esc(n.agent)+'</b><br>'+esc(n.description);if(n.evidence)h+='<div style=color:#8b98a9;font-size:12px>evidence: '+esc(n.evidence)+'</div>';h+='</div>';});
 if(!(s.flags||[]).length&&!(s.notes||[]).length&&!(s.conflicts||[]).length)h+='<div style=color:#8b98a9>No flags or notes returned.</div>';
 return h;}
function poll(run_id){return new Promise(res=>{const tick=async()=>{try{const r=await fetch('/api/center/result/'+run_id);const j=await r.json();
  if(j.status==='done'){res(j);}else if(j.status==='error'){$('out').innerHTML='<span style=color:#ff8a8a>error: '+esc(j.error||'unknown')+'</span>';res(j);}
  else{$('out').innerHTML='<span style=color:#9fd0ff>Panel convening… ('+esc(j.status)+') — usually 30–60s</span>';setTimeout(tick,3000);}}catch(e){$('out').innerHTML='<span style=color:#ff8a8a>poll failed: '+esc(e)+'</span>';res({});}};tick();});}
async function su(){const r=await fetch('/signup?center='+slug,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('email').value})});const j=await r.json();
 if(j.key){$('key').textContent=j.key;try{localStorage.setItem('ct_'+slug,j.key);}catch(e){}$('bill').textContent='✓ key issued — first '+j.free_sessions+' sessions free, then EUR '+j.price_eur+'/session';}
 else{$('out').innerHTML='<span style=color:#e8c14a>'+esc(JSON.stringify(j))+'</span>';}}
async function run(){const k=$('key').textContent;if(k==='—'||!k){$('out').innerHTML='<span style=color:#e8c14a>issue a key first (top of panel)</span>';return;}
 const tab=window._tab||'t1';const doc=$('doc').value.trim();
 if(tab==='t1'){if(!doc){$('out').innerHTML='<span style=color:#e8c14a>enter your question above</span>';return;}
  $('run').disabled=true;$('run').textContent='convening…';$('out').innerHTML='<span style=color:#9fd0ff>Queued — convening the panel now…</span>';
  const r=await fetch('/api/center?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({text:doc})});const j=await r.json();
  if(j.run_id){const fin=await poll(j.run_id);$('run').disabled=false;$('run').textContent=$('runlabel').textContent;
   if(fin.synthesis){$('out').innerHTML=renderSynth(fin.synthesis,fin.demo);if(fin.billed_eur!==undefined)$('bill').textContent='billed EUR '+fin.billed_eur;}}
  else{$('out').innerHTML='<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';$('run').disabled=false;$('run').textContent=$('runlabel').textContent;}}
 else if(tab==='t2'){if(!doc){$('out').innerHTML='<span style=color:#e8c14a>describe the proposed action</span>';return;}
  $('run').disabled=true;$('run').textContent='simulating…';$('out').innerHTML='<span style=color:#9fd0ff>Running scenario through the panel…</span>';
  const r=await fetch('/api/center/scenario?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({action:doc,context:($('ctx').value||'')})});const j=await r.json();
  $('run').disabled=false;$('run').textContent=$('runlabel').textContent;
  $('out').innerHTML=j.synthesis?renderSynth(j.synthesis,j.demo):'<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';}
 else{$('run').disabled=true;$('run').textContent='checking…';$('out').innerHTML='<span style=color:#9fd0ff>Running standing posture check…</span>';
  const r=await fetch('/api/center/healthcheck?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({})});const j=await r.json();
  $('run').disabled=false;$('run').textContent=$('runlabel').textContent;
  $('out').innerHTML=j.synthesis?renderSynth(j.synthesis,j.demo):'<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';}}
function showTab(n){['t1','t2','t3'].forEach(t=>$(t).classList.toggle('on',t===n));
 $('ctxwrap').style.display=(n==='t2')?'block':'none';
 $('runlabel').textContent=n==='t1'?'convene panel':(n==='t2'?'simulate scenario':'run standing check');
 $('doc').placeholder=n==='t1'?__SAMPLE__:(n==='t2'?'PROPOSED ACTION — e.g. we ship X without a DPIA':'standing check needs no input');
 window._tab=n;}
['t1','t2','t3'].forEach(t=>$(t).onclick=()=>showTab(t));showTab('t1');
document.querySelectorAll('.uc').forEach(b=>b.onclick=()=>{const q=b.getAttribute('data-q')||b.textContent;$('doc').value=q;showTab('t1');$('doc').scrollIntoView({behavior:'smooth',block:'center'});});
$('su').onclick=su;$('run').onclick=run;"""
    js = js.replace("__SLUG__", slug).replace("__SAMPLE__", json.dumps(c["sample_question"]))
    return page + "<script>" + js + "</script></body></html>"



async def center_page_handler(request):
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    return web.Response(text=center_page(slug), content_type="text/html")


async def index(request):
    q = request.query.get("q", "").strip().lower()
    if q:
        matches = {s: c for s, c in CENTERS.items()
                   if q in c["name"].lower() or q in c["mandate"].lower()
                   or any(q in d.lower() for d in c["disciplines"])}
    else:
        matches = dict(CENTERS.items())
    cards = "".join(
        f'<div style="background:#0f141d;border:1px solid #1c2733;border-radius:8px;padding:12px;margin:6px">'
        f'<a href="/{s}"><b>{c["name"]}</b></a><br>'
        f'<span style="color:#8b98a9;font-size:13px">{c["mandate"]}</span></div>'
        for s, c in matches.items())
    hint = f'{len(matches)} centers match "{q}"' if q else f"{len(matches)} standing interdisciplinary centers"
    return web.Response(text=f"""<!doctype html><html><head><meta charset=utf-8>
<title>CoEvolution AI — 50 interdisciplinary centers</title>
<style>body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:30px 22px}} h1{{font-size:30px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:20px}}
a{{color:#4ea1ff;text-decoration:none}}
input{{width:100%;max-width:420px;padding:10px;background:#070b10;border:1px solid #1c2733;border-radius:8px;color:#e6edf3;margin:12px 0}}</style></head><body><div class=wrap>
<h1>50 autonomous interdisciplinary centers</h1>
<p style="color:#8b98a9">Each a distinct, crisis-resistant standing body of experts, convened across the live 292-agent engine. We only track the cashflow. <a href="/observatory">→ Observatory</a> · <a href="/network">→ Center network</a></p>
<form method=get><input name=q placeholder="search by problem, discipline or center (e.g. GDPR, security, hiring)" value="{q}"></form>
<p class=small style="color:#5b6675;font-size:13px">{hint}</p>
<div class=grid>{cards}</div></div></body></html>""", content_type="text/html")


async def discover(request):
    """JSON discovery: filter centers by problem/discipline/name. Powers a
    lightweight client-side filter without a full page reload."""
    q = (request.query.get("q") or "").strip().lower()
    out = []
    for s, c in CENTERS.items():
        if not q or q in c["name"].lower() or q in c["mandate"].lower() \
                or any(q in d.lower() for d in c["disciplines"]):
            out.append({"slug": s, "name": c["name"], "mandate": c["mandate"],
                        "disciplines": c["disciplines"],
                        "adjacent": CENTER_NETWORK.get(s, [])})
    return web.json_response({"query": q, "count": len(out), "centers": out})


# --------------------------------------------------------------------------
# Recursive self-improvement (Coevolution) — PROPOSE only; the daily cron
# gates each staged proposal through the REAL mcp_laura_review_plan and applies
# via /evolve/apply with a laura_pass token. No self-approve (doctrine).
# --------------------------------------------------------------------------
async def evolve_handler(request):
    """PROPOSE a recursive self-improvement cycle (does NOT apply).
    Pipeline: telemetry -> data-grounded panel rewrite -> test candidate panel
    on the LIVE engine. Returns proposals; the daily cron gates each via the
    REAL mcp_laura_review_plan (no self-approve) and applies the approved ones
    via /evolve/apply. This honors the doctrine: Laura = final ship gate."""
    import evolve as E
    center = request.query.get("center", "")
    all_centers = request.query.get("all") == "1"
    targets = [center] if (center and not all_centers) else list(CENTERS.keys())
    proposals = []
    for slug in targets:
        c = CENTERS.get(slug)
        if not c:
            continue
        tel = E.telemetry(slug, state)
        new_spec, changelog = E.evolve_panel(slug, c, tel)
        if changelog == ["no change warranted this cycle (stable)"]:
            proposals.append({"center": slug, "status": "stable"})
            continue
        # test the candidate panel on the LIVE engine (real signal)
        test_text = ("We process customer data on legitimate interest without "
                     "a DPIA and store it unencrypted.")
        if DEMO_MODE:
            test_status = "demo"
        else:
            _, test_status, detail = await call_engine(test_text, new_spec["panel"])
            if test_status == 502:
                test_status = f"engine_unreachable:{detail}"
        # stage the proposal (NOT applied). The cron carries it to Laura.
        state.setdefault("proposals", {})[slug] = {
            "spec": new_spec, "changelog": changelog,
            "test_upstream_status": test_status, "at": int(time.time())}
        save_state(state)
        proposals.append({"center": slug, "changelog": changelog,
                          "test_upstream_status": test_status, "staged": True})
    return web.json_response({"proposed": len(proposals), "proposals": proposals})


async def evolve_apply_handler(request):
    """Apply a STAGED proposal ONLY if it carries a Laura-pass token.
    Body: {"center": slug, "laura_pass": true, "kind": "panel"|"daughter"}.
    The cron sets laura_pass after mcp_laura_review_plan returns 0 FLAGs.
    No token = no apply. Daughter-center proposals are applied the same way
    (never auto-instantiated) — the gate is identical."""
    import evolve as E
    try:
        data = await request.json()
    except Exception:
        data = {}
    laura_pass = bool(data.get("laura_pass"))
    if not laura_pass:
        return web.json_response(
            {"error": "LAURA GATE BLOCKED — no laura_pass token"}, status=403)
    kind = data.get("kind", "panel")
    if kind == "daughter":
        # apply a staged daughter-center proposal: register the new center
        # from the proposal panel. Still Laura-gated above (laura_pass).
        slug = data.get("center", "")
        dp = state.get("daughter_proposals", {}).get(slug)
        if not dp:
            return web.json_response({"error": "no staged daughter proposal"},
                                     status=404)
        # build the new center spec from the proposal
        parent = dp["parent"]
        panel = dp["panel"]
        new_slug = slug
        # never overwrite an existing center
        if new_slug in CENTERS:
            return web.json_response({"error": f"center {new_slug} exists"},
                                     status=409)
        CENTERS[new_slug] = {
            "name": f"{CENTERS[parent]['name']} — Daughter {new_slug}",
            "mandate": (f"Autonomous daughter center formed from recurring "
                        f"emergence in {CENTERS[parent]['name']}. Panel: "
                        f"{', '.join(panel)}."),
            "disciplines": [p.replace('-', ' ') for p in panel],
            "panel": panel, "free": CENTERS[parent]["free"],
            "price": CENTERS[parent]["price"],
            "sample_question": CENTERS[parent].get("sample_question", ""),
            "value_prop": (f"Spawned by {CENTERS[parent]['name']} when its "
                           f"own panel kept hitting the same gap."),
            "resilient": (f"Self-formed from observed recurrence in its parent "
                          f"center; inherits the parent's resilience posture."),
            "standing_prompt": CENTERS[parent].get("standing_prompt", ""),
            "cross_center": [], "feeds_into": [], "is_daughter": True,
            "parent": parent,
        }
        CENTER_SLUGS.append(new_slug)
        CENTER_NETWORK.setdefault(new_slug, [parent])
        CENTER_NETWORK.setdefault(parent, [])
        if parent not in CENTER_NETWORK[new_slug]:
            CENTER_NETWORK[new_slug].append(parent)
        state.setdefault("centers", {})[new_slug] = {"version": 1,
                                                     "is_daughter": True,
                                                     "parent": parent}
        # persist the full spec so it survives restarts (rehydrated on boot)
        state.setdefault("daughter_centers", {})[new_slug] = {
            "name": CENTERS[new_slug]["name"],
            "mandate": CENTERS[new_slug]["mandate"],
            "disciplines": CENTERS[new_slug]["disciplines"],
            "panel": panel, "free": CENTERS[new_slug]["free"],
            "price": CENTERS[new_slug]["price"],
            "sample_question": CENTERS[new_slug].get("sample_question", ""),
            "value_prop": CENTERS[new_slug]["value_prop"],
            "resilient": CENTERS[new_slug]["resilient"],
            "standing_prompt": CENTERS[new_slug].get("standing_prompt", ""),
            "cross_center": [], "feeds_into": [], "is_daughter": True,
            "parent": parent,
        }
        state["daughter_proposals"].pop(new_slug, None)
        save_state(state)
        return web.json_response({"center": new_slug, "applied": "daughter center",
                                  "parent": parent, "panel": panel,
                                  "version": 1})
    # panel type (existing behavior)
    slug = data.get("center", "")
    staged = state.get("proposals", {}).get(slug)
    if not staged:
        return web.json_response({"error": "no staged proposal"}, status=404)
    new_v, msg = E.apply_version(state, slug, staged["spec"],
                                 staged["changelog"], True)
    state["proposals"].pop(slug, None)
    save_state(state)
    return web.json_response({"center": slug, "applied": msg, "version": new_v})


app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/discover", discover)
app.router.add_get("/health", health)
app.router.add_get("/observatory", observatory)
app.router.add_get("/network", network)
app.router.add_get("/{slug}", center_page_handler)
app.router.add_post("/signup", signup)
app.router.add_post("/api/center", center_session)
app.router.add_get("/api/center/result/{run_id}", panel_result)
app.router.add_post("/api/center/scenario", scenario_session)
app.router.add_post("/api/center/healthcheck", healthcheck_session)
app.router.add_post("/api/center/resolve", resolve_session)
app.router.add_post("/api/center/spawn", spawn_session)
app.router.add_get("/api/center/team/{team_id}", team_result)
app.router.add_post("/api/center/propose", propose_session)
app.router.add_post("/evolve", evolve_handler)
app.router.add_post("/evolve/apply", evolve_apply_handler)
app.router.add_post("/stripe/webhook", stripe_webhook)

# Background task registry so async panel jobs survive the request that
# spawned them (aiohttp cancels tasks created inside a handler once the
# response is sent). We keep strong refs here + prune finished ones.
BACKGROUND_TASKS = set()


def spawn_background(coro):
    """Schedule a coroutine to run after the response returns.

    Must NOT use asyncio.create_task() inside a request handler — aiohttp
    cancels handler-scoped tasks when the response is sent. We attach the task
    to the running event loop directly and keep a strong ref so it survives.
    """
    loop = asyncio.get_event_loop()
    task = loop.create_task(coro)
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    return task


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("FT_PORT", "8091")))
