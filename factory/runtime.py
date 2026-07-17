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

import os, json, secrets, time, asyncio, hmac, hashlib, sys, html, math
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

# First-party tracking — reuses the same self-hosted Lighthouse pixel/beacon
# rfi-irfos.com already runs (see LegalPage.tsx / PublicSite.tsx there for the
# identical pattern). No cookie, no visitor id, one row per pageview or click:
# path, referrer->source, utm_*, site, section. Disclosed at /privacy.
TRACK_URL = "https://lighthouse-rfi-irfos.fly.dev/lighthouse/api/track"
TRACK_SITE = "coevolution-factory"


# --------------------------------------------------------------------------
# Shared nav — matches rfi-irfos.com's real header (see PublicSite.tsx there:
# fixed 64px bar, wordmark + teal EKG accent, dark bg). Same partial used by
# the honeycomb landing page, every center's terrarium, and /privacy.
# --------------------------------------------------------------------------
RFI_TEAL = "#00f5c4"


def _nav_html(active=""):
    return f"""<nav class=sitenav><div class=navwrap>
<a class=brand href="/">
<svg width="22" height="18" viewBox="0 0 54 18" fill="none" style="overflow:visible;flex-shrink:0">
<polyline points="0,9 12,9 16,2 20,16 24,2 28,9 54,9" stroke="{RFI_TEAL}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg><span class=word>CoEvolution&nbsp;Factory</span>
<span class=sub>by RFI-IRFOS</span></a>
<div class=navlinks><a href="https://rfi-irfos.com" target=_blank rel=noreferrer>rfi-irfos.com ↗</a></div>
</div></nav>
<style>
.sitenav{{position:fixed;top:0;left:0;right:0;z-index:100;height:64px;background:rgba(10,14,20,.85);
backdrop-filter:blur(16px);border-bottom:1px solid #1c2733}}
.navwrap{{max-width:none;margin:0;height:64px;padding:0 28px;display:flex;align-items:center;justify-content:space-between}}
.brand{{display:flex;align-items:center;text-decoration:none;gap:8px}}
.brand .word{{font-weight:800;font-size:16px;letter-spacing:-.01em;color:#e6edf3}}
.brand .sub{{margin-left:6px;font-size:11px;color:#5b6675;letter-spacing:.04em;border-left:1px solid #1c2733;padding-left:10px}}
.navlinks{{display:flex;gap:26px;align-items:center}}
.navlinks a{{color:#8b98a9;font-size:13px;font-weight:600;text-decoration:none;letter-spacing:.02em}}
.navlinks a:hover{{color:#e6edf3}}
@media(max-width:640px){{.brand .sub{{display:none}}.navlinks{{gap:14px}}}}
</style>"""


# --------------------------------------------------------------------------
# Honeycomb layout — axial hex-coordinate spiral (the same ring-by-ring
# construction Catan itself uses to lay out a hex board), computed once
# server-side. CENTER_NETWORK is a dense expertise-adjacency graph (10-20
# edges per node), too dense to double as physical grid adjacency, so
# placement here is purely geometric/deterministic — same center always
# lands in the same tile.
# --------------------------------------------------------------------------
def _hex_ring(radius):
    if radius == 0:
        return [(0, 0)]
    dirs = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
    q, r = dirs[4][0] * radius, dirs[4][1] * radius
    out = []
    for dq, dr in dirs:
        for _ in range(radius):
            out.append((q, r))
            q, r = q + dq, r + dr
    return out


def _hex_spiral(n):
    coords = [(0, 0)]
    radius = 1
    while len(coords) < n:
        coords += _hex_ring(radius)
        radius += 1
    return coords[:n]


def _axial_to_pixel(q, r, size):
    x = size * (3 ** 0.5 * q + (3 ** 0.5 / 2) * r)
    y = size * (1.5 * r)
    return x, y


STATUS_COLOR = {"healthy": "#36d6a0", "degraded": "#f0883e", "0-status": "#f85c5c"}


def _tracker_js(section):
    """JS snippet firing one pageview beacon on load, tagged with `section`
    (a center slug, or "" for the homepage grid). Plain fetch (not
    sendBeacon — the backend's JSON extractor expects
    application/json, sendBeacon defaults to text/plain), fire-and-forget."""
    return f"""<script>(function(){{
var q=new URLSearchParams(location.search);
fetch({json.dumps(TRACK_URL)},{{method:'POST',headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{path:location.pathname,referrer:document.referrer,
utm_source:q.get('utm_source')||'',utm_medium:q.get('utm_medium')||'',
utm_campaign:q.get('utm_campaign')||'',site:{json.dumps(TRACK_SITE)},
section:{json.dumps(section)}}})}}).catch(function(){{}});
}})();</script>"""


def load_state():
    if DB.exists():
        s = json.loads(DB.read_text())
        s.setdefault("jobs", {})
        s.setdefault("spawned_teams", {})
        s.setdefault("leads", {})
        return s
    return {"keys": {}, "usage": [], "jobs": {}, "spawned_teams": {},
            "leads": {}}


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


def _normalize_center(slug, c):
    """Daughter centers spawned autonomously (see factory_spawn_agent.py /
    state["daughter_centers"]) carry a much sparser field set than the 50
    seed centers in catalog.py — e.g. no icp/resilient/price/panel at
    spawn time. Direct c['icp']-style access on a sparse daughter crashes
    center_page()/firms_grid() with a KeyError (confirmed live 2026-07-17).
    Fill in sane, honestly-labeled defaults instead of guessing values.
    Applied once at rehydration time below, so every downstream consumer
    of CENTERS[slug] — not just center_page() — gets a safe dict."""
    parent = CENTERS.get(c.get("parent")) if c.get("parent") else None
    d = dict(c)
    d.setdefault("mandate", c.get("mandate") or "Autonomous daughter center — mandate still forming")
    d.setdefault("resilient", (parent or {}).get("resilient") or "Standing, crisis-resistant by construction — inherits the network's Laura-gated spawn discipline")
    d.setdefault("panel", (parent or {}).get("panel") or [])
    d.setdefault("disciplines", (parent or {}).get("disciplines") or [])
    d.setdefault("price", (parent or {}).get("price", 0))
    d.setdefault("free", (parent or {}).get("free", 1))
    d.setdefault("icp", (parent or {}).get("icp") or "organizations covered by this center's mandate")
    d.setdefault("sample_question", (parent or {}).get("sample_question") or "What does this center currently cover?")
    d.setdefault("value_prop", c.get("value_prop"))
    d.setdefault("use_cases", c.get("use_cases") or [])
    d.setdefault("icp_pain", c.get("icp_pain"))
    return d


state = load_state()

# Rehydrate autonomous daughter centers (formed at runtime via the Laura-gated
# /evolve flow) so they survive restarts. They live in state.json, not catalog.py.
for _dslug, _dspec in state.get("daughter_centers", {}).items():
    if _dslug not in CENTERS:
        CENTERS[_dslug] = _normalize_center(_dslug, _dspec)
        CENTER_SLUGS.append(_dslug)
        _parent = _dspec.get("parent")
        if _parent:
            CENTER_NETWORK.setdefault(_dslug, [_parent])
            CENTER_NETWORK.setdefault(_parent, [])
            if _parent not in CENTER_NETWORK[_dslug]:
                CENTER_NETWORK[_dslug].append(_parent)


# --------------------------------------------------------------------------
# Resilience / 0-status subsystem (Task 1)
#
# Per-center status FSM persisted in state["center_status"]. A center never
# 500s/offlines on an engine error: it drops to "degraded" (or an explicit
# "0-status") and is served from its last cached synthesis in an honest
# "reduced mode". It auto-recovers to "healthy" on the next successful engine
# call (OQ1: no human intervention needed for recovery — only spawning/money
# stay Laura-gated).
# --------------------------------------------------------------------------
VALID_CENTER_STATUS = ("healthy", "degraded", "0-status")


def get_center_status(slug):
    """Return a center's persisted status, defaulting to 'healthy' (a center
    we have never heard from is assumed operational)."""
    rec = state.get("center_status", {}).get(slug)
    if not rec:
        return "healthy"
    return rec.get("status", "healthy")


def _sessions_for(slug, usage):
    return sum(1 for u in usage if u.get("center") == slug)


def _revenue_for(slug, usage):
    return round(sum(u.get("cost", 0.0) for u in usage
                      if u.get("center") == slug), 2)


def _leads_for(slug, leads):
    return len(leads.get(slug, []))


def _problems_for(slug, usage, deb):
    n_deb = sum(1 for d in deb.values()
                if d.get("center") == slug and d.get("status") == "done")
    return _sessions_for(slug, usage) + n_deb


def _active_job_for(slug):
    """The most recent in-flight job (queued/running, not done/error) against
    this center, if any — same state["jobs"] dict shape created in
    center_session() ({center, status, created, text, panel, result, error})
    that the existing panel-result poll() JS already reads from. Only panel
    convenes go through this async job/poll path (scenario sim and standing
    check are synchronous, no job record) so every entry here is a panel
    convene. Used by the terrarium's live-session view so a visitor can
    watch someone else's convened panel happen in real time."""
    jobs = [j for j in state.get("jobs", {}).values()
            if j.get("center") == slug and j.get("status") not in ("done", "error")]
    if not jobs:
        return None
    jobs.sort(key=lambda j: j.get("created", 0), reverse=True)
    j = jobs[0]
    return {"status": j.get("status"), "created": j.get("created")}


def _live_stats_for(slug):
    usage = state.get("usage", [])
    deb = state.get("debates", {})
    leads = state.get("leads", {})
    return {
        "slug": slug, "status": get_center_status(slug),
        "sessions": _sessions_for(slug, usage),
        "revenue_eur": _revenue_for(slug, usage),
        "leads": _leads_for(slug, leads),
        "problems": _problems_for(slug, usage, deb),
        "active_job": _active_job_for(slug),
    }


def set_center_status(slug, status, detail=None):
    """Persist a center status. Auto-recovery (OQ1): a successful engine call
    passes status='healthy' and the center silently returns to normal with a
    log line — no human resume required."""
    if status not in VALID_CENTER_STATUS:
        raise ValueError(f"invalid center status: {status!r}")
    prev = get_center_status(slug)
    rec = state.setdefault("center_status", {})
    rec[slug] = {"status": status, "detail": detail, "updated": int(time.time())}
    save_state(state)
    if prev != status:
        print(f"[resilience] center {slug}: {prev} -> {status}"
              + (f" ({detail})" if detail else ""), flush=True)
    return rec[slug]


# Per-offering product pipeline (Virtual Firm R0hne). Offerings move through
# idea -> debate -> prototype -> staged -> launched. "launched" is always
# Laura-gated at the staged->launched transition (wired in Task 4); this module
# only provides the store + seed/advance primitives.
PIPELINE_STAGES = ["idea", "debate", "prototype", "staged", "launched"]


def seed_offering(center, idea_text):
    """Create a new offering at the 'idea' stage. Returns the new offering id."""
    pipeline = state.setdefault("pipeline", {})
    oid = "offer_" + secrets.token_hex(8)
    pipeline[oid] = {
        "center": center,
        "idea": (idea_text or "")[:500],
        "stage": "idea",
        "created": int(time.time()),
        "updated": int(time.time()),
    }
    save_state(state)
    return oid


def advance_pipeline(offering_id, stage):
    """Move an offering to a new (valid) pipeline stage. Persisted."""
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"invalid pipeline stage: {stage!r}")
    pipeline = state.setdefault("pipeline", {})
    rec = pipeline.get(offering_id)
    if rec is None:
        raise KeyError(f"unknown offering: {offering_id}")
    rec["stage"] = stage
    rec["updated"] = int(time.time())
    save_state(state)
    return rec


def _last_done_job(slug):
    """Return the most recent 'done' job for a center (for reduced-mode cache
    serving). Returns None if none exists."""
    jobs = state.get("jobs", {})
    for j in reversed(list(jobs.values())):
        if j.get("center") == slug and j.get("status") == "done":
            return j
    return None


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


# ── Red-team hardening (rfi-irfos-infra-hardening doctrine) ────────────────
# In-memory sliding-window rate limiter. Bounds abusive/mutating operator
# calls (key-granted) so a leaked key cannot burn engine budget or brute the
# API. Not persistent across restarts — that's fine; it's a speed bump, not a
# court record. Tune via env without a code change.
import os as _os
_RATE_MAX = int(_os.environ.get("VF_RATE_MAX", "20"))
_RATE_WINDOW = int(_os.environ.get("VF_RATE_WINDOW", "60"))  # seconds
_RATE_HITS = {}  # (ip, route) -> list[timestamp]


def _client_ip(request):
    # Fly proxy forwards the real client in X-Forwarded-For (first hop).
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() or request.remote or "local"


def rate_limited(request, route, max_hits=_RATE_MAX, window=_RATE_WINDOW):
    """Return True if this (ip, route) exceeded max_hits in window seconds."""
    ip = _client_ip(request)
    now = time.time()
    key = (ip, route)
    hits = _RATE_HITS.setdefault(key, [])
    # drop stale
    _RATE_HITS[key] = [t for t in hits if now - t < window]
    if len(_RATE_HITS[key]) >= max_hits:
        return True
    _RATE_HITS[key].append(now)
    return False


def cors_headers(request):
    """Explicit, strict CORS: only same-origin (no wildcard) for /api/*.

    aiohttp's default is already 'no ACAO header' (safe), but we set it
    explicitly so a future CORS middleware can't accidentally open '*'."""
    origin = request.headers.get("Origin")
    # Only reflect the requesting origin if it matches our own host; never '*'.
    own_host = request.headers.get("Host", "")
    if origin and own_host and origin.split("://")[-1] == own_host:
        return {"Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type"}
    return {}  # no cross-origin grant


async def require_operator(request, center, route):
    """Combined gate for mutating operator routes: key + rate-limit + CORS.

    Returns (acct, err_response). err_response is None on success. CORS
    headers are merged into err_response when present."""
    acct, err = await require_key(request, center)
    if err:
        err.headers.update(cors_headers(request))
        return None, err
    if rate_limited(request, route):
        r = web.json_response(
            {"error": "rate limit exceeded", "retry_after": _RATE_WINDOW},
            status=429)
        r.headers["Retry-After"] = str(_RATE_WINDOW)
        r.headers.update(cors_headers(request))
        return None, r
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


def add_lead(center, kind, ref, text, outcome=None):
    """Record a CRM lead for a center from REAL visitor traffic ONLY.

    A lead is an honest, no-PII memory of an inbound question or debate:

        {ts, kind:'session'|'debate', ref:run_id, question_hash,
         outcome, center}

    The raw ``text`` is NEVER stored — only its SHA-256 hex digest
    (``question_hash``) so we can attribute/de-dupe inbound interest without
    retaining any PII. No external scrape, no fabricated contacts.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lead = {
        "ts": int(time.time()),
        "kind": kind,
        "ref": ref,
        "question_hash": digest,
        "outcome": outcome,
        "center": center,
    }
    state.setdefault("leads", {}).setdefault(center, []).append(lead)


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
                # 0-status resilience: degrade the center but DO NOT offline it.
                set_center_status(center, "degraded",
                                  detail=f"engine unreachable: {detail}")
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
        # CRM lead (Task 3): record this REAL inbound session as a lead for
        # the center. Never stores the raw question — only its hash.
        add_lead(center, "session", run_id, text,
                 outcome=synth.get("posture"))
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
        # 0-status auto-recover (OQ1): a successful engine call returns the
        # center to 'healthy' with no human intervention.
        set_center_status(center, "healthy", detail="engine call succeeded")
    except Exception as e:
        state["jobs"][run_id].update({"status": "error", "error": str(e)})
        # engine-side failure degrades the center but keeps it served.
        set_center_status(center, "degraded", detail=str(e))
    save_state(state)


# --------------------------------------------------------------------------
# Inter-center debate convener (Virtual Firm R0hne, Task 2).
#
# POST /api/center/debate?center=<slug>  body {text}
#   - requires the center's entitlement key
#   - pulls ADJACENT centers from CENTER_NETWORK (OQ3: adjacent-only quorum;
#     firm-wide is a later flag)
#   - convenes a POOLED panel = this center's own panel + every adjacent
#     center's panel
#   - runs engine_synthesize on the pooled panel, stores the resolution in
#     state['debates'][run_id]
#   - advances any related offering's pipeline stage idea -> debate
#   - surfaces a debate count + last resolution in /observatory
# --------------------------------------------------------------------------
def _build_pooled_panel(center):
    """Pooled panel = the center's own panel + adjacent centers' panels.

    Adjacent agents are appended (de-duplicated) so a debate invitation always
    reaches the adjacent centers' disciplines (OQ3 quorum)."""
    c = CENTERS.get(center, {})
    pooled = list(c.get("panel", []))
    for adj in CENTER_NETWORK.get(center, []):
        adj_meta = CENTERS.get(adj)
        if not adj_meta:
            continue
        for a in adj_meta.get("panel", []):
            if a not in pooled:
                pooled.append(a)
    return pooled


async def debate_session(request):
    """Convene an inter-center debate. Returns a run_id immediately; the
    pooled-panel review runs in the background. Poll the result endpoint for
    the resolution."""
    center = request.query.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_operator(request, center, "debate")
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "missing 'text'"}, status=400)

    adjacent = CENTER_NETWORK.get(center, [])
    pooled_panel = _build_pooled_panel(center)

    run_id = "debate_" + secrets.token_hex(10)
    state.setdefault("debates", {})[run_id] = {
        "center": center,
        "adjacent": adjacent,
        "pooled_panel": pooled_panel,
        "text": text[:500],
        "status": "queued",
        "created": int(time.time()),
        "resolution": None,
        "error": None,
    }
    save_state(state)

    # Advance a related offering (idea -> debate) once the debate resolves.
    related = None
    for oid, rec in state.get("pipeline", {}).items():
        if rec.get("center") == center and rec.get("stage") == "idea":
            related = oid
            break

    spawn_background(
        run_debate_job(run_id, center, text, pooled_panel, adjacent,
                       c, acct, related))
    return web.json_response({
        "run_id": run_id,
        "status": "queued",
        "center": center,
        "adjacent": adjacent,
        "pooled_panel_size": len(pooled_panel),
        "poll": f"/api/center/debate/result/{run_id}"})


async def run_debate_job(run_id, center, text, pooled_panel, adjacent,
                         c, acct, related_oid):
    """Background worker: run the pooled-panel debate, store resolution,
    advance a related offering's pipeline stage idea -> debate."""
    try:
        if DEMO_MODE:
            synth = {"posture": "demo", "panel_size": len(pooled_panel),
                     "disciplines_fired": 0,
                     "disciplines_silent": pooled_panel,
                     "flags": [], "notes": [], "conflicts": [],
                     "flag_count": 0, "note_count": 0,
                     "demo_note": "engine key not configured — connect FT_ENGINE_KEY"}
            upstream_status = "demo"
        else:
            upstream, status, detail = await call_engine(text, pooled_panel)
            if upstream is None:
                state["debates"][run_id].update(
                    {"status": "error",
                     "error": f"engine unreachable: {detail}"})
                save_state(state)
                return
            synth = await engine_synthesize(upstream, pooled_panel,
                                            ENGINE_URL, ENGINE_KEY)
            upstream_status = status

        # Advance a related offering's pipeline (idea -> debate).
        advanced = None
        if related_oid:
            try:
                advance_pipeline(related_oid, "debate")
                advanced = related_oid
            except Exception:
                advanced = None

        # Cross-center tension propagation (metadata only, no fabrication).
        shared = propagate_tensions(center, synth, CENTER_NETWORK)

        state["debates"][run_id].update({
            "status": "done",
            "resolution": synth,
            "upstream_status": upstream_status,
            "demo": DEMO_MODE,
            "cross_center_tensions": shared,
            "advanced_offering": advanced,
        })
        # CRM lead (Task 3): record this REAL inbound debate as a lead for the
        # center. Never stores the raw question — only its hash.
        add_lead(center, "debate", run_id, text,
                 outcome=synth.get("posture"))
    except Exception as e:
        state["debates"][run_id].update({"status": "error", "error": str(e)})
    save_state(state)


async def debate_result(request):
    """Poll endpoint for an async debate run."""
    run_id = request.match_info.get("run_id", "")
    rec = state.get("debates", {}).get(run_id)
    if not rec:
        return web.json_response({"error": "unknown run_id"}, status=404)
    return web.json_response(rec)


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
    acct, err = await require_operator(request, center, "scenario")
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
    acct, err = await require_operator(request, center, "spawn")
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
    acct, err = await require_operator(request, center, "propose")
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
# Lighthouse cashflow bridge — best-effort, fire-and-forget. If this fails the
# payment is still recorded locally in state["payments"] above; nothing about
# accepting the Stripe payment depends on Lighthouse being reachable.
# --------------------------------------------------------------------------
LIGHTHOUSE_INGEST_URL = "https://lighthouse-rfi-irfos.fly.dev/lighthouse/api/finance/coevolution-ingest"
LIGHTHOUSE_COEVOLUTION_KEY = os.environ.get("LIGHTHOUSE_COEVOLUTION_KEY", "")


async def _report_to_lighthouse(amount_eur, center, session_id):
    if not LIGHTHOUSE_COEVOLUTION_KEY or not session_id:
        return
    try:
        async with ClientSession(timeout=ClientTimeout(total=10)) as s:
            await s.post(LIGHTHOUSE_INGEST_URL,
                         headers={"X-Inbox-Key": LIGHTHOUSE_COEVOLUTION_KEY},
                         json={"session_id": session_id, "amount_eur": amount_eur,
                               "center": center})
    except (ClientError, asyncio.TimeoutError):
        pass


# --------------------------------------------------------------------------
# Stripe webhook — REAL, with signature verification when STRIPE_WHSEC set.
# --------------------------------------------------------------------------
async def stripe_webhook(request):
    raw = await request.read()
    if STRIPE_WHSEC:
        sig = request.headers.get("Stripe-Signature", "")
        # Stripe signed-payload format: t=<ts>,v1=<base64-hmac>
        import base64 as _b64
        m = __import__("re").search(r"t=(\d+),v1=([0-9a-zA-Z+/=]+)", sig or "")
        if not m:
            return web.json_response({"error": "bad signature"}, status=400)
        ts, sig_b64 = m.group(1), m.group(2)
        try:
            expect = _b64.b64decode(sig_b64)
        except Exception:
            return web.json_response({"error": "bad signature encoding"}, status=400)
        got = hmac.new(STRIPE_WHSEC.encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(got, expect):
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
        asyncio.create_task(_report_to_lighthouse(paid_eur, factory, obj.get("id", "")))
        return web.json_response(
            {"ok": True, "recorded_eur": paid_eur, "center": factory})
    return web.json_response({"ok": True, "ignored": evt})


async def trends_discover_handler(request):
    """Human-curated feed add (the (c) path): Simeon / Laura
    paste a REAL RSS/Atom URL; the agent validates it IS a feed
    and persists it to TREND_SOURCES.json (volume). No scraper,
    no API key. If Feedly search is desired, the key is set
    via `fly secrets set TREND_API_KEY=...` (never in code/chat).

    Honest governance: this is a WRITE endpoint, so it requires a
    valid center key (same as /api/center) — no anonymous feed adds.
    """
    acct, err = await require_key(request, "")
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    url = (body.get("url") or "").strip()
    if not url.startswith("http"):
        return web.json_response({"error": "missing url"}, status=400)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import factory_spawn_agent as F
    res = await F.discover_feed(url, body.get("name"))
    if not res.get("ok"):
        return web.json_response(
            {"error": res.get("reason", "rejected")}, status=400)
    return web.json_response(res)


async def trends_scan_handler(request):
    """Manual trigger for the spawn-agent scan (the (a)/(b)/(c)
    trends pipeline). Requires a valid center key (WRITE endpoint).
    Runs factory_spawn_agent.run_spawn_agent() NOW (instead of
    waiting up to 24h for the daily cron) and returns what
    it staged. PROMOTION stays Laura-gated in daily_spawn —
    this endpoint only STAGES candidates, never births centers.

    Honest: this is the "I want to see it scan now" path. The
    daily 02:00 cron still runs; this is a manual override
    for Simeon / Laura to inspect the pipeline on demand.
    """
    acct, err = await require_key(request, "")
    if err:
        return err
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import factory_spawn_agent as F
        res = await F.run_spawn_agent()
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response(res)


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
    # Virtual Firm R0hne (Task 4): read-only pipeline snapshot. Labelled as a
    # VIRTUAL FIRM (agentic, data-processing only) — no real company replaced,
    # no physical product; staged->launched stays behind the Laura gate.
    pipeline = state.get("pipeline", {})
    vf_counts = {s: 0 for s in PIPELINE_STAGES}
    for rec in pipeline.values():
        stg = rec.get("stage")
        if stg in vf_counts:
            vf_counts[stg] += 1
    vf_last = None
    if pipeline:
        loid, lrec = sorted(pipeline.items(),
                            key=lambda kv: kv[1].get("created", 0))[-1]
        vf_last = loid
    virtual_firm = {
        "label": "VIRTUAL FIRM (agentic, data-processing only)",
        "offerings_total": len(pipeline),
        "stage_counts": vf_counts,
        "last_offering_id": vf_last,
    }
    # Inter-center debates (Task 2): count + last resolution summary.
    debates = state.get("debates", {})
    resolved = [d for d in debates.values() if d.get("status") == "done"]
    last_debate = None
    if debates:
        last = sorted(debates.values(),
                      key=lambda d: d.get("created", 0), reverse=True)[0]
        last_debate = {
            "run_id": next((rid for rid, d in debates.items() if d is last),
                           None),
            "center": last.get("center"),
            "adjacent": last.get("adjacent"),
            "status": last.get("status"),
            "posture": (last.get("resolution") or {}).get("posture"),
        }
    leads_by_center = {slug: len(state.get("leads", {}).get(slug, []))
                       for slug in by_center}
    spawn_candidates = {
        slug: {"name": c.get("name"), "mandate": c.get("mandate"),
                  "status": c.get("status"), "laura_pass": c.get("laura_pass"),
                  "uncovered_signals": c.get("uncovered_signals", [])}
        for slug, c in state.get("spawn_candidates", {}).items()
    }
    # Scale-out (Task 5): surface autonomous daughter scale-out counts.
    # daughters_total = standing daughter centers; scaleout_promoted =
    # candidates promoted ("born") this cycle (fallback: daughter count).
    daughter_centers = state.get("daughter_centers", {})
    daughters_total = len(daughter_centers)
    scaleout_promoted = sum(
        1 for c in state.get("spawn_candidates", {}).values()
        if c.get("status") == "born")
    payload = {
        "centers_total": len(by_center),
        "centers_active": len(active),
        "total_sessions": total_sessions,
        "total_revenue_eur": total_rev,
        "total_paid_eur": total_paid,
        "debates_total": len(debates),
        "debates_resolved": len(resolved),
        "last_debate": last_debate,
        "virtual_firm": virtual_firm,
        # Per-center CRM leads (Task 3): populated ONLY from real inbound
        # sessions + debates. Read-only here; no PII (hash only), no scrape.
        "leads_total": sum(len(v) for v in state.get("leads", {}).values()),
        "leads": leads_by_center,
        "stripe_account": "RFI-IRFOS (verified link pool, %d links)" % len(STRIPE_LINKS),
        "cashflow": {s: {"name": b["name"], "sessions": b["sessions"],
                         "revenue_eur": round(b["revenue_eur"], 2),
                         "paid_eur": round(b["paid_eur"], 2),
                         "stripe_link": b["stripe_link"]}
                     for s, b in by_center.items()},
        # FACTORY-FACTORY transparency: what the spawn-agent staged,
        # and whether Laura let it through. No human needed to SEE this.
        "spawn_candidates": spawn_candidates,
        # Scale-out counts (Task 5): standing daughters + promoted this cycle.
        "daughters_total": daughters_total,
        "scaleout_promoted": scaleout_promoted,
    }
    # Machine path: keep the JSON contract 100% intact for API clients.
    if request.headers.get("Accept", "").startswith("application/json"):
        return web.json_response(payload)
    # Human path (Task 5): a calm, static HTML watch-page so Simeon + Laura can
    # WATCH the orchestra — status badges, debates, leads, spawn candidates and
    # the Virtual Firm pipeline — without grepping state.json. Same Palantir
    # palette as index(); no flicker, no auto-refresh loop.
    return web.Response(
        text=_observatory_html(by_center, payload, vf_counts),
        content_type="text/html")


def _observatory_html(by_center, payload, vf_counts):
    """Render the calm observatory watch-page (static, no auto-refresh)."""
    def _badge(status):
        # blue=healthy, orange=degraded/0-status (reuses index accent tokens)
        color = "#4ea1ff" if status == "healthy" else "#f0883e"
        return (f'<span class=badge style="color:{color};'
                f'border-color:{color}">{status}</span>')

    rows = "".join(
        f'<tr><td class=cn>{b["name"]}</td>'
        f'<td>{_badge(get_center_status(slug))}</td>'
        f'<td class=num>{b["sessions"]}</td>'
        f'<td class=num>€{round(b["revenue_eur"], 2)}</td>'
        f'<td class=num>{payload["leads"].get(slug, 0)}</td>'
        f'<td><a href="{b["stripe_link"]}" target=_blank rel=noreferrer>pay link</a></td>'
        f'</tr>'
        for slug, b in by_center.items())

    vf = payload["virtual_firm"]
    stages = "".join(
        f'<span class=pill>{stg}: <b>{vf_counts.get(stg, 0)}</b></span>'
        for stg in PIPELINE_STAGES)

    ld = payload["last_debate"]
    last_debate = (f'last: <b>{ld.get("center")}</b> '
                   f'({ld.get("status")}, {ld.get("posture") or "—"})'
                   if ld else "no debates yet")

    cands = "".join(
        f'<tr><td class=cn>{c.get("name")}</td>'
        f'<td>{c.get("status") or "—"}</td>'
        f'<td>{c.get("source") or "spawn-agent"}</td>'
        f'<td>{"✔ Laura pass" if c.get("laura_pass") else "— gate pending"}</td>'
        f'</tr>'
        for c in payload["spawn_candidates"].values()) \
        or '<tr><td colspan=4 class=empty>no spawn candidates staged</td></tr>'

    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>CoEvolution Observatory</title>
<style>
body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 24px 60px}}
h1{{font-size:30px;font-weight:650;margin:0 0 6px;letter-spacing:-.01em}}
.lede{{color:#8b98a9;font-size:15px;max-width:720px;margin:0 0 26px}}
.lede a{{color:#4ea1ff;text-decoration:none}}
h2{{font-size:15px;font-weight:600;color:#8b98a9;text-transform:uppercase;letter-spacing:.08em;margin:30px 0 12px}}
.stats{{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 8px}}
.stat{{background:#0f141d;border:1px solid #1c2733;border-radius:12px;padding:12px 16px;min-width:120px}}
.stat .k{{color:#5b6675;font-size:11px;text-transform:uppercase;letter-spacing:.06em}}
.stat .v{{color:#e6edf3;font-size:22px;font-weight:650;margin-top:2px}}
table{{width:100%;border-collapse:collapse;background:#0f141d;border:1px solid #1c2733;border-radius:12px;overflow:hidden}}
th,td{{text-align:left;padding:10px 14px;font-size:13px;border-bottom:1px solid #1c2733}}
th{{color:#5b6675;font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}}
tr:last-child td{{border-bottom:none}}
td.cn{{color:#e6edf3;font-weight:550}}
td.num{{text-align:right;color:#c7d2e0;font-variant-numeric:tabular-nums}}
th.num{{text-align:right}}
a{{color:#4ea1ff;text-decoration:none}}
.badge{{display:inline-block;border:1px solid;border-radius:10px;padding:1px 9px;font-size:11px;font-weight:600;letter-spacing:.02em}}
.pill{{display:inline-block;background:#0f141d;border:1px solid #1c2733;border-radius:10px;padding:4px 11px;font-size:12px;color:#c7d2e0;margin:0 6px 6px 0}}
.card{{background:#0f141d;border:1px solid #1c2733;border-radius:12px;padding:16px 18px;font-size:14px;color:#c7d2e0}}
.empty{{color:#5b6675;text-align:center;padding:16px}}
.foot{{color:#5b6675;font-size:12px;margin-top:36px}}
</style></head><body><div class=wrap>
<h1>CoEvolution Observatory</h1>
<p class=lede>Watch the orchestra — center health, debates, leads and the Virtual Firm pipeline, rendered once from live state. No flicker, no polling loop. <a href="/">→ centers</a> · <a href="/network">→ network</a></p>
<div class=stats>
<div class=stat><div class=k>Centers</div><div class=v>{payload["centers_active"]}/{payload["centers_total"]}</div></div>
<div class=stat><div class=k>Sessions</div><div class=v>{payload["total_sessions"]}</div></div>
<div class=stat><div class=k>Revenue</div><div class=v>€{payload["total_revenue_eur"]}</div></div>
<div class=stat><div class=k>Paid</div><div class=v>€{payload["total_paid_eur"]}</div></div>
<div class=stat><div class=k>Leads</div><div class=v>{payload["leads_total"]}</div></div>
</div>

<h2>Centers</h2>
<table><tr><th>Center</th><th>Status</th><th class=num>Sessions</th><th class=num>Revenue</th><th class=num>Leads</th><th>Stripe</th></tr>{rows}</table>

<h2>Virtual Firm</h2>
<div class=card>
<div style="margin-bottom:10px">{vf["label"]} · <b>{vf["offerings_total"]}</b> offerings</div>
{stages}
<div style="margin-top:12px;font-size:13px;color:#8b98a9">
<b>Loop status:</b> {("staged ✔ — spawn candidate queued for Laura gate" if vf.get("stage_transition", {}).get("advanced") else vf.get("launch_gate", ""))}
</div>
</div>

<h2>Debates</h2>
<div class=card>{payload["debates_resolved"]}/{payload["debates_total"]} resolved · {last_debate}</div>

<h2>Spawn candidates</h2>
<table><tr><th>Candidate</th><th>Status</th><th>Source</th><th>Laura gate</th></tr>{cands}</table>

<h2>Scale-out</h2>
<div class=card>
{payload["centers_total"]} standing · <b>{payload.get("daughters_total", 0)}</b> daughters · <b>{payload.get("scaleout_promoted", 0)}</b> promoted last cycle
</div>

<p class=foot>{payload["stripe_account"]} · static render, refresh to update.</p>
</div></body></html>"""


async def network(request):
    return web.json_response({
        "centers": CENTER_SLUGS,
        "edges": {k: v for k, v in CENTER_NETWORK.items()},
        "adjacency_count": {k: len(v) for k, v in CENTER_NETWORK.items()},
    })


async def live_grid(request):
    """GET /api/live-grid — every center's live stats in one batched response,
    polled by the honeycomb landing page (~10s) to patch tile numbers/LED
    colors in place instead of the old render-once-per-load snapshot."""
    return web.json_response({s: _live_stats_for(s) for s in CENTER_SLUGS})


async def center_live(request):
    """GET /api/center/{slug}/live — one center's live stats, polled (~3s) by
    the terrarium panel on that center's detail page."""
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    return web.json_response(_live_stats_for(slug))


def center_page(slug):
    c = _normalize_center(slug, CENTERS[slug])
    stripe_link = link_for_factory(slug, c["price"])
    panel_list = ", ".join(c["panel"])
    disc_list = ", ".join(c["disciplines"])
    adj = CENTER_NETWORK.get(slug, [])
    # 0-status resilience: if the center is degraded/0-status, render an honest
    # "reduced mode" banner and surface its last cached synthesis — NEVER a
    # fabricated fresh verdict.
    center_status = get_center_status(slug)
    reduced_mode_html = ""
    if center_status in ("degraded", "0-status"):
        last = _last_done_job(slug)
        cached = last.get("synthesis") if last else None
        cached_html = ""
        if cached:
            cached_html = (
                '<div class=box style="border-color:#6b4a2c;margin-top:18px">'
                '<div class=small style="text-transform:uppercase;'
                'letter-spacing:.1em;font-size:11px;color:#e8c14a">'
                'last known synthesis (cached)</div>'
                '<pre>{html.escape(json.dumps(cached, indent=2)[:2000])}</pre></div>')
        reduced_mode_html = (
            '<div class=box style="border-color:#6b4a2c;background:#1a1710;'
            'margin-top:18px">'
            '<div style="color:#e8c14a;font-weight:600">Operating in reduced '
            f'mode — engine temporarily unreachable (status: {center_status}).</div>'
            '<div class="small" style="margin-top:6px;color:#c9b48a">Showing the '
            'last known synthesis. No fresh verdict is fabricated while the '
            'center is degraded.</div>'
            '</div>' + cached_html)
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
        f'<div style="margin-top:10px;font-size:13px;color:#ffb38a">'
        f'{c["icp_pain"]}</div>') if c.get("icp_pain") else ""
    initial_stats = _live_stats_for(slug)
    initial_color = STATUS_COLOR.get(initial_stats["status"], "#f0883e")
    # panel roster as avatar chips — plain-English label per role, two-letter
    # initials for the avatar, so the "N experts" number from the old
    # copy becomes a row of actual faces instead of an abstract count.
    def _role_label(role):
        return role.replace('-', ' ').replace('_', ' ').title()
    def _role_initials(role):
        parts = [p for p in role.replace('_', '-').split('-') if p]
        return (parts[0][:1] + (parts[1][:1] if len(parts) > 1 else parts[0][1:2])).upper()
    roster_html = "".join(
        f'<span class=chip><span class=av>{_role_initials(p)}</span>{_role_label(p)}</span>'
        for p in c["panel"])
    page = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{c['name']} — interdisciplinary center</title>
<style>body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{max-width:860px;margin:0 auto;padding:88px 22px 60px}}
h1{{font-size:32px;margin:26px 0 8px;font-weight:700;letter-spacing:-.01em}}
.tagline{{color:#8b98a9;font-size:16px;max-width:620px;line-height:1.55}}
.herorow{{display:flex;align-items:center;gap:14px;margin-top:16px;flex-wrap:wrap}}
.box{{background:#0f141d;border:1px solid #1c2733;border-radius:12px;padding:22px;margin-top:22px}}
button{{background:#14202e;color:#cfe6ff;border:1px solid #2c4258;border-radius:8px;padding:9px 16px;cursor:pointer}}
.buy{{background:#1b3a2a;border-color:#2c6b4a;color:#9ff0c8;text-decoration:none;display:inline-block;padding:11px 20px;border-radius:9px;font-weight:700;font-size:14px}}
.freenote{{color:#5b6675;font-size:13px}}
input,textarea{{width:100%;padding:10px;background:#070b10;border:1px solid #1c2733;border-radius:8px;color:#e6edf3;margin:8px 0;font-family:inherit;box-sizing:border-box}}
pre{{background:#070b10;border:1px solid #1c2733;border-radius:8px;padding:12px;overflow:auto;font-size:12px;max-height:260px}}
.small{{color:#5b6675;font-size:12px}} a{{color:#4ea1ff}}
.out{{background:#070b10;border:1px solid #1c2733;border-radius:8px;padding:12px;margin-top:6px;font-size:13px;min-height:60px;white-space:normal;line-height:1.5}}
button:disabled{{opacity:.6;cursor:default}}
@keyframes tdot{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
@keyframes glow{{0%,100%{{box-shadow:0 0 0 0 {initial_color}33}}50%{{box-shadow:0 0 22px 3px {initial_color}33}}}}
.dash{{border-color:{initial_color}55;animation:glow 3.2s ease-in-out infinite;background:radial-gradient(ellipse at top left,#101a24,#0f141d 65%)}}
.dashtop{{display:flex;align-items:center;gap:10px}}
.dashtop .liveword{{color:#8b98a9;font-size:11px;text-transform:uppercase;letter-spacing:.14em;font-weight:700}}
.dashtop .dashsub{{color:#5b6675;font-size:11px;margin-left:auto}}
.tstats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}}
.tstat{{background:#070b10;border:1px solid #1c2733;border-radius:10px;padding:12px 10px;text-align:center}}
.tstat .k{{color:#5b6675;font-size:10px;text-transform:uppercase;letter-spacing:.06em}}
.tstat .v{{color:#e6edf3;font-size:22px;font-weight:800;margin-top:3px;font-variant-numeric:tabular-nums}}
.tled{{width:9px;height:9px;border-radius:50%;display:inline-block;animation:tdot 1.8s ease-in-out infinite}}
.roster{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}
.chip{{display:flex;align-items:center;gap:6px;background:#0f1a14;border:1px solid #1c3a2a;border-radius:20px;padding:5px 12px 5px 6px;font-size:12px;color:#9fd0ff}}
.chip .av{{width:20px;height:20px;border-radius:50%;background:#1b3a2a;color:#9ff0c8;font-size:9px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.chip.active .av{{background:#36d6a0;color:#04140c;animation:tdot 1.4s ease-in-out infinite}}
.tactivity{{margin-top:14px;font-size:13px;color:#9fd0ff;background:#0f1a14;border:1px solid #1c3a2a;border-radius:8px;padding:10px 12px}}
.asktabs{{display:flex;gap:4px;background:#070b10;border:1px solid #1c2733;border-radius:10px;padding:4px;margin-bottom:2px}}
.asktabs .tab{{flex:1;text-align:center;padding:8px 6px;border-radius:7px;cursor:pointer;color:#8b98a9;font-size:12.5px;font-weight:600;user-select:none}}
.asktabs .tab.on{{background:#14202e;color:#e6edf3}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}
.chips button{{background:#0f141d;border:1px solid #1c2733;border-radius:16px;padding:6px 12px;font-size:12px;color:#9fd0ff;cursor:pointer}}
.chips button:hover{{border-color:#2c4258}}
.meta{{margin-top:30px;padding-top:18px;border-top:1px solid #1c2733;color:#5b6675;font-size:12px;line-height:1.8}}
.meta a{{color:#5b6675;text-decoration:underline}}
@media(max-width:620px){{.tstats{{grid-template-columns:1fr 1fr}}.asktabs{{flex-direction:column}}}}</style></head>
<body>{_nav_html()}
<div class=wrap>
<h1>{c['name']}</h1>
<p class=tagline>{c['mandate']}.</p>
<div class=herorow>
<a class=buy id=buyLink href="{stripe_link}" target="_blank" rel="noopener">Buy sessions — €{c['price']} each →</a>
<span class=freenote>first {c['free']} sessions free · built for {c['icp']}</span>
</div>
{icp_pain_html}
{reduced_mode_html}
<div class="box dash" id=terrarium>
<div class=dashtop>
<span class=tled id=tled style="background:{initial_color}"></span>
<span class=liveword>live right now</span>
<span class=dashsub>updates every few seconds, no refresh needed</span>
</div>
<div class=tstats>
<div class=tstat><div class=k>Status</div><div class=v id=tstatus style="color:{initial_color};font-size:15px">{html.escape(initial_stats['status'])}</div></div>
<div class=tstat><div class=k>Sessions</div><div class=v id=tsessions>{initial_stats['sessions']}</div></div>
<div class=tstat><div class=k>Revenue</div><div class=v id=trevenue>€{initial_stats['revenue_eur']:.0f}</div></div>
<div class=tstat><div class=k>Leads</div><div class=v id=tleads>{initial_stats['leads']}</div></div>
</div>
<div class=roster>{roster_html}</div>
<div class=tactivity id=tactivity>no live session running — try it below and watch this panel light up</div>
</div>

<div class=box>
<div class=asktabs><div class=tab id=t1 class=on>Ask a question</div><div class=tab id=t2>Test a decision</div><div class=tab id=t3>Quick health check</div></div>
<div style="margin-top:14px"><input id=email placeholder="you@company.com — where we send your free answer"></div>
<div id=ctxwrap style="display:none"><input id=ctx placeholder="optional: a bit more context"></div>
<textarea id=doc placeholder="{c['sample_question']}"></textarea>
{('<div class=chips>' + use_cases_html + '</div>') if use_cases_html else ''}
<button id=run style="margin-top:12px;width:100%">ask now — first {c['free']} free</button><span id=runlabel style="display:none">Ask now</span>
<div class=small id=key style="display:none"></div>
<div class=small id=bill style="margin-top:8px"></div>
<div class=small style="margin-top:14px">answer</div>
<div id=out class=out>waiting for your question…</div>
</div>

<div class=meta>
Payments via RFI-IRFOS Stripe · <a href="/privacy">Datenschutz</a> · <a href="/briefing/{slug}">this center's autonomous briefings</a>{(' · related: ' + adj_links) if adj_links else ''}
<br>This is a decision-support tool that surfaces expert perspectives — not a substitute for qualified counsel.
</div>
</div></body>
"""
    js = r"""const $=id=>document.getElementById(id);const slug='__SLUG__';
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
let currentKey='';try{currentKey=localStorage.getItem('ct_'+slug)||'';}catch(e){}
function renderSynth(s,demo){if(!s)return '<span style=color:#8b98a9>no answer came back</span>';
 const posture=s.posture||'unknown';
 const color=posture==='stable'?'#36d6a0':posture==='watch'?'#e8c14a':posture==='elevated'?'#ff8a8a':'#8b98a9';
 let h='<div style="margin:4px 0 10px"><b style="color:'+color+'">'+posture.toUpperCase()+'</b> · '+(s.disciplines_fired||0)+'/'+(s.panel_size||0)+' experts responded';
 if(demo)h+=' · <span style=color:#e8c14a>demo mode (engine not configured)</span>';h+='</div>';
 (s.flags||[]).forEach(f=>{h+='<div style="border-left:3px solid #ff8a8a;padding:6px 10px;margin:6px 0;background:#1a1014"><b>'+esc(f.agent)+'</b> <span style=color:#ff8a8a>['+esc(f.severity)+']</span><br>'+esc(f.description);if(f.evidence)h+='<div style=color:#8b98a9;font-size:12px>evidence: '+esc(f.evidence)+'</div>';h+='</div>';});
 (s.conflicts||[]).forEach(cf=>{h+='<div style="border-left:3px solid #e8c14a;padding:6px 10px;margin:6px 0;background:#1a1710"><b>Open tension</b> - flagged by '+esc((cf.flag_by||[]).join(', '))+' but cleared by '+esc(cf.note_by||'')+'<div style=color:#8b98a9;font-size:12px>evidence: '+esc(cf.evidence||'')+'</div></div>';});
 (s.notes||[]).slice(0,12).forEach(n=>{h+='<div style="border-left:3px solid #2c4258;padding:6px 10px;margin:6px 0;background:#0f141d"><b>'+esc(n.agent)+'</b><br>'+esc(n.description);if(n.evidence)h+='<div style=color:#8b98a9;font-size:12px>evidence: '+esc(n.evidence)+'</div>';h+='</div>';});
 if(!(s.flags||[]).length&&!(s.notes||[]).length&&!(s.conflicts||[]).length)h+='<div style=color:#8b98a9>Nothing flagged.</div>';
 return h;}
function poll(run_id){return new Promise(res=>{const tick=async()=>{try{const r=await fetch('/api/center/result/'+run_id);const j=await r.json();
  if(j.status==='done'){res(j);}else if(j.status==='error'){$('out').innerHTML='<span style=color:#ff8a8a>error: '+esc(j.error||'unknown')+'</span>';res(j);}
  else{$('out').innerHTML='<span style=color:#9fd0ff>The panel is working on it… (usually 30-60s)</span>';setTimeout(tick,3000);}}catch(e){$('out').innerHTML='<span style=color:#ff8a8a>lost connection: '+esc(e)+'</span>';res({});}};tick();});}
async function ensureKey(){
 if(currentKey)return currentKey;
 const email=($('email').value||'').trim();
 if(!email){$('out').innerHTML='<span style=color:#e8c14a>enter your email above first — that\'s where your free answer goes</span>';return null;}
 const r=await fetch('/signup?center='+slug,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
 const j=await r.json();
 if(j.key){currentKey=j.key;try{localStorage.setItem('ct_'+slug,currentKey);}catch(e){}
  $('bill').textContent='first '+j.free_sessions+' sessions free, then EUR '+j.price_eur+'/session';return currentKey;}
 $('out').innerHTML='<span style=color:#e8c14a>'+esc(JSON.stringify(j))+'</span>';return null;}
async function run(){const k=await ensureKey();if(!k)return;
 const tab=window._tab||'t1';const doc=$('doc').value.trim();
 if(tab==='t1'){if(!doc){$('out').innerHTML='<span style=color:#e8c14a>type your question above</span>';return;}
  $('run').disabled=true;$('run').textContent='asking…';$('out').innerHTML='<span style=color:#9fd0ff>Sent to the panel — thinking…</span>';
  const r=await fetch('/api/center?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({text:doc})});const j=await r.json();
  if(j.run_id){const fin=await poll(j.run_id);$('run').disabled=false;$('run').textContent=$('runlabel').textContent;
   if(fin.synthesis){$('out').innerHTML=renderSynth(fin.synthesis,fin.demo);if(fin.billed_eur!==undefined)$('bill').textContent='billed EUR '+fin.billed_eur;}}
  else{$('out').innerHTML='<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';$('run').disabled=false;$('run').textContent=$('runlabel').textContent;}}
 else if(tab==='t2'){if(!doc){$('out').innerHTML='<span style=color:#e8c14a>describe the decision you\'re about to make</span>';return;}
  $('run').disabled=true;$('run').textContent='testing…';$('out').innerHTML='<span style=color:#9fd0ff>Running it past the panel…</span>';
  const r=await fetch('/api/center/scenario?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({action:doc,context:($('ctx').value||'')})});const j=await r.json();
  $('run').disabled=false;$('run').textContent=$('runlabel').textContent;
  $('out').innerHTML=j.synthesis?renderSynth(j.synthesis,j.demo):'<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';}
 else{$('run').disabled=true;$('run').textContent='checking…';$('out').innerHTML='<span style=color:#9fd0ff>Checking current standing…</span>';
  const r=await fetch('/api/center/healthcheck?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({})});const j=await r.json();
  $('run').disabled=false;$('run').textContent=$('runlabel').textContent;
  $('out').innerHTML=j.synthesis?renderSynth(j.synthesis,j.demo):'<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';}}
function showTab(n){['t1','t2','t3'].forEach(t=>$(t).classList.toggle('on',t===n));
 $('ctxwrap').style.display=(n==='t2')?'block':'none';
 $('runlabel').textContent=n==='t1'?'Ask now':(n==='t2'?'Test it':'Check now');
 $('run').textContent=$('runlabel').textContent;
 $('doc').placeholder=n==='t1'?__SAMPLE__:(n==='t2'?'the decision you\'re about to make - e.g. we ship X without a DPIA':'no input needed - just checks current standing');
 window._tab=n;}
['t1','t2','t3'].forEach(t=>$(t).onclick=()=>showTab(t));showTab('t1');
document.querySelectorAll('.uc').forEach(b=>b.onclick=()=>{const q=b.getAttribute('data-q')||b.textContent;$('doc').value=q;showTab('t1');$('doc').scrollIntoView({behavior:'smooth',block:'center'});});
$('run').onclick=run;
// Offer click-through beacon — target=_blank so the current tab never unloads,
// a plain fetch is enough (no keepalive/sendBeacon needed).
$('buyLink').addEventListener('click',function(){fetch('__TRACK_URL__',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({path:location.pathname,site:'__TRACK_SITE__',section:slug+':offer_click'})}).catch(function(){});});
// Terrarium — poll this center's own live numbers + any in-flight panel
// session (someone else's, not just yours) so a visitor watches real
// activity happen, not a static snapshot from page-load.
var COLOR_MAP={healthy:'#36d6a0',degraded:'#f0883e','0-status':'#f85c5c'};
function pollLive(){fetch('/api/center/'+slug+'/live').then(function(r){return r.json()}).then(function(s){
var c=COLOR_MAP[s.status]||'#f0883e';
$('tled').style.background=c;
var st=$('tstatus');st.textContent=s.status;st.style.color=c;
$('tsessions').textContent=s.sessions;
$('trevenue').textContent='€'+Math.round(s.revenue_eur);
$('tleads').textContent=s.leads;
var act=$('tactivity');
document.querySelectorAll('.roster .chip').forEach(function(el){el.classList.toggle('active',!!s.active_job);});
if(s.active_job){act.innerHTML='<b style=color:#36d6a0>● live now</b> - a real question is being answered right now ('+esc(s.active_job.status)+')';}
else{act.textContent='no live session right now - ask a question below and watch this light up';}
}).catch(function(){});}
pollLive();setInterval(pollLive,3000);"""
    js = (js.replace("__SLUG__", slug).replace("__SAMPLE__", json.dumps(c["sample_question"]))
          .replace("__TRACK_URL__", TRACK_URL).replace("__TRACK_SITE__", TRACK_SITE))
    return page + "<script>" + js + "</script>" + _tracker_js(slug) + "</body></html>"



async def center_page_handler(request):
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    return web.Response(text=center_page(slug), content_type="text/html")


async def briefing_page_handler(request):
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    st = load_state()
    briefs = st.get("briefings", {}).get(slug, [])
    c = CENTERS[slug]
    # briefing subscription uses an existing Stripe link (monthly tier),
    # attributed to this center via metadata[center] so the webhook tracks it.
    sub_link = (STRIPE_LINKS["further_dev_monthly"]
                 + "?metadata[center]=" + slug)
    cards = "".join(
        f'<div class=brf>'
        f'<div class=bhead><a class=bh href="{b["link"]}" target=_blank rel=noreferrer>{b["source"]}</a></div>'
        f'<div class=btime>{"DEMO — engine key not configured, not convened" if b.get("demo") else "convened panel briefing"} · {time.strftime("%Y-%m-%d", time.gmtime(b["at"]))}</div>'
        + "".join(
            f'<div class=bitem><span class=blink>↗ {it["link"] and "source" or ""}</span> '
            f'<a href="{it["link"]}" target=_blank rel=noreferrer style="color:#9fd0ff;font-size:13px">{it["source"][:90]}</a>'
            f'<div class=bnote>{it["syn"].get("note","")[:300] or "(no synthesis)"}</div></div>'
            for it in b["items"])
        + '</div>'
        for b in briefs[:8]) or '<div class=bempty>no briefings published yet — the autonomous loop runs on a schedule</div>'
    return web.Response(text=f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{c['name']} — autonomous briefings</title>
<style>
body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{max-width:860px;margin:0 auto;padding:30px 22px 60px}}
nav{{border-bottom:1px solid #1c2733;padding:18px 0;margin-bottom:26px}}
.brand{{font-weight:600}} .ey{{color:#36d6a0;font-size:12px;letter-spacing:.12em;text-transform:uppercase}}
h1{{font-size:28px;margin:0 0 8px;font-weight:650}}
.sub{{color:#8b98a9;font-size:15px;max-width:640px;line-height:1.6}}
.brf{{background:#0f141d;border:1px solid #1c2733;border-radius:12px;padding:18px;margin:14px 0}}
.bhead{{font-weight:600;color:#4ea1ff;font-size:15px;margin-bottom:4px}}
.bhead a{{color:inherit;text-decoration:none}}
.btime{{color:#5b6675;font-size:12px;margin-bottom:10px}}
.bitem{{border-top:1px solid #1c2733;padding:10px 0 4px}}
.blink{{color:#5b6675;font-size:11px}}
.bnote{{color:#c7d2e0;font-size:13px;line-height:1.5;margin-top:4px}}
.bempty{{color:#5b6675;font-size:14px;padding:20px 0}}
a{{color:#4ea1ff}}
</style></head><body><nav><div class=wrap><span class=brand>{c['name']}</span> · <span class=small>a CoEvolution AI center</span></div></nav>
<div class=wrap>
<div class=ey>autonomous briefing feed</div>
<h1>{c['name']} — briefings</h1>
<p class=sub>Standing panel, convened on real regulatory & security signals from public feeds. Published on a schedule, even when no human is online. <a href="/{slug}">→ back to center</a></p>
<div style="margin:18px 0"><a class=buy href="{sub_link}" target="_blank" rel="noopener">Subscribe to this center's autonomous briefing feed →</a>
<div class=small style="margin-top:8px">A standing panel, briefed on real regulatory signals — delivered as it publishes. Secure payment via RFI-IRFOS Stripe.</div></div>
{cards}
</div></body></html>""", content_type="text/html")


async def index(request):
    q = request.query.get("q", "").strip().lower()
    if q:
        matches = {s: c for s, c in CENTERS.items()
                   if q in c["name"].lower() or q in (c.get("mandate") or "").lower()
                   or any(q in d.lower() for d in c.get("disciplines") or [])}
    else:
        matches = dict(CENTERS.items())
    cards = "".join(
        f'<a class=card href="/{s}">'
        f'<div class=ctop><span class=cname>{c["name"]}</span>'
        f'<span class=cmeta>{len(c["panel"])} experts</span></div>'
        f'<div class=cmandate>{c["mandate"]}</div>'
        f'</a>'
        for s, c in matches.items())
    hint = (f'{len(matches)} centers match "{html.escape(q)}"'
            if q else f"{len(matches)} standing interdisciplinary centers")
    return web.Response(text=f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>CoEvolution AI — 50 interdisciplinary centers</title>
<style>
body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 24px 60px}}
h1{{font-size:30px;font-weight:650;margin:0 0 10px;letter-spacing:-.01em}}
.lede{{color:#8b98a9;font-size:15px;max-width:680px;margin:0 0 22px}}
.lede a{{color:#4ea1ff;text-decoration:none}}
.search{{position:relative;margin:0 0 8px}}
.search input{{width:100%;max-width:520px;padding:12px 14px;background:#070b10;border:1px solid #1c2733;border-radius:10px;color:#e6edf3;font-size:14px;font-family:inherit;outline:none;transition:border-color .2s}}
.search input:focus{{border-color:#2c4258}}
.hint{{color:#5b6675;font-size:13px;margin:0 0 22px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.card{{display:block;background:#0f141d;border:1px solid #1c2733;border-radius:12px;padding:16px 16px 14px;text-decoration:none;color:inherit;transition:border-color .2s,transform .2s}}
.card:hover{{border-color:#2c4258;transform:translateY(-2px)}}
.ctop{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:8px}}
.cname{{color:#4ea1ff;font-weight:600;font-size:15px}}
.cmeta{{color:#5b6675;font-size:11px;border:1px solid #1c2733;border-radius:10px;padding:2px 8px;white-space:nowrap}}
.cmandate{{color:#8b98a9;font-size:13px;line-height:1.45}}
@media(max-width:760px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:480px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><div class=wrap>
<h1>50 autonomous interdisciplinary centers</h1>
<p class=lede>Each a distinct, crisis-resistant standing body of experts, convened across the live 292-agent engine. We only track the cashflow. <a href="/observatory">→ Observatory</a> · <a href="/network">→ Center network</a></p>
<form class=search method=get><input name=q placeholder="search by problem, discipline or center (e.g. GDPR, security, hiring)" value="{html.escape(q)}"></form>
<p class=hint>{hint}</p>
<div class=grid>{cards}</div></div></body></html>""", content_type="text/html")


HEX_SIZE = 74         # center-to-vertex, px — the polygon's own geometry
HEX_PITCH = HEX_SIZE  # true edge-to-edge Catan tiling — pitch == size means adjacent hexes share an edge exactly, no gaps/no overlap
HEX_POINTS = " ".join(
    f"{HEX_SIZE * math.cos(math.radians(60 * i - 30)):.1f},"
    f"{HEX_SIZE * math.sin(math.radians(60 * i - 30)):.1f}"
    for i in range(6))


async def firms_grid(request):
    """Public landing page — the 50 centers as a Catan-style honeycomb: each
    a real SVG <polygon> hex (true geometry, clickable, no canvas hit-testing)
    with an HTML <foreignObject> overlay for the name/LED/live numbers, laid
    out via a deterministic axial-coordinate spiral (_hex_spiral) and
    revealed with a staggered per-ring CSS animation on load. Live numbers
    (sessions/revenue/leads/status) are polled from /api/live-grid every
    ~10s and patched into the DOM in place — see the <script> below.
    Merged from the old split index()/firms_grid() duo — single landing
    page at both / and /firms.
    """
    q = (request.query.get("q") or "").strip().lower()

    items = list(CENTERS.items())
    if q:
        items = [(s, c) for s, c in items
                 if q in c["name"].lower() or q in (c.get("mandate") or "").lower()
                 or any(q in d.lower() for d in c.get("disciplines") or [])]

    pad = HEX_SIZE + 20
    if items:
        coords = _hex_spiral(len(items))
        pixels = [_axial_to_pixel(qx, r, HEX_PITCH) for qx, r in coords]
        min_x = min(p[0] for p in pixels) - pad
        max_x = max(p[0] for p in pixels) + pad
        min_y = min(p[1] for p in pixels) - pad
        max_y = max(p[1] for p in pixels) + pad
    else:
        pixels = []
        min_x = min_y = -pad
        max_x = max_y = pad
    vb_w, vb_h = max_x - min_x, max_y - min_y

    def _tile(i, s, c):
        x, y = pixels[i]
        stats = _live_stats_for(s)
        color = STATUS_COLOR.get(stats["status"], "#f0883e")
        delay = min(i * 0.028, 1.1)
        fo_size = HEX_SIZE * 1.35
        # Two nested <g>s on purpose: the OUTER one carries the SVG
        # positioning transform="translate(...)" attribute and is never
        # touched by CSS. The INNER one carries the CSS `hexin` keyframe
        # animation (opacity/scale). A CSS animation that sets `transform`
        # on an element REPLACES that element's transform attribute rather
        # than composing with it — putting position and animation on the
        # same <g> silently collapsed every tile onto the same coordinates.
        return (
            f'<g transform="translate({x - min_x:.1f},{y - min_y:.1f})">'
            f'<g class=hex data-slug="{s}" style="animation-delay:{delay:.3f}s">'
            f'<a href="/{s}">'
            f'<polygon class=hexshape points="{HEX_POINTS}" data-c="{color}" style="stroke:{color}"/>'
            f'<foreignObject x="{-fo_size/2:.1f}" y="{-fo_size/2:.1f}" width="{fo_size:.1f}" height="{fo_size:.1f}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class=hexbody>'
            f'<div class=hexname>{html.escape(c["name"])}</div>'
            f'<div class=hexled style="background:{color}"></div>'
            f'<div class=hexstats>'
            f'<span data-k=sessions>{stats["sessions"]}</span>&nbsp;S · '
            f'<span data-k=revenue>€{stats["revenue_eur"]:.0f}</span> · '
            f'<span data-k=leads>{stats["leads"]}</span>&nbsp;L'
            f'</div></div></foreignObject>'
            f'</a></g></g>')

    tiles_svg = "".join(_tile(i, s, c) for i, (s, c) in enumerate(items))
    empty_note = "" if items else '<div class=empty>keine Zentren passen zur Suche</div>'

    hint = (f'{len(items)} Zentren gefunden für "{html.escape(q)}"'
            if q else f"{len(CENTERS)} autonome Firmen, live aus dem Netzwerk")

    # aggregate business KPI bar — sum the same live-stat functions each tile
    # already calls, once, so a visitor sees "what is this even" answered in
    # numbers before they land on a single hex.
    all_stats = [_live_stats_for(s) for s in CENTER_SLUGS]
    kpi_sessions = sum(s["sessions"] for s in all_stats)
    kpi_revenue = sum(s["revenue_eur"] for s in all_stats)
    kpi_leads = sum(s["leads"] for s in all_stats)
    kpi_healthy = sum(1 for s in all_stats if s["status"] == "healthy")

    body = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>CoEvolution AI — {len(CENTERS)} autonome Firmen, live</title>
<style>
@keyframes hexin{{0%{{opacity:0;transform:scale(.55)}}70%{{opacity:1}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{width:100%;max-width:none;margin:0;padding:88px 40px 60px;box-sizing:border-box}}
.eyebrow{{color:#36d6a0;font-size:12px;letter-spacing:.16em;text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px}}
.eyebrow .dot{{width:7px;height:7px;border-radius:50%;background:#36d6a0;animation:blink 1.6s ease-in-out infinite}}
h1{{font-size:32px;font-weight:700;margin:0 0 10px;letter-spacing:-.01em;
background:linear-gradient(90deg,#e6edf3,#9fd0ff 60%,#36d6a0);-webkit-background-clip:text;background-clip:text;color:transparent}}
.lede{{color:#8b98a9;font-size:15px;max-width:720px;margin:0 0 22px}}
.lede a{{color:#4ea1ff;text-decoration:none}}
.kpibar{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 26px}}
.kpi{{background:#0f141d;border:1px solid #1c2733;border-radius:12px;padding:16px 18px}}
.kpi .k{{color:#5b6675;font-size:11px;text-transform:uppercase;letter-spacing:.08em}}
.kpi .v{{color:#e6edf3;font-size:24px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}}
@media(max-width:820px){{.kpibar{{grid-template-columns:1fr 1fr}}}}
.search{{margin:0 0 8px}}
.search input{{width:100%;max-width:520px;padding:12px 14px;background:#070b10;border:1px solid #1c2733;border-radius:10px;color:#e6edf3;font-size:14px;font-family:inherit;outline:none;transition:border-color .2s}}
.search input:focus{{border-color:#4ea1ff}}
.hint{{color:#5b6675;font-size:13px;margin:0 0 22px}}
.honeycomb{{display:block;width:100%;max-width:1600px;margin:0 auto;height:auto;overflow:visible}}
.hex{{animation:hexin .5s cubic-bezier(.2,.9,.3,1.2) both}}
.hex a{{display:block;text-decoration:none;color:inherit;cursor:pointer}}
.hexshape{{fill:#0f141d;stroke-width:1.5;transition:fill .2s,stroke-width .2s;paint-order:stroke}}
.hex:hover .hexshape{{fill:#141c28;stroke-width:2.5}}
.hexbody{{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:8px;box-sizing:border-box;font-family:-apple-system,Segoe UI,Inter,sans-serif;pointer-events:none}}
.hexname{{color:#e6edf3;font-weight:650;font-size:11px;line-height:1.25;margin-bottom:5px}}
.hexled{{width:7px;height:7px;border-radius:50%;margin-bottom:5px;animation:blink 1.8s ease-in-out infinite}}
.hexstats{{color:#8b98a9;font-size:9.5px;font-variant-numeric:tabular-nums;letter-spacing:.01em}}
.empty{{color:#5b6675;text-align:center;padding:30px}}
.foot{{color:#5b6675;font-size:12px;margin-top:36px}}
@media(max-width:640px){{.hexname{{font-size:9.5px}}.hexstats{{font-size:8.5px}}}}
</style></head><body>{_nav_html('centers')}<div class=wrap>
<div class=eyebrow><span class=dot></span>live · 292-agenten-engine</div>
<h1>CoEvolution AI — {len(CENTERS)} autonome Firmen</h1>
<p class=lede>Jede Wabe ist eine eigenständige, autonome Firma. Klick rein für die volle Ansicht: was sie tut, was sie gerade live macht, und wie du sie buchst.</p>
<div class=kpibar>
<div class=kpi><div class=k>Firmen im Netzwerk</div><div class=v>{len(CENTERS)}</div></div>
<div class=kpi><div class=k>Healthy</div><div class=v style="color:#36d6a0">{kpi_healthy}/{len(CENTERS)}</div></div>
<div class=kpi><div class=k>Sessions gesamt</div><div class=v>{kpi_sessions}</div></div>
<div class=kpi><div class=k>Umsatz gesamt</div><div class=v>€{kpi_revenue:.0f}</div></div>
</div>
<form class=search method=get><input name=q placeholder="Suche nach Problem, Fachgebiet oder Firma (z.B. GDPR, Security, Hiring)" value="{html.escape(q)}"></form>
<p class=hint>{hint}</p>
{empty_note}
<svg class=honeycomb viewBox="0 0 {vb_w:.1f} {vb_h:.1f}" xmlns="http://www.w3.org/2000/svg">{tiles_svg}</svg>
<p class=foot>Live-Waben · Zahlen alle ~10s aktualisiert · Zahlung sicher via RFI-IRFOS Stripe. · <a href="/privacy">Datenschutz</a></p>
</div>
<script>(function(){{
function poll(){{fetch('/api/live-grid').then(function(r){{return r.json()}}).then(function(d){{
document.querySelectorAll('.hex').forEach(function(g){{
var s=d[g.dataset.slug];if(!s)return;
var c=g.querySelector('.hexshape'),color=c.getAttribute('data-c');
var colorMap={{healthy:'#36d6a0',degraded:'#f0883e','0-status':'#f85c5c'}};
var nc=colorMap[s.status]||color;
c.setAttribute('data-c',nc);c.style.stroke=nc;
var led=g.querySelector('.hexled');if(led)led.style.background=nc;
var ss=g.querySelector('[data-k=sessions]');if(ss)ss.textContent=s.sessions;
var rv=g.querySelector('[data-k=revenue]');if(rv)rv.textContent='€'+Math.round(s.revenue_eur);
var ld=g.querySelector('[data-k=leads]');if(ld)ld.textContent=s.leads;
}});}}).catch(function(){{}});}}
setInterval(poll,10000);
}})();</script>
{_tracker_js('search:' + q if q else '')}</body></html>"""
    return web.Response(text=body, content_type="text/html")


async def discover(request):
    """JSON discovery: filter centers by problem/discipline/name. Powers a
    lightweight client-side filter without a full page reload."""
    q = (request.query.get("q") or "").strip().lower()
    out = []
    for s, c in CENTERS.items():
        if not q or q in c["name"].lower() or q in (c.get("mandate") or "").lower() \
                or any(q in d.lower() for d in c.get("disciplines") or []):
            out.append({"slug": s, "name": c["name"], "mandate": c.get("mandate") or "",
                        "disciplines": c.get("disciplines") or [],
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


async def privacy_page(request):
    return web.Response(text=f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Datenschutz — CoEvolution AI</title>
<style>body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.6}}
.wrap{{max-width:760px;margin:0 auto;padding:40px 22px 60px}}
h1{{font-size:26px;font-weight:650;margin:0 0 6px}}
h2{{font-size:16px;font-weight:600;margin:28px 0 8px;color:#e6edf3}}
p{{color:#c7d2e0;font-size:14px}}
code{{background:#0f141d;border:1px solid #1c2733;border-radius:4px;padding:1px 6px;font-size:12.5px}}
pre{{background:#0f141d;border:1px solid #1c2733;border-radius:8px;padding:12px;overflow:auto;font-size:12px;color:#36d6a0;white-space:pre-wrap;word-break:break-all}}
a{{color:#4ea1ff}}
.small{{color:#5b6675;font-size:12px}}</style></head><body><div class=wrap>
<h1>Datenschutz</h1>
<p class=small>a CoEvolution AI center · <a href="/">← back to centers</a></p>
<h2>Cookies</h2>
<p>We don't use cookies. No cookie banner exists because there is nothing to consent to — nothing is written to or read from your device.</p>
<h2>What we track</h2>
<p>Each page you load on this site, and each time you click a center's "Sponsor / buy sessions" button, sends exactly one request to our own self-hosted pixel — the same first-party tracker RFI-IRFOS runs on rfi-irfos.com. The literal request:</p>
<pre>POST {TRACK_URL}
{{"path": "/{{center-slug}}", "referrer": "...", "utm_source": "...", "site": "{TRACK_SITE}", "section": "{{center-slug}} or {{center-slug}}:offer_click"}}</pre>
<p>What lands in our database from that request: the page path, the referring domain normalized into a channel bucket (organic search, direct, referral, linkedin, and so on), the UTM parameters if present, the site tag, and the section tag (which center, and whether it was a pageview or an offer click). That's the full field list: <code>path, source, referrer, utm_source, utm_medium, utm_campaign, site, section</code>.</p>
<p>No cookie is set. No visitor identifier is ever populated by this site's copy of the pixel, so two visits from the same person land as two independent, unlinked rows, never one growing profile. No IP address column exists in that table. The offer-click beacon exists so we can see which centers people are actually interested in enough to click through to Stripe — that's it, we don't track anything past the click; what you do on Stripe's own checkout page is between you and Stripe.</p>
<h2>Legal basis</h2>
<p>Because nothing is stored on or read from your device, the ePrivacy Art. 5(3) cookie-consent trigger does not apply. Because nothing here identifies you individually, this is not personal data processing requiring a GDPR Art. 6 legal basis in the first place — it is anonymous, aggregate usage counting.</p>
<h2>Payments</h2>
<p>Payment processing runs through Stripe, linked from RFI-IRFOS's account. We never see or store card details — that is handled entirely by Stripe.</p>
<h2>Contact</h2>
<p>Questions: <a href="mailto:rfi.irfos@gmail.com">rfi.irfos@gmail.com</a></p>
</div></body></html>""", content_type="text/html")


app = web.Application()
app.router.add_get("/", firms_grid)
app.router.add_get("/firms", firms_grid)
app.router.add_get("/centers", index)
app.router.add_get("/discover", discover)
app.router.add_get("/privacy", privacy_page)
app.router.add_get("/health", health)
app.router.add_get("/observatory", observatory)
app.router.add_get("/network", network)
app.router.add_get("/api/live-grid", live_grid)
app.router.add_get("/api/center/{slug}/live", center_live)
app.router.add_get("/{slug}", center_page_handler)
app.router.add_get("/briefing/{slug}", briefing_page_handler)
app.router.add_post("/signup", signup)
app.router.add_post("/api/center", center_session)
app.router.add_get("/api/center/result/{run_id}", panel_result)
app.router.add_post("/api/center/scenario", scenario_session)
app.router.add_post("/api/center/healthcheck", healthcheck_session)
app.router.add_post("/api/center/resolve", resolve_session)
app.router.add_post("/api/center/spawn", spawn_session)
app.router.add_get("/api/center/team/{team_id}", team_result)
app.router.add_post("/api/center/propose", propose_session)
app.router.add_post("/api/center/debate", debate_session)
app.router.add_get("/api/center/debate/result/{run_id}", debate_result)
app.router.add_post("/evolve", evolve_handler)
app.router.add_post("/evolve/apply", evolve_apply_handler)
app.router.add_post("/stripe/webhook", stripe_webhook)
app.router.add_post("/api/trends/discover", trends_discover_handler)
app.router.add_post("/api/trends/scan", trends_scan_handler)

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
