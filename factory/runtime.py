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

import os, json, secrets, time, asyncio, hmac, hashlib, sys, html, math, random, re
from pathlib import Path
from aiohttp import web, ClientSession, ClientError, ClientTimeout

from catalog import CENTERS_META, CENTER_NETWORK, _REG
from catalog_de import DE_CONTENT
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

# Plain-English display names — the catalog's original squished-CamelCase
# brand names ("FranchiseCompliance Center", "SOXControls Center") tested as
# unreadable and got clipped mid-word in the honeycomb tiles (confirmed live
# 2026-07-18). Overriding `name` here, once, at load time means every
# consumer of CENTERS[slug]["name"] — landing grid, center page, buybar,
# briefings — picks up the clearer name with no per-call-site changes.
# Slugs (used for routing/Stripe metadata) are untouched.
DISPLAY_NAMES = {
    "gdpr-guard": "GDPR & Data Privacy Team",
    "ai-act-guard": "EU AI Act Team",
    "sox-controls": "Financial Controls Team",
    "hipaa-check": "Health Data Privacy Team",
    "contract-risk": "Contract Risk Team",
    "ip-watch": "Patents & IP Team",
    "employment-law": "Employment Law Team",
    "litigation-risk": "Lawsuit Risk Team",
    "license-audit": "Software License Team",
    "tax-exposure": "Tax Exposure Team",
    "vendor-risk": "Vendor Risk Team",
    "cyber-posture": "App Security Team",
    "threat-intel": "Cyber Threat Team",
    "incident-readiness": "Incident Response Team",
    "data-governance": "Data Governance Team",
    "a11y-audit": "Accessibility Team",
    "esg-report": "ESG Reporting Team",
    "carbon-audit": "Carbon Footprint Team",
    "supply-chain-risk": "Supply Chain Risk Team",
    "procure-leak": "Procurement Savings Team",
    "ma-diligence": "M&A Due Diligence Team",
    "board-gov": "Board Governance Team",
    "investor-disclosure": "Investor Disclosure Team",
    "crisis-comms": "Crisis Communications Team",
    "insurance-review": "Insurance Coverage Team",
    "clinical-doc": "Clinical Trial Docs Team",
    "finserv-compliance": "Fintech Compliance Team",
    "saas-security": "Cloud Security Team",
    "payments-compliance": "Payments Compliance Team",
    "crypto-reg": "Crypto Regulation Team",
    "lease-review": "Lease Review Team",
    "franchise-compliance": "Franchise Compliance Team",
    "nonprofit-gov": "Nonprofit Governance Team",
    "export-control": "Export Control Team",
    "product-safety": "Product Safety Team",
    "recall-readiness": "Product Recall Team",
    "pharma-labeling": "Drug Labeling Team",
    "food-safety": "Food Safety Team",
    "energy-compliance": "Energy Compliance Team",
    "telecom-compliance": "Telecom Compliance Team",
    "edu-compliance": "Student Privacy Team",
    "child-safety": "Child Safety Team",
    "content-policy": "Content Moderation Team",
    "bias-audit": "AI Fairness Team",
    "model-card": "AI Documentation Team",
    "breach-readiness": "Data Breach Team",
    "whistleblower": "Whistleblower Policy Team",
    "antitrust": "Antitrust Risk Team",
    "audit-readiness": "Audit Readiness Team",
    "resilience-review": "Business Resilience Team",
}
for _slug, _name in DISPLAY_NAMES.items():
    if _slug in CENTERS:
        CENTERS[_slug]["name"] = _name


# --------------------------------------------------------------------------
# Real per-role bios for the office-floor desks.
#
# Before this, every desk click showed the identical copy-paste line
# "{role} is part of the standing team here — every question passes through
# this perspective" for ALL roles. That told the visitor nothing. We now pull
# a REAL, non-fabricated description from agents_registry/<role>.toml
# (name + lane + the role's actual scope from its system_prompt) and render
# it in plain language. No invented copy.
# --------------------------------------------------------------------------
_REGISTRY_DIR = HERE / "agents_registry"
_ROLE_CACHE = {}
# panel slug -> .toml stem, for the few roles whose panel slug does not match
# a .toml filename 1:1.
_ROLE_ALIASES = {
    "audit-readiness": "quality-audits",
    "incident-readiness": "sre-incident",
}
_NAME_INDEX = {}  # normalized registry name -> slug, built on first miss


def _ensure_name_index():
    """Map (normalized) registry name -> slug, for roles whose panel slug
    does not match a .toml filename 1:1 (e.g. panel 'audit-readiness' lives
    in 'quality-audits.toml'). Built once, lazily."""
    if _NAME_INDEX:
        return
    for fn in _REGISTRY_DIR.glob("*.toml"):
        txt = fn.read_text()
        nm = re.search(r'name\s*=\s*"([^"]+)"', txt)
        if nm:
            key = re.sub(r'\s+', ' ', nm.group(1).strip().lower())
            _NAME_INDEX[key] = fn.stem


def _load_role(slug):
    """Return {name, lane, bio} from agents_registry/<slug>.toml, or None."""
    if slug in _ROLE_CACHE:
        return _ROLE_CACHE[slug]
    fn = _REGISTRY_DIR / f"{slug}.toml"
    if not fn.exists():
        # panel slug may not match the .toml filename; try a name lookup
        # or an explicit alias.
        alt = _ROLE_ALIASES.get(slug)
        if not alt:
            _ensure_name_index()
            key = re.sub(r'[-_]', ' ', slug).strip().lower()
            alt = _NAME_INDEX.get(key)
        if alt:
            fn = _REGISTRY_DIR / f"{alt}.toml"
        else:
            _ROLE_CACHE[slug] = None
            return None
    txt = fn.read_text()
    name = re.search(r'name\s*=\s*"([^"]+)"', txt)
    lane = re.search(r'lane\s*=\s*"([^"]+)"', txt)
    m = re.search(r"system_prompt\s*=\s*'''\n(.*?)'''", txt, re.S)
    sp = m.group(1) if m else ""
    # Grab the role's real scope sentence(s): the "You are ..." intro and the
    # "Your ONLY scope: ..." / "You check ..." detail. Keep it to ~2 sentences.
    picks = []
    for s in re.split(r'(?<=[\.\n])\s*', sp):
        s = re.sub(r'\s+', ' ', s.strip())
        if not s:
            continue
        if (re.match(r'You are (the|a|an) ', s)
                or s.startswith('Your ONLY scope')
                or s.lower().startswith('you check')
                or 'look for' in s.lower()):
            if len(s) > 260:
                s = s[:257] + "…"
            picks.append(s)
        if len(picks) >= 2:
            break
    raw_bio = " ".join(picks)
    rec = {
        "name": name.group(1) if name else slug.replace('-', ' ').title(),
        "lane": lane.group(1) if lane else "",
        "bio": raw_bio,
    }
    _ROLE_CACHE[slug] = rec
    return rec


def role_bio(role):
    """Plain-language, REAL description of a panel role for the desk click.

    Returns HTML-safe text (no markup). Falls back to an honest
    'no detail on file' line rather than inventing a responsibility.
    """
    rec = _load_role(role)
    if not rec:
        return f"{role.replace('-', ' ').title()} — keine Detailbeschreibung hinterlegt."
    name = rec["name"]
    lane = rec["lane"]
    bio = rec["bio"]
    if bio:
        # Strip the "You are the X agent (slug) in the Y lane of a large,
        # publicly-listed enterprise's AI-review ecosystem." framing.
        bio = re.sub(
            r'^You are (?:the |an |a )?.+? agent \([^)]+\) in the .+? lane of '
            r'a large, publicly-listed enterprise\'?s? AI-review ecosystem\.?\s*',
            '', bio).strip()
        # Translate the remaining agent-prompt phrasing into visitor-readable
        # language. These are deterministic restatements of the role's REAL
        # scope from its system_prompt — not invented copy.
        bio = re.sub(
            r'^You are a ([a-z ]+?) \([^)]+\)\.?\s*',
            lambda mo: f"Arbeitet als {mo.group(1)}. ", bio)
        bio = re.sub(
            r'^Your ONLY scope: review the provided text for '
            r'(risks, gaps, missing controls, or required actions) '
            r'that fall squarely within (.+?) responsibilities\.?\s*$',
            lambda mo: "Prüft Risiken, Lücken, fehlende Kontrollen und nötige "
                       f"Maßnahmen, die klar in den Zuständigkeitsbereich "
                       f"„{mo.group(2)}“ fallen.", bio)
        bio = re.sub(
            r'^You are a member of the (.+?)\.?\.?\s*$',
            lambda mo: f"Gehört zur {mo.group(1)}.", bio)
        # "You check X, Y, and Z." -> "Prüft auf X, Y und Z."
        bio = re.sub(
            r"^You check (?:for )?(.+?)\.\s*$",
            lambda mo: "Prüft auf " + mo.group(1).rstrip(".") + ".", bio)
        # "Arbeitet als <englischer beruf>." -> keep, but capitalise cleanly
        # Generic fallback normalisation for any leftover "You are ..." lead.
        bio = re.sub(r'^You are (?:the |an |a )?', '', bio)
        bio = bio[0].upper() + bio[1:] if bio else bio
    if bio:
        return f"{name} ({lane}): {bio}"
    return f"{name} — Teil des {lane}-Bereichs in diesem Team."


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


def _lang_switch_html(lang, url_de, url_en):
    """Proper two-segment DE/EN toggle (matches the pattern on our other
    sites) — NOT a single "click to switch" link, which read as an unlabeled
    mystery button. The current language is a plain highlighted label (not
    a link to itself); the other is a real link."""
    de = '<span class=langseg-on>DE</span>' if lang == "de" else f'<a class=langseg href="{url_de}">DE</a>'
    en = '<span class=langseg-on>EN</span>' if lang == "en" else f'<a class=langseg href="{url_en}">EN</a>'
    return f'<div class=langswitch>{de}{en}</div>'


def _nav_html(active="", brand_extra="", right_html=None):
    """Shared top bar. `brand_extra` renders next to the wordmark (e.g. the
    live badge on the landing page, instead of the old static "by RFI-IRFOS"
    subtitle). `right_html`, if given, REPLACES the default empty right
    side — used by the landing page and center pages to pack in the search
    box / language toggle as one row instead of scattering them across the
    page. No default external link — the rfi-irfos.com link was clutter
    with no reason to be on every single page."""
    right = right_html if right_html is not None else ""
    return f"""<nav class=sitenav><div class=navwrap>
<a class=brand href="/"><span class=grad>CoEvolution AI</span></a>
{brand_extra}
<div class=navlinks>{right}</div>
</div></nav>
<style>
.sitenav{{position:fixed;top:0;left:0;right:0;z-index:100;min-height:64px;background:rgba(10,14,20,.85);
backdrop-filter:blur(16px);border-bottom:1px solid #1c2733}}
.navwrap{{max-width:none;margin:0;min-height:64px;padding:10px 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;text-decoration:none;gap:8px}}
.brand .grad{background:linear-gradient(90deg,#9fd0ff,#36d6a0);-webkit-background-clip:text;background-clip:text;color:transparent;font-weight:800;font-size:16px}}
.navbadge{{color:#36d6a0;font-size:11px;letter-spacing:.1em;text-transform:uppercase;display:flex;align-items:center;gap:6px;
border-left:1px solid #1c2733;padding-left:12px;margin-left:2px}}
.navbadge .dot{{width:6px;height:6px;border-radius:50%;background:#36d6a0;animation:navblink 1.6s ease-in-out infinite}}
@keyframes navblink{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.navlinks{{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-left:auto}}
.navlinks a{{color:#8b98a9;font-size:13px;font-weight:600;text-decoration:none;letter-spacing:.02em}}
.navlinks a:hover{{color:#e6edf3}}
.navsearchwrap{{position:relative;display:flex;align-items:center}}
.navsearchicon{{position:absolute;left:10px;width:14px;height:14px;color:#9fd0ff;pointer-events:none}}
.navsearch{{padding:7px 12px 7px 30px;background:#070b10;border:1.5px solid #2c3744;border-radius:8px;color:#e6edf3;font-size:13px;font-family:inherit;outline:none;width:230px;transition:border-color .2s,width .2s}}
.navsearch:focus{{border-color:#2c4258;width:280px}}
.navbtn{{display:inline-flex;align-items:center;background:#0f141d;border:1px solid #1c2733;border-radius:8px;padding:6px 12px;
color:#9fd0ff!important;font-size:12.5px!important;font-weight:600;text-decoration:none;white-space:nowrap}}
.navbtn:hover{{border-color:#2c4258;color:#e6edf3!important}}
.langswitch{{display:flex;align-items:center;background:#0f141d;border:1px solid #1c2733;border-radius:8px;overflow:hidden;font-size:12.5px;font-weight:700}}
.langswitch a,.langswitch span{{padding:6px 11px;letter-spacing:.03em}}
.langseg{{color:#8b98a9!important;text-decoration:none}}
.langseg:hover{{color:#e6edf3!important;background:#141c28}}
.langseg-on{{color:#04140c;background:#36d6a0}}
@media(max-width:900px){{.navsearch{{width:160px}}.navsearch:focus{{width:190px}}}}
@media(max-width:640px){{.navbadge{{display:none}}.navlinks{{gap:8px}}}}
</style>"""


# --------------------------------------------------------------------------
# Legal footer — CoEvolution Factory takes real payments (Stripe) under the
# same legal entity as rfi-irfos.com, so Austrian ECG (E-Commerce-Gesetz)
# §5 Impressum duties apply here too, not just on the main site. Mirrors
# the identity block from PublicSite.tsx's <footer> (WKO membership, GISA,
# UID, trade-law management, address) rather than inventing a lighter one —
# legal/reference links point at rfi-irfos.com's actual pages since this
# product doesn't have its own Impressum/AGB, it shares RFI-IRFOS's.
# --------------------------------------------------------------------------
def _footer_html():
    return """<footer class=sitefoot><div class=footwrap>
<p class=footdoctrine>Human rights are not subject to negotiation.<br><span>&mdash; RFI-IRFOS &times; Emergent Interaction Lab, core doctrine</span></p>
<div class=footlinks>
<a href="https://rfi-irfos.com/#p/impressum" target=_blank rel=noreferrer>Legal Notice</a>
<a href="https://rfi-irfos.com/#p/datenschutz" target=_blank rel=noreferrer>Privacy Policy</a>
<a href="https://rfi-irfos.com/#p/agb" target=_blank rel=noreferrer>Terms</a>
<a href="/privacy">This site's tracking disclosure</a>
<a href="https://rfi-irfos.com" target=_blank rel=noreferrer>rfi-irfos.com ↗</a>
</div>
<div class=footbadges>
<span class=footbadge>WKO MEMBER · GewO § 32 · Automatic Data Processing</span>
<span class=footbadge>REGULATED NOT-FOR-PROFIT · ZVR 1015608684 · GISA 39261441 · UID ATU83405245</span>
</div>
<p class=footfine>Trade-Law Management: Simeon-Andreas Johann Manfred Kepp &middot; Elisabethinergasse 25/10, 8020 Graz &middot; GLN 9110038490191</p>
<p class=footfine>&copy; 2026 RFI-IRFOS &middot; UID ATU83405245 &middot; Steuernummer 68 696/8736 &middot; Graz, Austria &middot; CoEvolution Factory is an RFI-IRFOS product</p>
</div>
<style>
.sitefoot{border-top:1px solid #1c2733;margin-top:50px;padding:34px 22px 40px;text-align:center}
.footwrap{max-width:900px;margin:0 auto}
.footdoctrine{font-family:monospace;font-size:12px;color:#00f5c4;letter-spacing:.05em;font-weight:600;margin:0 0 22px}
.footdoctrine span{font-size:10px;color:#5b6675;font-weight:400}
.footlinks{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;margin-bottom:18px}
.footlinks a{color:#5b6675;font-size:12px;text-decoration:none}
.footlinks a:hover{color:#9fd0ff}
.footbadges{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:14px}
.footbadge{display:inline-flex;align-items:center;border:1px solid #1c2733;border-radius:4px;padding:5px 12px;background:#0f141d;
font-family:monospace;font-size:10px;color:#5b6675;letter-spacing:.05em}
.footfine{font-family:monospace;font-size:10px;color:#3a4552;letter-spacing:.05em;margin:4px 0}
</style></footer>"""


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


_AXIAL_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _organic_hex_coords(n, seed=0):
    """Deterministic random-growth placement — a branching, irregular blob
    (visually closer to mycelium/organic growth) instead of the perfectly
    symmetric ring-by-ring spiral above. Seeded so the layout is stable
    across reloads exactly like the spiral was; every tile still shares a
    true edge with at least one already-placed neighbor (no floating
    islands, no overlaps)."""
    rng = random.Random(seed)
    placed = [(0, 0)]
    occupied = {(0, 0)}
    frontier = [(0, 0)]  # placed coords that still have empty neighbors
    while len(placed) < n and frontier:
        src = frontier[rng.randrange(len(frontier))]
        empties = [(src[0] + dq, src[1] + dr) for dq, dr in _AXIAL_DIRS
                   if (src[0] + dq, src[1] + dr) not in occupied]
        if not empties:
            frontier.remove(src)
            continue
        nxt = empties[rng.randrange(len(empties))]
        occupied.add(nxt)
        placed.append(nxt)
        frontier.append(nxt)
    return placed[:n]


def _axial_to_pixel(q, r, size):
    x = size * (3 ** 0.5 * q + (3 ** 0.5 / 2) * r)
    y = size * (1.5 * r)
    return x, y


STATUS_COLOR = {"healthy": "#36d6a0", "degraded": "#f0883e", "0-status": "#f85c5c"}
STATUS_LABEL = {
    "healthy": "working normally",
    "degraded": "slow right now",
    "0-status": "offline",
}


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
    d.setdefault("value_prop", c.get("value_prop") or (parent or {}).get("value_prop")
                 or f"A standing panel that watches over: {d['mandate']}.")
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
        # older daughters (created before the plain-English rename pass)
        # were persisted with the raw "{parent} — Daughter {slug}" name —
        # clean it up display-side without touching the persisted state.
        if _parent and _parent in CENTERS and " — Daughter " in CENTERS[_dslug]["name"]:
            CENTERS[_dslug]["name"] = f"{CENTERS[_parent]['name']} — Spin-off"
            CENTERS[_dslug]["mandate"] = (
                f"A focused spin-off team from {CENTERS[_parent]['name']}, "
                f"formed because that team kept hitting the same gap")


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


def _activity_by_day(slug, days=7):
    """Real per-day session counts for the last `days` days (UTC), oldest
    first — built from state["usage"]'s actual "ts" timestamps, not
    fabricated. Powers the BI activity chart on the center detail page."""
    now = int(time.time())
    day = 86400
    buckets = [0] * days
    today0 = (now // day) * day
    for u in state.get("usage", []):
        if u.get("center") != slug:
            continue
        ts = u.get("ts", 0)
        idx = days - 1 - ((today0 - (ts // day) * day) // day)
        if 0 <= idx < days:
            buckets[int(idx)] += 1
    labels = [time.strftime("%a", time.gmtime(today0 - (days - 1 - i) * day))
              for i in range(days)]
    return list(zip(labels, buckets))


def _trust_index_for(slug):
    """A single 0-100 index summarizing a center's current standing, built
    only from real signals already tracked (status FSM + most recent
    synthesized posture) — never a fabricated score. Clearly labeled as
    computed on the page, not presented as ground truth."""
    status = get_center_status(slug)
    base = {"healthy": 92, "degraded": 55, "0-status": 15}.get(status, 92)
    last = _last_done_job(slug)
    posture = (last or {}).get("synthesis", {}).get("posture") if last else None
    adj = {"stable": 6, "watch": -4, "elevated": -18}.get(posture, 0)
    return max(5, min(100, base + adj)), posture


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


# -------------------------------------------------------------------------
# Stripe webhook — REAL, with MANDATORY signature verification.
# STRIPE_WHSEC MUST be set in production (fly secret). If it is missing the
# endpoint refuses to process events (500) instead of silently accepting
# unverified POSTs — an unverified webhook lets anyone fake payments.
# -------------------------------------------------------------------------
async def stripe_webhook(request):
    raw = await request.read()
    if not STRIPE_WHSEC:
        # Prod must set STRIPE_WHSEC. Without it we cannot trust the source.
        return web.json_response(
            {"error": "webhook signing secret not configured"}, status=500)
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


# UI-chrome translations for center_page(). Only the fixed interface copy is
# translated here — per-center descriptive content (value_prop, mandate,
# icp, sample_question, icp_pain, use_cases) lives in catalog.py in English
# only and is NOT machine-translated, so a German visitor still sees English
# center-specific text mixed with German chrome. That's a known limit, not
# an oversight — translating 50 centers' worth of catalog copy is separate
# follow-up work.
CENTER_PAGE_TR = {
    "en": {
        "lead_team": "a standing team of {n} AI experts, working continuously on this problem",
        "workshop_title": "Who's on shift right now",
        "workshop_idle": "nobody is working on anything right now — ask a question below to wake the panel up",
        "workshop_active": "someone is answering a question right now",
        "baynote_empty": "no experts assigned yet — this center is still being set up",
        "status_title": "Status",
        "status_sub": "checked every few seconds, not a one-time snapshot",
        "sessions": "Sessions",
        "leads": "Leads",
        "trust_title": "How much to trust this",
        "trust_word": "trust",
        "kpi_sessions_week": "Sessions this week",
        "kpi_leads": "Leads",
        "kpi_price": "Price per session",
        "kpi_team": "Team size",
        "kpi_related": "Related teams",
        "roster_widget": "Who's on the team",
        "donut_title": "Team composition",
        "trust_sub": "how sure we are the last answer was right — based on whether the center is working normally{posture}",
        "trust_posture": " and how confident the experts were last time ({posture})",
        "chart_title": "Activity — last 7 days",
        "chart_sub": "real session counts, not simulated",
        "chart_empty": "No sessions yet this week — be the first to ask this team something.",
        "roster_title": "Standing panel ({n} experts)",
        "roster_idle": "no live session right now - ask a question below and watch this light up",
        "roster_active": "a real question is being answered right now ({status})",
        "profile_title": "Company profile",
        "revenue_tracked": "Revenue tracked",
        "price_label": "Price",
        "price_value": "€{price}/session, first {free} free",
        "who_for": "Who this is for",
        "disciplines": "Disciplines",
        "network_title": "Network ({n} adjacent)",
        "network_empty": "no adjacent centers yet",
        "ask_title": "Try this company",
        "tab_ask": "Ask a question",
        "tab_test": "Test a decision",
        "tab_check": "Quick health check",
        "email_placeholder": "optional — email to get a copy of your answer",
        "ctx_placeholder": "optional: a bit more context",
        "ask_button": "ask now — first {free} free",
        "ask_label": "Ask now",
        "test_label": "Test it",
        "check_label": "Check now",
        "answer_label": "answer",
        "waiting": "waiting for your question…",
        "privacy": "Privacy notice",
        "briefings_link": "this center's autonomous briefings",
        "disclaimer": "This is a decision-support tool that surfaces expert perspectives - not a substitute for qualified counsel.",
        "buybar_note": "first {free} sessions free · then €{price}/session · built for {icp}",
        "buy_button": "Buy sessions — €{price} each →",
        "status_labels": {"healthy": "working normally", "degraded": "slow right now", "0-status": "offline"},
        "decision_placeholder": "the decision you're about to make - e.g. we ship X without a DPIA",
        "check_placeholder": "no input needed - just checks current standing",
        "enter_email": "enter your email above first — that's where your free answer goes",
        "type_question": "type your question above",
        "describe_decision": "describe the decision you're about to make",
        "asking": "asking…",
        "sent_to_panel": "Sent to the panel — thinking…",
        "testing": "testing…",
        "running_past_panel": "Running it past the panel…",
        "checking": "checking…",
        "checking_standing": "Checking current standing…",
        "lang_toggle": "Deutsch",
        "tab_overview": "Overview",
        "tab_howwork": "How they work",
        "tab_try": "Try it now",
        "desk_hint": "Click a team member",
        "desk_default": "Click someone on the team to see what they're responsible for.",
        "desk_role_line": "{role} is part of the standing team here — every question passes through this perspective too.",
        "hub_label": "Request",
        "hub_idle": "waiting",
        "hub_active": "being handled",
        "buy_explain": "opens the secure Stripe checkout in a new tab — usable results immediately, no account needed",
        "related_label": "Related teams",
        "no_chatbot_banner": "This is not a chatbot. A whole team of experts handles your request — and delivers a finished result.",
        "pipeline_1": "1 · Your question",
        "pipeline_2": "2 · The team advises (multiple experts)",
        "pipeline_3": "3 · Finished result for you",
        "what_you_get_title": "What you get",
        "what_you_get_1": "A finished result, not just \"an answer\"",
        "what_you_get_2": "Worked out jointly by a team of autonomous experts",
        "what_you_get_3": "In a few minutes, no appointment needed",
        "wiz_prompt": "What's it about?",
        "wiz_mode_ask_desc": "Ask your question — the team works out an answer plus a finished result for you.",
        "wiz_mode_test_desc": "Describe a decision — the team checks it from several angles.",
        "wiz_mode_check_desc": "No input — the team just checks the current standing.",
        "buy_button": "Get it done — €{price}",
        "buybar_note": "first {free} times free · then €{price} for a finished result · built for {icp}",
        "wiz_back": "← back",
        "wiz_again": "← ask something else",
    },
    "de": {
        "lead_team": "ein festes Team aus {n} KI-Fachleuten, das sich ständig um dieses Thema kümmert",
        "workshop_title": "Wer gerade im Einsatz ist",
        "workshop_idle": "gerade arbeitet niemand an etwas — stell unten eine Frage und weck das Team auf",
        "workshop_active": "gerade beantwortet jemand eine echte Frage",
        "baynote_empty": "noch keine Fachleute zugeteilt — dieses Center wird gerade aufgebaut",
        "status_title": "Status",
        "status_sub": "wird alle paar Sekunden geprüft, kein einmaliger Schnappschuss",
        "sessions": "Sitzungen",
        "leads": "Anfragen",
        "trust_title": "Wie sehr man dem hier vertrauen kann",
        "trust_word": "Vertrauen",
        "kpi_sessions_week": "Sitzungen diese Woche",
        "kpi_leads": "Anfragen",
        "kpi_price": "Preis pro Sitzung",
        "kpi_team": "Teamgröße",
        "kpi_related": "Verwandte Teams",
        "roster_widget": "Wer im Team ist",
        "trust_sub": "wie sicher wir sind, dass die letzte Antwort gestimmt hat — je nachdem, ob das Center normal läuft{posture}",
        "trust_posture": " und wie sicher sich die Fachleute beim letzten Mal waren ({posture})",
        "chart_title": "Aktivität — letzte 7 Tage",
        "chart_sub": "echte Sitzungszahlen, nichts simuliert",
        "chart_empty": "Diese Woche noch keine Sitzungen — stell als Erster diesem Team eine Frage.",
        "roster_title": "Festes Team ({n} Fachleute)",
        "roster_idle": "gerade läuft keine Sitzung - stell unten eine Frage und schau zu, wie es losgeht",
        "roster_active": "gerade wird eine echte Frage beantwortet ({status})",
        "profile_title": "Firmenprofil",
        "revenue_tracked": "Erfasster Umsatz",
        "price_label": "Preis",
        "price_value": "€{price}/Sitzung, die ersten {free} kostenlos",
        "who_for": "Für wen das gedacht ist",
        "disciplines": "Fachbereiche",
        "network_title": "Netzwerk ({n} benachbart)",
        "network_empty": "noch keine benachbarten Center",
        "ask_title": "Diese Firma ausprobieren",
        "tab_ask": "Frage stellen",
        "tab_test": "Entscheidung testen",
        "tab_check": "Kurzcheck",
        "email_placeholder": "optional — Email für eine Kopie deiner Antwort",
        "ctx_placeholder": "optional: etwas mehr Kontext",
        "ask_button": "jetzt fragen — die ersten {free} kostenlos",
        "ask_label": "Jetzt fragen",
        "test_label": "Testen",
        "check_label": "Jetzt prüfen",
        "answer_label": "Antwort",
        "waiting": "wartet auf deine Frage…",
        "privacy": "Datenschutz",
        "briefings_link": "die automatischen Berichte dieses Centers",
        "disclaimer": "Das hier ist ein Entscheidungs-Hilfsmittel, das die Sicht mehrerer Fachleute zeigt - kein Ersatz für echte Rechtsberatung.",
        "buybar_note": "die ersten {free} Sitzungen kostenlos · danach €{price}/Sitzung · gedacht für {icp}",
        "buy_button": "Buche uns! ▸",
        "status_labels": {"healthy": "läuft normal", "degraded": "gerade langsam", "0-status": "offline"},
        "decision_placeholder": "die Entscheidung, die ansteht - z.B. wir launchen X ohne DPIA",
        "check_placeholder": "keine Eingabe nötig - prüft einfach den aktuellen Stand",
        "enter_email": "trag oben zuerst deine Email ein — dahin geht deine kostenlose Antwort",
        "type_question": "schreib oben deine Frage rein",
        "describe_decision": "beschreib die Entscheidung, die ansteht",
        "asking": "fragt gerade…",
        "sent_to_panel": "An das Team geschickt — überlegt gerade…",
        "testing": "testet gerade…",
        "running_past_panel": "Wird gerade vom Team geprüft…",
        "checking": "prüft gerade…",
        "checking_standing": "Prüft aktuellen Stand…",
        "lang_toggle": "English",
        "tab_overview": "Übersicht",
        "tab_howwork": "Wie sie arbeiten",
        "tab_try": "Jetzt ausprobieren",
        "desk_hint": "Klick auf ein Teammitglied",
        "desk_default": "Klick auf jemanden im Team, um zu sehen, wofür er zuständig ist.",
        "desk_role_line": "{role} ist Teil des festen Teams hier — jede Frage geht auch durch diese Perspektive.",
        "hub_label": "Anfrage",
        "hub_idle": "wartet",
        "hub_active": "wird bearbeitet",
        "buy_explain": "öffnet die sichere Stripe-Kasse in einem neuen Tab — sofort nutzbare Ergebnisse, keine Anmeldung nötig",
        "related_label": "Verwandte Teams",
        "no_chatbot_banner": "Das ist kein Chatbot. Ein ganzes Team aus Experten kümmert sich um dein Anliegen — und liefert dir ein fertiges Ergebnis.",
        "pipeline_1": "1 · Deine Frage",
        "pipeline_2": "2 · Das Team berät (mehrere Experten)",
        "pipeline_3": "3 · Fertiges Ergebnis für dich",
        "what_you_get_title": "Was du bekommst",
        "what_you_get_1": "Ein fertiges Ergebnis, nicht nur „eine Antwort“",
        "what_you_get_2": "Von einem Team autonomer Experten gemeinsam erarbeitet",
        "what_you_get_3": "In wenigen Minuten, ohne Termin",
        "wiz_prompt": "Worum geht's?",
        "wiz_mode_ask_desc": "Stell deine Frage — das Team arbeitet eine Antwort plus ein fertiges Ergebnis für dich aus.",
        "wiz_mode_test_desc": "Beschreib eine Entscheidung — das Team prüft sie aus mehreren Blickwinkeln.",
        "wiz_mode_check_desc": "Keine Eingabe nötig — das Team prüft einfach den aktuellen Stand.",
        "buy_button": "Jetzt erledigen lassen — €{price}",
        "buybar_note": "die ersten {free} Male kostenlos · danach €{price} für ein fertiges Ergebnis · gedacht für {icp}",
        "wiz_back": "← zurück",
        "wiz_again": "← was anderes fragen",
    },
}


def center_card_html(slug, lang="en"):
    """Renders ONLY the inner modal content for a center — no <html>/<nav>/
    <footer> — reused by both the AJAX fragment endpoint (GET
    /api/center/{slug}/card) and the SSR direct-link path (GET /{slug},
    which renders the full landing grid with this fragment pre-opened in
    the modal). Layout follows a smart-home-app reference the user
    supplied: icon-badge header, a big circular "trust" dial as the hero
    (stand-in for the reference's AC-temperature dial), a grid of rounded
    device tiles — one per panel expert, on/off state = idle/answering now
    — instead of the old arch-shaped 'workshop bay' row, and a small
    weekly-activity bar chart with a headline number instead of a bare
    sparkline. All CSS is scoped under #cmbody so it can't leak onto the
    landing page it gets injected into."""
    t = CENTER_PAGE_TR.get(lang, CENTER_PAGE_TR["en"])
    other_lang = "de" if lang == "en" else "en"
    c = _normalize_center(slug, CENTERS[slug])
    if lang == "de" and slug in DE_CONTENT:
        c = dict(c)
        c.update(DE_CONTENT[slug])
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
    initial_status_label = t["status_labels"].get(initial_stats["status"], initial_stats["status"])
    initial_active = bool(initial_stats.get("active_job"))
    workshop_caption = t["workshop_active"] if initial_active else t["workshop_idle"]

    # Tab 2 "office scene" — the interactive whitebox-into-the-company view.
    # Each panel member is a clickable desk (data-role carries the plain
    # label + a real, non-fabricated description: "this person is a
    # standing part of the team, every question passes through them too" —
    # true for all of them, since the whole panel fires on every session).
    # Desks sit in curated top-down positions per headcount — real shared-
    # office layouts (desks against the walls, facing the shared table in
    # the middle), not one geometric ring stretched to fit. A 2-person team
    # reads as two desks facing off; a 4-person team reads as four desks in
    # the corners, like an actual small office. Coordinates are percentages
    # of the (now square) scene box.
    def _office_layout(n):
        if n <= 0:
            return []
        if n == 1:
            return [(50, 18)]
        if n == 2:
            return [(50, 16), (50, 84)]
        if n == 3:
            return [(50, 15), (18, 82), (82, 82)]
        if n == 4:
            return [(18, 18), (82, 18), (18, 82), (82, 82)]
        if n == 5:
            return [(50, 12), (14, 42), (86, 42), (28, 86), (72, 86)]
        top_n, bot_n = (n + 1) // 2, n // 2
        pos = [(50 if top_n == 1 else 14 + 72 * i / (top_n - 1), 16) for i in range(top_n)]
        pos += [(50 if bot_n == 1 else 14 + 72 * i / (bot_n - 1), 84) for i in range(bot_n)]
        return pos[:n]
    desk_class = "desk active" if initial_active else "desk"
    n_desks = len(c["panel"])
    desk_positions = [
        (p, dx, dy) for p, (dx, dy) in zip(c["panel"], _office_layout(n_desks))
    ]
    # Top-down desk furniture (desk surface + monitor + chair), one real SVG
    # per desk instead of a plain rounded card — this is the "actual desk,
    # actual computer, actual floor" ask: a literal architect-software-style
    # top-down furniture silhouette, not an abstract chip. Outlined (not
    # just filled) so it stays visible against the dark floor at any size.
    _desk_furniture_svg = (
        '<svg class=deskshape viewBox="0 0 64 64" fill=none xmlns="http://www.w3.org/2000/svg">'
        '<ellipse cx=32 cy=54 rx=9 ry=7 fill=currentColor fill-opacity=.3 stroke=currentColor stroke-opacity=.6 stroke-width=1.2/>'  # chair
        '<rect x=4 y=18 width=56 height=26 rx=4 fill=currentColor fill-opacity=.16 stroke=currentColor stroke-opacity=.7 stroke-width=1.4/>'  # desk surface
        '<rect x=21 y=9 width=22 height=12 rx=1.5 fill=currentColor fill-opacity=.5 stroke=currentColor stroke-opacity=.8 stroke-width=1.2/>'  # monitor
        '<rect x=29 y=21 width=6 height=2.5 fill=currentColor fill-opacity=.6/>'  # keyboard
        '</svg>')
    desks_html = "".join(
        f'<button type=button class="{desk_class}" data-role="{html.escape(_role_label(p))}" '
        f'data-bio="{html.escape(role_bio(p))}" '
        f'style="left:{dx:.1f}%;top:{dy:.1f}%">'
        f'{_desk_furniture_svg}<span class=deskdot></span>'
        f'<span class=deskicon>{_role_initials(p)}</span>'
        f'<span class=desklabel>{_role_label(p)}</span></button>'
        for p, dx, dy in desk_positions) or (
        f'<div class=dtilenote>{t["baynote_empty"]}</div>')
    _plant_svg = (
        '<svg viewBox="0 0 32 32" fill=none xmlns="http://www.w3.org/2000/svg">'
        '<path d="M16 30 V18" stroke=currentColor stroke-width=2 stroke-linecap=round/>'
        '<ellipse cx=16 cy=12 rx=9 ry=7 fill=currentColor opacity=.5/>'
        '<ellipse cx=9 cy=17 rx=6 ry=5 fill=currentColor opacity=.4/>'
        '<ellipse cx=23 cy=17 rx=6 ry=5 fill=currentColor opacity=.4/>'
        '<path d="M9 30 H23 L21 24 H11 Z" fill=currentColor opacity=.7/>'
        '</svg>')
    line_class = "active" if initial_active else ""
    office_lines_html = "".join(
        f'<line class="{line_class}" x1=50 y1=50 x2={dx:.1f} y2={dy:.1f}></line>'
        for _, dx, dy in desk_positions)
    trust_score, last_posture = _trust_index_for(slug)
    trust_color = "#36d6a0" if trust_score >= 75 else ("#e8c14a" if trust_score >= 45 else "#f85c5c")
    activity = _activity_by_day(slug, 7)
    max_day = max((n for _, n in activity), default=0) or 1
    total_week = sum(n for _, n in activity)
    chart_bars = "".join(
        f'<div class=cbar><div class=cbarfill style="height:{max(6, round(n / max_day * 100)):.0f}%"'
        f' title="{lbl}: {n}"></div><div class=cbarlabel>{lbl}</div></div>'
        for lbl, n in activity)
    # a flat "0 everywhere" bar chart reads as noise, not information — swap
    # the bars for a calm placeholder when there's genuinely no activity yet
    # (never fabricate the shape of data that doesn't exist), but always keep
    # the same header + widget structure as the donut next to it so the two
    # widgets read as a matched pair instead of one looking broken.
    chart_body_html = (
        f'<div class=chartbars>{chart_bars}</div>' if total_week > 0 else
        f'<div class=chartempty>{t["chart_empty"]}</div>')
    icon_key = ICON_BY_SLUG.get(slug, "shield")
    icon_svg = HEX_ICONS.get(icon_key, HEX_ICONS["shield"])
    accent_color = ICON_COLORS.get(icon_key, "#36d6a0")

    def _pill_style(pc, var="--pc"):
        # A hex-alpha suffix glued onto a CSS var() (e.g. `var(--kc)1a`) is
        # not a valid color token — the browser silently drops the whole
        # declaration. Precompute the alpha variants here instead.
        return f"{var}:{pc};{var}bg:{pc}1f;{var}hover:{pc}33"

    # KPI strip — every number here is a real field already computed above
    # (sessions, leads, price, panel size). No fabricated metrics — a
    # BI-dashboard look needs several tiles, but each one has to be honest
    # or it's not worth doing. Trust is NOT in this strip: it gets its own
    # gauge widget below. Related-team count was dropped from here too —
    # it's not a KPI, it's navigation, and lives as its own pill row.
    kpi_tiles = [
        (t["kpi_sessions_week"], f"{total_week}", "#60a5fa", "eye"),
        (t["kpi_leads"], f"{initial_stats['leads']}", "#fbbf24", "speech"),
        (t["kpi_price"], f"€{c['price']:g}", "#4ade80", "coin"),
        (t["kpi_team"], f"{len(c['panel'])}", "#c084fc", "users"),
    ]
    # Each tile is its own fully-colored box now (not a shared strip with a
    # left accent stripe) — background/border alpha variants are computed
    # here in Python and passed as separate vars, same fix as the related-
    # team pills: `var(--kc)1a` glued together is not valid CSS and the
    # browser silently drops it.
    kpi_tiles_html = "".join(
        f'<div class=kpitile style="{_pill_style(color, "--kc")}">'
        f'<svg viewBox="0 0 24 24" fill=none stroke=currentColor '
        f'stroke-width=1.6 stroke-linecap=round stroke-linejoin=round>{HEX_ICONS[icon]}</svg>'
        f'<b>{val}</b><span>{label}</span></div>'
        for label, val, color, icon in kpi_tiles)

    # Trust gauge — the ring is back as its own widget (removed in the last
    # pass, which left trust as one bare number in the strip). Animated
    # fill from 0 to the real score on open.
    gauge_r = 52
    gauge_circ = 2 * math.pi * gauge_r
    gauge_offset = gauge_circ * (1 - trust_score / 100)

    # Related-team pills get their own accent color (borrowed from that
    # team's category — same palette used for hex icons/company logos) so
    # they read as distinct destinations instead of a uniform gray list.
    adj_links = "".join(
        f'<a class=netchip href="/{a}" style="{_pill_style(ICON_COLORS.get(ICON_BY_SLUG.get(a, "shield"), "#36d6a0"))}">{CENTERS[a]["name"]}</a>'
        for a in adj[:3])
    # Real, engine-generated sample product (never a placeholder). Shown in the
    # overview tab so a visitor sees the firm is already useful — not "0 sessions".
    try:
        from firm_foundation import load_sample_product
        _prod = load_sample_product(slug)
    except Exception:
        _prod = None
    if _prod:
        _body = (_prod.get("body") or _prod.get("summary") or "").strip()
        _title = _prod.get("title", t["what_you_get_title"])
        _days = max(0, int((time.time() - _prod.get("generated_at", 0)) / 86400))
        sample_html = (
            f'<div class=sampleproduct><div class=sphead>{html.escape(_title)}'
            f'<span class=spmeta>vom Team erstellt · {_days}d alt</span></div>'
            f'<div class=spbody>{html.escape(_body[:700])}</div></div>')
    else:
        sample_html = ""
    page = f"""<style>
#cmbody{{font-family:-apple-system,Segoe UI,Inter,sans-serif;color:#e6edf3;line-height:1.5}}
#cmbody a{{color:#4ea1ff}}
#cmbody button{{background:#14202e;color:#cfe6ff;border:1px solid #2c4258;border-radius:8px;padding:9px 16px;cursor:pointer;font-family:inherit}}
#cmbody button:disabled{{opacity:.6;cursor:default}}
#cmbody input,#cmbody textarea{{width:100%;padding:10px;background:#070b10;border:1px solid #1c2733;border-radius:8px;color:#e6edf3;margin:8px 0;font-family:inherit;box-sizing:border-box}}
#cmbody .cmsmall{{color:#5b6675;font-size:12px}}
#cmbody .out{{background:#070b10;border:1px solid #1c2733;border-radius:8px;padding:12px;margin-top:6px;font-size:13px;min-height:160px;white-space:normal;line-height:1.5}}
#cmbody .feedback{{display:flex;align-items:center;gap:8px;margin-top:12px;flex-wrap:wrap}}
#cmbody .feedback[hidden]{{display:none}}
#cmbody .fblabel{{color:#8b98a9;font-size:12px}}
#cmbody .fbbtn{{background:#14202e;border:1px solid #2c4258;border-radius:8px;font-size:16px;padding:5px 10px;cursor:pointer}}
#cmbody .fbbtn:hover{{border-color:#36d6a0}}
#cmbody .fbtext{{flex:1;min-width:120px;background:#070b10;border:1px solid #1c2733;border-radius:8px;color:#e6edf3;padding:6px 10px;font-family:inherit;font-size:12px}}
#cmbody .fbthanks{{color:#36d6a0;font-size:12px;font-weight:600}}
@keyframes tdot{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
@keyframes cmbob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-3px)}}}}
@keyframes cmglow{{0%,100%{{box-shadow:0 0 0 0 {initial_color}33}}50%{{box-shadow:0 0 22px 3px {initial_color}33}}}}
@keyframes cmpop{{from{{opacity:0;transform:scale(.85)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes gaugefill{{from{{stroke-dashoffset:{gauge_circ:.1f}}}to{{stroke-dashoffset:{gauge_offset:.1f}}}}}
#cmbody #run.idle{{animation:cmglow 2.6s ease-in-out infinite}}
#cmbody .zone{{background:#0f141d;border:1px solid #1c2733;border-radius:16px;padding:20px 22px;margin-top:14px}}
#cmbody .zone>h3{{margin:0 0 14px;font-size:11px;color:#8b98a9;text-transform:uppercase;letter-spacing:.1em;font-weight:700}}
#cmbody .cmhero{{display:flex;align-items:center;gap:16px;background:linear-gradient(135deg,{accent_color}1f,#0f141d 60%);border:1px solid {accent_color}44;border-radius:16px;padding:20px 22px}}
#cmbody .cmicon{{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:{accent_color}26;color:{accent_color}}}
#cmbody .cmicon svg{{width:28px;height:28px}}
#cmbody .cmheadtext{{flex:1;min-width:0}}
#cmbody .cmheadtext h2{{margin:0 0 4px;font-size:24px;font-weight:800;letter-spacing:-.01em}}
#cmbody .cmvalue{{font-size:14.5px;font-weight:500;color:#c7d2e0;line-height:1.5;margin:0;max-width:640px}}
#cmbody .cmstatus{{align-self:flex-start;display:flex;align-items:center;gap:6px;background:#0a0e14cc;border:1px solid #1c2733;border-radius:20px;padding:6px 12px;font-size:12px;color:#c7d2e0;white-space:nowrap;cursor:help}}
#cmbody .tled{{width:9px;height:9px;border-radius:50%;display:inline-block;animation:tdot 1.8s ease-in-out infinite}}
#cmbody .kpirow{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
#cmbody .kpitile{{background:var(--kcbg);border:1px solid var(--kc);border-radius:14px;padding:14px 16px;display:flex;flex-direction:column;gap:6px;animation:cmpop .4s ease-out both}}
#cmbody .kpitile svg{{width:15px;height:15px;color:var(--kc)}}
#cmbody .kpitile b{{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.1}}
#cmbody .kpitile span{{font-size:10.5px;color:#8b98a9;line-height:1.3}}
#cmbody .widgetgrid{{display:grid;grid-template-columns:1fr 1.6fr;gap:14px;margin-top:14px}}
#cmbody .widget{{background:#0f141d;border:1px solid #1c2733;border-radius:16px;padding:18px 20px;min-width:0;display:flex;flex-direction:column}}
#cmbody .widget>h3{{margin:0 0 4px;font-size:11px;color:#8b98a9;text-transform:uppercase;letter-spacing:.1em;font-weight:700;display:flex;justify-content:space-between;align-items:baseline}}
#cmbody .widget>h3 b{{font-size:15px;color:#e6edf3}}
#cmbody .widgetbody{{flex:1;display:flex;align-items:center;justify-content:center;gap:16px;padding-top:10px}}
#cmbody .widgetsub{{font-size:11px;color:#5b6675;line-height:1.45;margin-top:10px}}
#cmbody .gaugewrap{{position:relative;width:116px;height:116px;flex-shrink:0}}
#cmbody .gauge{{transform:rotate(-90deg)}}
#cmbody .gaugetrack{{fill:none;stroke:#1c2733;stroke-width:9}}
#cmbody .gaugeval{{fill:none;stroke:{trust_color};stroke-width:9;stroke-linecap:round;stroke-dashoffset:{gauge_circ:.1f};animation:gaugefill 1.2s ease-out .15s forwards}}
#cmbody .gaugenum{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}}
#cmbody .gaugenum b{{font-size:30px;font-weight:800;line-height:1}}
#cmbody .gaugenum span{{font-size:10px;color:#5b6675;margin-top:3px}}
#cmbody .chartbars{{display:flex;align-items:flex-end;gap:8px;height:84px;width:100%}}
#cmbody .cbar{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}}
#cmbody .cbarfill{{width:100%;border-radius:4px 4px 0 0;min-height:3px;background:linear-gradient(to top,{accent_color}55,{accent_color})}}
#cmbody .cbarlabel{{font-size:9px;color:#5b6675;margin-top:5px;text-transform:uppercase}}
#cmbody .chartempty{{color:#5b6675;font-size:12.5px;font-style:italic;text-align:center;line-height:1.5;padding:12px}}
#cmbody .cmtabs{{display:flex;gap:6px;margin-top:16px;background:#070b10;border:1px solid #1c2733;border-radius:12px;padding:5px}}
#cmbody .cmtab{{flex:1;text-align:center;padding:10px 8px;border-radius:8px;cursor:pointer;color:#8b98a9;font-size:13px;font-weight:700;user-select:none;transition:background .15s,color .15s}}
#cmbody .cmtab.on{{background:{accent_color}22;color:#e6edf3}}
#cmbody .cmtab:hover:not(.on){{color:#c7d2e0}}
#cmbody .cmpane{{display:none;padding-top:6px}}
#cmbody .cmpane.on{{display:block}}
/* Office scene — a true top-down floor plan (RoomSketcher-style reference):
   desks are absolutely positioned by real angle/radius math (Python-computed
   percentages, not CSS layout), radiating around a central meeting table,
   with an SVG floor-plan grid underneath standing in for a room outline. */
#cmbody .officecanvas{{display:block;width:min(100%,520px);aspect-ratio:1/1;margin:0 auto;border-radius:12px;overflow:hidden;background:#d5d0c4;box-shadow:0 10px 30px rgba(0,0,0,.4)}}
#cmbody .deskinfo{{text-align:center;color:#9aa7b5;font-size:12.5px;margin:10px 0 2px}}
#cmbody .plant svg{{width:100%;height:100%}}
#cmbody .plant.p1{{top:14px;left:14px}}
#cmbody .plant.p2{{bottom:14px;right:14px}}
#cmbody .officelines{{position:absolute;inset:0;width:100%;height:100%;z-index:1}}
#cmbody .officelines line{{stroke:{accent_color}55;stroke-width:.6;stroke-dasharray:2 1.6}}
#cmbody .officelines line.active{{stroke:#36d6a0;stroke-width:.9;animation:linerun .6s linear infinite}}
#cmbody .desk{{all:unset;box-sizing:border-box;position:absolute;transform:translate(-50%,-50%);cursor:pointer;display:flex;flex-direction:column;align-items:center;text-align:center;width:84px;transition:transform .15s;z-index:2}}
#cmbody .desk:hover{{transform:translate(-50%,-50%) translateY(-3px)}}
#cmbody .desk:focus-visible{{outline:2px solid {accent_color};outline-offset:2px;border-radius:8px}}
#cmbody .deskshape{{position:absolute;top:-8px;left:50%;transform:translateX(-50%);width:84px;height:84px;color:{accent_color};pointer-events:none}}
#cmbody .desk.selected .deskshape{{color:#36d6a0}}
#cmbody .deskdot{{position:absolute;top:2px;right:6px;width:7px;height:7px;border-radius:50%;background:#5b6675;opacity:.6;z-index:3}}
#cmbody .desk.active .deskdot{{background:#36d6a0;opacity:1;animation:tdot 1.4s ease-in-out infinite}}
#cmbody .deskicon{{position:relative;z-index:3;margin-top:6px;width:30px;height:30px;border-radius:50%;background:#0f1a14;border:1.5px solid {accent_color};color:{accent_color};font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center;animation:cmbob 3.6s ease-in-out infinite;box-shadow:0 2px 6px rgba(0,0,0,.5)}}
#cmbody .desk.active .deskicon{{background:#36d6a0;border-color:#36d6a0;color:#04140c;animation:cmbob 1s ease-in-out infinite}}
#cmbody .desklabel{{position:relative;z-index:3;margin-top:34px;font-size:10px;color:#e6edf3;line-height:1.2;text-shadow:0 1px 3px #000;background:#0a0e14cc;border-radius:6px;padding:2px 6px}}
#cmbody .hub{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:104px;background:#0a0e14;border:1.5px solid {accent_color}70;border-radius:12px;padding:10px;text-align:center;z-index:2}}
#cmbody .hub.active{{border-color:#36d6a0}}
@keyframes linerun{{to{{background-position:0 13px}}}}
#cmbody .hub{{width:120px;margin:0 auto;background:#0a0e14;border:1.5px solid {accent_color}60;border-radius:14px;padding:12px;text-align:center}}
#cmbody .hub.active{{border-color:#36d6a0}}
#cmbody .hubdot{{width:10px;height:10px;border-radius:50%;background:#5b6675;margin:0 auto 6px;opacity:.5}}
#cmbody .hub.active .hubdot{{background:#36d6a0;opacity:1;animation:tdot 1s ease-in-out infinite}}
#cmbody .hub b{{display:block;font-size:12px}}
#cmbody .hub span{{font-size:10px;color:#5b6675;text-transform:uppercase;letter-spacing:.04em}}
#cmbody .dtilenote{{color:#5b6675;font-size:13px;padding:16px;text-align:center}}
#cmbody .deskinfo{{margin-top:14px;background:#0f141d;border:1px solid #1c2733;border-radius:10px;padding:12px 16px;font-size:13px;color:#c7d2e0;min-height:20px}}
#cmbody .workpopup{{position:absolute;left:50%;top:14px;transform:translateX(-50%);max-width:320px;background:#0f141d;border:1px solid #2c4258;border-radius:12px;padding:12px 14px;box-shadow:0 12px 30px rgba(0,0,0,.55);font-size:13px;color:#e6edf3;z-index:6;animation:cmpop .18s ease;line-height:1.45}}
#cmbody .workpopup b{{color:#36d6a0}}
#cmbody .workpopup[hidden]{{display:none}}
#cmbody .deskinfo b{{color:#9fd0ff}}
#cmbody .cmask{{margin-top:0;background:none;border:none;padding:0;max-width:520px;margin-left:auto;margin-right:auto}}
#cmbody .nochat{{background:#36d6a01a;border:1px solid #36d6a044;border-radius:12px;padding:10px 14px;color:#a7f3d0;font-size:13px;margin-bottom:14px;line-height:1.45}}
#cmbody .pipeline{{display:flex;gap:8px;margin-bottom:16px}}
#cmbody .pstep{{flex:1;background:#0f141d;border:1px solid #1c2733;border-radius:10px;padding:10px;font-size:12px;color:#c7d2e0;display:flex;align-items:center;gap:8px;line-height:1.3}}
#cmbody .pstep span{{display:inline-flex;width:22px;height:22px;border-radius:50%;background:#36d6a0;color:#04140d;font-weight:800;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}}
#cmbody .cmask h3{{display:none}}
#cmbody .wizsteps,.wizsteps{{display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:18px}}
#cmbody .wizdot,.wizdot{{width:24px;height:24px;border-radius:50%;background:#0f141d;border:1px solid #1c2733;color:#5b6675;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}}
#cmbody .wizdot.on,.wizdot.on{{background:{accent_color}22;border-color:{accent_color};color:{accent_color}}}
#cmbody .wizstep{{display:none}}
#cmbody .wizstep.on{{display:block;animation:cmpop .3s ease-out both}}
#cmbody .wizprompt{{text-align:center;font-size:16px;font-weight:700;margin-bottom:16px}}
#cmbody .wizmodes{{display:flex;flex-direction:column;gap:10px}}
#cmbody .wizmode{{all:unset;box-sizing:border-box;cursor:pointer;background:#0f141d;border:1.5px solid #1c2733;border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:3px;transition:border-color .15s,background .15s}}
#cmbody .wizmode:hover{{border-color:{accent_color}80}}
#cmbody .wizmode.on{{border-color:{accent_color};background:{accent_color}14}}
#cmbody .wizmode b{{font-size:14px;color:#e6edf3}}
#cmbody .wizmode span{{font-size:12px;color:#8b98a9}}
#cmbody .wizback{{all:unset;cursor:pointer;color:#8b98a9;font-size:12.5px;font-weight:600;margin-bottom:12px;display:inline-block}}
#cmbody .wizback:hover{{color:#e6edf3}}
#cmbody .chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}
#cmbody .chips button{{background:#0f141d;border:1px solid #1c2733;border-radius:16px;padding:6px 12px;font-size:12px;color:#9fd0ff;cursor:pointer}}
#cmbody .chips button:hover{{border-color:#2c4258}}
#cmbody .related{{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:18px;padding-top:14px;border-top:1px solid #1c2733}}
#cmbody .relabel{{color:#5b6675;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-right:4px}}
#cmbody .whatyouget{{margin-top:18px;padding:16px 18px;background:#0f141d;border:1px solid #1c2733;border-radius:14px}}
#cmbody .whatyouget h3{{margin:0 0 10px;font-size:11px;color:#8b98a9;text-transform:uppercase;letter-spacing:.1em;font-weight:700}}
#cmbody .whatyouget ul{{margin:0;padding-left:18px;color:#c7d2e0;font-size:13px;line-height:1.7}}
#cmbody .whatyouget li{{margin:0}}
#cmbody .sampleproduct{{margin-top:16px;padding:16px 18px;background:#0b1411;border:1px solid #1f4d3a;border-radius:14px}}
#cmbody .sampleproduct .sphead{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:8px}}
#cmbody .sampleproduct .sphead{{color:#36d6a0;font-weight:700;font-size:14px}}
#cmbody .sampleproduct .spmeta{{color:#5b6675;font-size:11px;font-weight:400;white-space:nowrap}}
#cmbody .sampleproduct .spbody{{color:#c7d2e0;font-size:13px;line-height:1.6;white-space:pre-wrap}}
#cmbody a.netchip{{display:inline-block;background:var(--pcbg);border:1px solid var(--pc);border-radius:14px;padding:5px 12px;margin:0;font-size:11.5px;font-weight:600;color:var(--pc)!important;text-decoration:none!important}}
#cmbody a.netchip:hover{{background:var(--pchover)}}
#cmbody .cmbuy{{position:absolute;right:18px;bottom:14px;margin:0;background:transparent;padding:0;display:flex;align-items:center;justify-content:flex-end;z-index:5}}
#cmbody .buy{{display:inline-flex;align-items:center;gap:7px;background:linear-gradient(135deg,#36d6a0,#22c55e);color:#04140d;font-weight:800;font-size:13px;padding:9px 15px;border-radius:12px;text-decoration:none!important;box-shadow:0 6px 18px rgba(54,214,160,.35);transition:transform .15s ease,box-shadow .15s ease}}
#cmbody .buy:hover{{transform:translateY(-1px);box-shadow:0 10px 24px rgba(54,214,160,.45)}}
#cmbody .buy svg{{width:16px;height:16px;flex-shrink:0}}
#cmbody .buyprice{{color:#36d6a0;font-weight:700;font-size:12px;background:#0f1b16;padding:5px 9px;border-radius:9px}}
@media(max-width:900px){{#cmbody .widgetgrid{{grid-template-columns:1fr}}}}
@media(max-width:640px){{#cmbody .cmtabs{{overflow-x:auto}}#cmbody .cmtab{{font-size:12px;padding:9px 6px}}
#cmbody .kpirow{{grid-template-columns:repeat(2,1fr)}}
#cmbody .cmhero{{flex-direction:column;align-items:flex-start}}#cmbody .cmstatus{{align-self:flex-start}}
#cmbody .officefloor{{width:100%}}#cmbody .desk{{width:60px;padding:6px 4px 4px}}#cmbody .deskicon{{width:24px;height:24px;font-size:10px}}#cmbody .desklabel{{font-size:8.5px}}#cmbody .hub{{width:84px;padding:8px}}
#cmbody .cmbuy{{flex-direction:column;align-items:stretch;text-align:center}}#cmbody .buy{{text-align:center}}}}
</style>
<div class=cmhero>
<span class=cmicon><svg viewBox="0 0 24 24" fill=currentColor stroke=currentColor stroke-width=1.6 stroke-linecap=round stroke-linejoin=round>{icon_svg}</svg></span>
<div class=cmheadtext><h2>{c['name']}</h2><div class=cmvalue>{c['value_prop']}</div></div>
<span class=cmstatus title="{t['status_sub']}"><span class=tled id=tled style="background:{initial_color}"></span><span id=tstatus>{html.escape(initial_status_label)}</span></span>
</div>
{reduced_mode_html}

<div class=cmtabs>
<div class="cmtab on" id=ct1>{t['tab_overview']}</div>
<div class=cmtab id=ct2>{t['tab_howwork']}</div>
<div class=cmtab id=ct3>{t['tab_try']}</div>
</div>

<div class="cmpane on" id=cp1>
<div class=kpirow style="margin-top:14px">{kpi_tiles_html}</div>
<div class=widgetgrid>
<div class=widget>
<h3>{t['trust_word'].capitalize()}</h3>
<div class=widgetbody>
<div class=gaugewrap>
<svg width=116 height=116 class=gauge viewBox="0 0 116 116">
<circle class=gaugetrack cx=58 cy=58 r={gauge_r}></circle>
<circle class=gaugeval cx=58 cy=58 r={gauge_r} stroke-dasharray="{gauge_circ:.1f}"></circle>
</svg>
<div class=gaugenum><b>{trust_score}</b><span>/ 100</span></div>
</div>
</div>
<div class=widgetsub>{t['trust_sub'].format(posture=t['trust_posture'].format(posture=last_posture) if last_posture else '')}</div>
</div>
<div class=widget>
<h3>{t['chart_title']}<b>{total_week} {t['sessions']}</b></h3>
<div class=widgetbody>{chart_body_html}</div>
<div class=widgetsub>{t['chart_sub']}</div>
</div>
</div>
{(f'<div class=related><span class=relabel>{t["related_label"]}</span>{adj_links}</div>') if adj_links else ''}
{sample_html}
<div class=whatyouget>
  <h3>{t['what_you_get_title']}</h3>
  <ul><li>{t['what_you_get_1']}</li><li>{t['what_you_get_2']}</li><li>{t['what_you_get_3']}</li></ul>
</div>
</div>
<div class=zone style="margin-top:14px;position:relative">
<canvas class=officecanvas id=workshop width=1200 height=800></canvas>
<div class=workpopup id=workpopup hidden></div>
<div class=deskinfo id=deskinfo>{t['desk_default']}</div>
<div class=cmcaption id=wcaption>{workshop_caption}</div>
</div>
</div>

<div class="cmpane" id=cp3>
<div class=cmask>
<div class=nochat>{t['no_chatbot_banner']}</div>
<div class=pipeline>
  <div class=pstep><span>1</span> {t['pipeline_1']}</div>
  <div class=pstep><span>2</span> {t['pipeline_2']}</div>
  <div class=pstep><span>3</span> {t['pipeline_3']}</div>
</div>
<div class=wizsteps><span class="wizdot on" id=wd1>1</span><span class=wizdot id=wd2>2</span><span class=wizdot id=wd3>3</span></div>

<div class="wizstep on" id=ws1>
<div class=wizprompt>{t['wiz_prompt']}</div>
<div class=wizmodes>
<button type=button class="tab wizmode on" id=t1><b>{t['tab_ask']}</b><span>{t['wiz_mode_ask_desc']}</span></button>
<button type=button class="tab wizmode" id=t2><b>{t['tab_test']}</b><span>{t['wiz_mode_test_desc']}</span></button>
<button type=button class="tab wizmode" id=t3><b>{t['tab_check']}</b><span>{t['wiz_mode_check_desc']}</span></button>
</div>
</div>

<div class=wizstep id=ws2>
<button type=button class=wizback id=wback1>{t['wiz_back']}</button>
<textarea id=doc placeholder="{c['sample_question']}"></textarea>
{('<div class=chips>' + use_cases_html + '</div>') if use_cases_html else ''}
<div id=ctxwrap style="display:none"><input id=ctx placeholder="{t['ctx_placeholder']}"></div>
<input id=email placeholder="{t['email_placeholder']}">
<button id=run class="{'' if initial_active else 'idle'}" style="margin-top:6px;width:100%">{t['ask_button'].format(free=c['free'])}</button><span id=runlabel style="display:none">{t['ask_label']}</span>
<div class=cmsmall id=bill style="margin-top:8px"></div>
</div>

<div class=wizstep id=ws3>
<button type=button class=wizback id=wback2>{t['wiz_again']}</button>
<div class=cmsmall style="margin:10px 0 6px">{t['answer_label']}</div>
<div id=out class=out>{t['waiting']}</div>
<div class=feedback id=feedback hidden>
  <span class=fblabel>War des hilfreich?</span>
  <button type=button id=fbup class=fbbtn>👍</button>
  <button type=button id=fbdown class=fbbtn>👎</button>
  <input id=fbtext class=fbtext placeholder="Was hat gefehlt?" />
</div>
</div>
</div>
</div>

<div class=cmbuy>
<a class=buy id=buyLink href="{stripe_link}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><circle cx=9 cy=21 r=1/><circle cx=19 cy=21 r=1/><path d="M2.5 3 H5 L7 15 H19 L21.5 7 H6"/></svg>{t['buy_button']}</a><span class=buyprice>€{c['price']:g}</span>
</div>"""
    js = r"""(function(){
if(window.__cmPollId){clearInterval(window.__cmPollId);window.__cmPollId=null;}
const $=id=>document.getElementById(id);const slug='__SLUG__';
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
 const typed=($('email').value||'').trim();
 const email=(typed&&typed.indexOf('@')>-1)?typed:('anon-'+Math.random().toString(36).slice(2)+'@coevolution.local');
 const r=await fetch('/signup?center='+slug,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
 const j=await r.json();
 if(j.key){currentKey=j.key;try{localStorage.setItem('ct_'+slug,currentKey);}catch(e){}
  $('bill').textContent='first '+j.free_sessions+' sessions free, then EUR '+j.price_eur+'/session';return currentKey;}
function showFeedback(){var fb=$('feedback');if(fb)fb.hidden=false;}
function sendFb(v){var note=($('fbtext')||{}).value||'';fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slug:slug,value:v,note:note})}).then(function(){var fb=$('feedback');if(fb)fb.innerHTML='<span class=fbthanks>Danke! Das hilft dem Team.</span>';});}
if($('fbup'))$('fbup').onclick=function(){sendFb(1);};
if($('fbdown'))$('fbdown').onclick=function(){sendFb(-1);};
async function run(){const k=await ensureKey();if(!k)return;}
const tab=window._tab||'t1';const doc=$('doc').value.trim();
 if(tab==='t1'){if(!doc){$('out').innerHTML='<span style=color:#e8c14a>__T_TYPE_QUESTION__</span>';return;}
  showWizStep(3);
  $('run').disabled=true;$('run').textContent='__T_ASKING__';$('out').innerHTML='<span style=color:#9fd0ff>__T_SENT_TO_PANEL__</span>';
  const r=await fetch('/api/center?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({text:doc})});const j=await r.json();
  if(j.run_id){const fin=await poll(j.run_id);$('run').disabled=false;$('run').textContent=$('runlabel').textContent;
   if(fin.synthesis){$('out').innerHTML=renderSynth(fin.synthesis,fin.demo);if(fin.billed_eur!==undefined)$('bill').textContent='billed EUR '+fin.billed_eur;showFeedback();}}
  else{$('out').innerHTML='<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';$('run').disabled=false;$('run').textContent=$('runlabel').textContent;}}
 else if(tab==='t2'){if(!doc){$('out').innerHTML='<span style=color:#e8c14a>__T_DESCRIBE_DECISION__</span>';return;}
  showWizStep(3);
  $('run').disabled=true;$('run').textContent='__T_TESTING__';$('out').innerHTML='<span style=color:#9fd0ff>__T_RUNNING_PAST_PANEL__</span>';
  const r=await fetch('/api/center/scenario?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({action:doc,context:($('ctx').value||'')})});const j=await r.json();
  $('run').disabled=false;$('run').textContent=$('runlabel').textContent;
  $('out').innerHTML=j.synthesis?renderSynth(j.synthesis,j.demo):'<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';showFeedback();}
 else{showWizStep(3);
  $('run').disabled=true;$('run').textContent='__T_CHECKING__';$('out').innerHTML='<span style=color:#9fd0ff>__T_CHECKING_STANDING__</span>';
  const r=await fetch('/api/center/healthcheck?center='+slug,{method:'POST',headers:{Authorization:'Bearer '+k,'Content-Type':'application/json'},body:JSON.stringify({})});const j=await r.json();
  $('run').disabled=false;$('run').textContent=$('runlabel').textContent;
  $('out').innerHTML=j.synthesis?renderSynth(j.synthesis,j.demo):'<span style=color:#ff8a8a>'+esc(JSON.stringify(j))+'</span>';showFeedback();}}
function showTab(n){['t1','t2','t3'].forEach(t=>$(t).classList.toggle('on',t===n));
 $('ctxwrap').style.display=(n==='t2')?'block':'none';
 $('runlabel').textContent=n==='t1'?__T_ASK_LABEL__:(n==='t2'?__T_TEST_LABEL__:__T_CHECK_LABEL__);
 $('run').textContent=$('runlabel').textContent;
 $('doc').placeholder=n==='t1'?__SAMPLE__:(n==='t2'?__T_DECISION_PLACEHOLDER__:__T_CHECK_PLACEHOLDER__);
 window._tab=n;}
// Ask-flow wizard — 3 steps (pick mode → fill in → result) instead of
// tabs+form+output all visible at once. Same underlying data/requests as
// before, just revealed progressively.
function showWizStep(n){['1','2','3'].forEach(function(i){
 $('ws'+i).classList.toggle('on',i===String(n));$('wd'+i).classList.toggle('on',Number(i)<=n);});}
['t1','t2','t3'].forEach(t=>$(t).onclick=()=>{showTab(t);showWizStep(2);});showTab('t1');
document.querySelectorAll('.uc').forEach(b=>b.onclick=()=>{const q=b.getAttribute('data-q')||b.textContent;$('doc').value=q;showTab('t1');showWizStep(2);});
$('wback1').onclick=()=>showWizStep(1);
$('wback2').onclick=()=>{showWizStep(1);$('doc').value='';$('out').innerHTML=__T_WAITING__;};
$('run').onclick=run;
// Modal-level tabs — Overview / How they work / Try it now. Plain show/hide,
// no routing: this is a page inside a page, not worth its own history state.
function showPane(n){['1','2','3'].forEach(function(i){$('ct'+i).classList.toggle('on',i===n);$('cp'+i).classList.toggle('on',i===n);});}
['1','2','3'].forEach(function(i){$('ct'+i).onclick=function(){showPane(i);};});
// Office scene — click a desk to see what that role covers. Real, non-
// fabricated copy: every panel member fires on every question, so the
// "part of the standing team" line is true for whichever desk is clicked.
document.querySelectorAll('.desk').forEach(function(d){
 d.onclick=function(){
  document.querySelectorAll('.desk').forEach(function(o){o.classList.remove('selected');});
  d.classList.add('selected');
  var role=d.getAttribute('data-role');
  var bio=d.getAttribute('data-bio');
  $('deskinfo').innerHTML='<b>'+esc(role)+'.</b> '+esc(bio||role+' — keine Detailbeschreibung hinterlegt.');
 };
});
// Offer click-through beacon — target=_blank so the current tab never unloads,
// a plain fetch is enough (no keepalive/sendBeacon needed).
$('buyLink').addEventListener('click',function(){fetch('__TRACK_URL__',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({path:location.pathname,site:'__TRACK_SITE__',section:slug+':offer_click'})}).catch(function(){});});
// Terrarium — poll this center's own live numbers + any in-flight panel
// session (someone else's, not just yours) so a visitor watches real
// activity happen, not a static snapshot from page-load.
var COLOR_MAP={healthy:'#36d6a0',degraded:'#f0883e','0-status':'#f85c5c'};
var LABEL_MAP=__T_STATUS_LABELS__;
// === Production Office (Canvas, ported 1:1 from detailliertes_sims_office.html) ===
const OFFICE_PANEL = (__PANEL_JSON__ && Array.isArray(__PANEL_JSON__)) ? __PANEL_JSON__ : [];
function officeInit(){
  const cv=$('workshop'); if(!cv){console.log('office: no canvas');return;}
  const ctx=cv.getContext('2d'); const W=cv.width,H=cv.height;
  console.log('office: init',W,H,'panel',OFFICE_PANEL.length);
  const colors={floor:'#d5d0c4',wall:'#ffffff',wallEdge:'#e5e5e5',deskOuter:'#6b7280',deskInner:'#f3f4f6',chairDark:'#374151',chairLight:'#4b5563',plantDark:'#3f6212',plantLight:'#84cc16',paper:'#ffffff',coffee:'#78350f',wood:'#b45309',sofa:'#4b5563',carpet:'#9ca3af'};
  function setShadow(blur,offsetY,alpha){ctx.shadowColor='rgba(0,0,0,'+alpha+')';ctx.shadowBlur=blur;ctx.shadowOffsetY=offsetY;}
  function clearShadow(){ctx.shadowColor='transparent';ctx.shadowBlur=0;ctx.shadowOffsetY=0;}
  function randomRange(min,max){return Math.random()*(max-min)+min;}
  function rr(x,y,w,h,r){if(ctx.roundRect){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}else{ctx.beginPath();ctx.rect(x,y,w,h);}}
  function drawWalls(){setShadow(15,8,.4);ctx.fillStyle=colors.wall;ctx.strokeStyle=colors.wallEdge;ctx.lineWidth=2;
    const walls=[[20,20,1160,20],[20,760,1160,20],[20,20,20,760],[1160,20,20,760],[20,450,250,20],[350,450,150,20],[480,450,20,330],[480,20,20,200],[480,280,20,100],[750,550,430,20]];
    walls.forEach(function(w){rr(w[0],w[1],w[2],w[3],5);ctx.fill();ctx.stroke();});
    clearShadow();ctx.fillStyle='#d1d5db';ctx.fillRect(270,430,80,8);ctx.beginPath();ctx.arc(270,450,80,Math.PI*1.5,Math.PI*2);ctx.stroke();ctx.fillRect(460,200,8,80);clearShadow();}
  function drawChair(x,y,angle){ctx.save();ctx.translate(x,y);ctx.rotate(angle*Math.PI/180);setShadow(6,4,.4);
    ctx.strokeStyle='#1f2937';ctx.lineWidth=3;for(let i=0;i<5;i++){ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(0,-18);ctx.stroke();ctx.fillStyle='#000';ctx.beginPath();ctx.arc(0,-18,3,0,Math.PI*2);ctx.fill();ctx.rotate((Math.PI*2)/5);}
    ctx.fillStyle=colors.chairDark;rr(-14,-12,28,26,8);ctx.fill();
    ctx.fillStyle=colors.chairLight;rr(-16,-20,32,10,5);ctx.fill();
    ctx.fillStyle='#111827';rr(-20,-5,6,16,3);ctx.fill();rr(14,-5,6,16,3);ctx.fill();ctx.restore();}
  function drawPerson(x,y,angle,worker){ctx.save();ctx.translate(x,y);ctx.rotate(angle*Math.PI/180);setShadow(4,3,.3);
    ctx.fillStyle=worker&&worker.shirt?worker.shirt:'#3b82f6';ctx.beginPath();ctx.ellipse(0,4,18,10,0,0,Math.PI*2);ctx.fill();
    ctx.beginPath();ctx.roundRect?ctx.roundRect(-16,4,8,20,4):ctx.rect(-16,4,8,20);ctx.fill();ctx.beginPath();ctx.roundRect?ctx.roundRect(8,4,8,20,4):ctx.rect(8,4,8,20);ctx.fill();
    ctx.fillStyle=worker&&worker.skin?worker.skin:'#fbcfe8';ctx.beginPath();ctx.arc(0,0,10,0,Math.PI*2);ctx.fill();
    const hair=(worker&&worker.hair)?worker.hair:'#1a1919';ctx.fillStyle=hair;ctx.beginPath();ctx.arc(0,-2,10,Math.PI*0.9,Math.PI*0.1);ctx.fill();ctx.restore();}
  function drawDeskAccessories(x,y,rotation,width,height){ctx.save();ctx.translate(x,y);ctx.rotate(rotation*Math.PI/180);clearShadow();
    ctx.fillStyle='#1f2937';ctx.fillRect(-15,-height/2+5,30,8);ctx.fillStyle='#9ca3af';ctx.fillRect(-14,-height/2+6,28,2);
    ctx.fillStyle='#e5e7eb';ctx.fillRect(-12,-height/2+18,24,8);ctx.beginPath();ctx.ellipse(18,-height/2+22,3,5,0,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='rgba(255,255,255,0.9)';ctx.fillRect(-6,-8,12,16);ctx.fillStyle='#d1d5db';ctx.fillRect(-4,-5,8,2);ctx.fillRect(-4,-1,8,2);
    ctx.fillStyle='#d1d5db';ctx.fillRect(6,-2,10,12);ctx.fillStyle='#9ca3af';ctx.fillRect(7,-1,8,2);ctx.fillRect(7,2,8,2);
    ctx.save();ctx.translate(14,12);ctx.shadowColor='rgba(0,0,0,0.3)';ctx.shadowBlur=2;ctx.shadowOffsetY=1;ctx.fillStyle='#ffffff';ctx.beginPath();ctx.arc(0,0,5,0,Math.PI*2);ctx.fill();ctx.fillStyle=colors.coffee;ctx.beginPath();ctx.arc(0,0,4,0,Math.PI*2);ctx.fill();ctx.restore();ctx.restore();}
  function drawDesk(x,y,w,h,rotation,occupied,name,worker){ctx.save();ctx.translate(x,y);ctx.rotate(rotation*Math.PI/180);setShadow(12,6,.4);ctx.fillStyle=colors.deskOuter;rr(-w/2,-h/2,w,h,6);ctx.fill();clearShadow();ctx.fillStyle=colors.deskInner;rr(-w/2+4,-h/2+4,w-8,h-8,4);ctx.fill();ctx.restore();
    drawDeskAccessories(x,y,rotation,w,h);
    drawChair(x+Math.sin(rotation*Math.PI/180)*35,y-Math.cos(rotation*Math.PI/180)*35,rotation);
    if(occupied){drawPerson(x+Math.sin(rotation*Math.PI/180)*25,y-Math.cos(rotation*Math.PI/180)*25,rotation,worker||null);}
    if(name){ctx.fillStyle='#1f2937';ctx.font='bold 11px Inter,sans-serif';ctx.textAlign='center';ctx.fillText(name,x,y+h/2+12);}}
  function drawPlant(x,y,size){ctx.save();ctx.translate(x,y);setShadow(8,4,.4);ctx.fillStyle='#fef3c7';ctx.beginPath();ctx.arc(0,0,size*0.4,0,Math.PI*2);ctx.fill();clearShadow();const leafCount=12;for(let j=0;j<2;j++)for(let i=0;i<leafCount;i++){ctx.save();ctx.rotate((Math.PI*2/leafCount)*i+(j*0.2));ctx.fillStyle=j===0?colors.plantDark:colors.plantLight;ctx.beginPath();ctx.ellipse(0,size*(0.5-j*0.1),size*0.15,size*0.6,0,0,Math.PI*2);ctx.fill();ctx.restore();}ctx.restore();}
  function drawSofa(x,y,rotation){ctx.save();ctx.translate(x,y);ctx.rotate(rotation*Math.PI/180);setShadow(10,5,.4);ctx.fillStyle=colors.sofa;rr(-40,-40,80,30,8);ctx.fill();rr(10,-10,30,60,8);ctx.fill();clearShadow();ctx.strokeStyle='#374151';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(-10,-40);ctx.lineTo(-10,-10);ctx.stroke();ctx.beginPath();ctx.moveTo(10,20);ctx.lineTo(40,20);ctx.stroke();ctx.restore();}
  function drawFoosball(x,y,rotation){ctx.save();ctx.translate(x,y);ctx.rotate(rotation*Math.PI/180);setShadow(15,8,.4);ctx.fillStyle=colors.wood;rr(-40,-60,80,120,4);ctx.fill();clearShadow();ctx.fillStyle='#166534';ctx.fillRect(-30,-50,60,100);ctx.strokeStyle='white';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(-30,0);ctx.lineTo(30,0);ctx.stroke();ctx.beginPath();ctx.arc(0,0,10,0,Math.PI*2);ctx.stroke();const rods=[-40,-20,0,20,40];rods.forEach(function(yPos,index){ctx.strokeStyle='#d1d5db';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(-45,yPos);ctx.lineTo(45,yPos);ctx.stroke();ctx.fillStyle=index%2===0?'#ef4444':'#3b82f6';rr(-10,yPos-3,6,6,2);ctx.fill();rr(4,yPos-3,6,6,2);ctx.fill();});ctx.restore();}
  function _panelPos(n){const pos=[];for(let i=0;i<n;i++){const a=-Math.PI/2+i*2*Math.PI/n;pos.push([W/2+Math.cos(a)*W*0.30,H/2+Math.sin(a)*H*0.30]);}return pos;}
  // ---- precompute all random/strobe-prone values ONCE (not per frame) ----
  const SKINS=['#fbcfe8','#fed7aa','#f3a683','#8d5524','#c68642'];
  const SHIRTS=['#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6'];
  const HAIRS=['#1a1919','#4a3000','#d4af37','#7b2e00','#9ca3af'];
  function _pick(arr){return arr[Math.floor(Math.random()*arr.length)];}
  // panel workers: stable identity
  const _panelWorkers=OFFICE_PANEL.map(function(p){return {skin:_pick(SKINS),shirt:_pick(SHIRTS),hair:_pick(HAIRS)};});
  // meeting room: stable seats
  const _meetingSeats=[];
  for(let a=0;a<360;a+=45){const cx=260+Math.cos(a*Math.PI/180)*160,cy=620+Math.sin(a*Math.PI/180)*90;_meetingSeats.push({cx:cx,cy:cy,occupied:Math.random()>0.3,skin:'#fed7aa',shirt:'#0ea5e9'});}
  // decorative desk people: stable
  const _decoPeople=[];
  [[150,150],[350,150],[250,280],[650,150],[650,210],[770,210],[1000,150]].forEach(function(d){_decoPeople.push({x:d[0],y:d[1],skin:_pick(SKINS),shirt:_pick(SHIRTS)});});
  let t=0;
  const _posCache={};
  function _panelPosCached(n){if(_posCache[n])return _posCache[n];const pos=_panelPos(n);_posCache[n]=pos;return pos;}
  function frame(hubActive){
    try{
    t+=0.004;ctx.clearRect(0,0,W,H);
    ctx.fillStyle=colors.floor;ctx.fillRect(0,0,W,H);
    ctx.fillStyle='#c7c2b5';ctx.fillRect(50,470,420,280);
    ctx.fillStyle='#a8a29e';ctx.beginPath();ctx.ellipse(960,660,120,80,0,0,Math.PI*2);ctx.fill();
    drawWalls();
    // decorative desks (stable people)
    drawDesk(150,150,160,70,0,true,'',_decoPeople[0]);drawDesk(350,150,160,70,0,true,'',_decoPeople[1]);drawDesk(250,280,160,70,180,true,'',_decoPeople[2]);
    drawDesk(650,150,120,60,0,true,'',_decoPeople[3]);drawDesk(650,210,120,60,180,true,'',_decoPeople[4]);drawDesk(770,150,120,60,0,false);drawDesk(770,210,120,60,180,true,'',_decoPeople[5]);
    drawDesk(1000,150,140,60,90,true,'',_decoPeople[6]);drawDesk(1060,250,140,60,180,false);
    // meeting room
    setShadow(15,8,.4);ctx.fillStyle='#9ca3af';ctx.beginPath();ctx.ellipse(260,620,140,70,0,0,Math.PI*2);ctx.fill();clearShadow();ctx.fillStyle='#e5e7eb';ctx.beginPath();ctx.ellipse(260,620,130,60,0,0,Math.PI*2);ctx.fill();
    _meetingSeats.forEach(function(s){drawChair(s.cx,s.cy,Math.atan2(s.cy-620,s.cx-260)*180/Math.PI-90);if(s.occupied)drawPerson(s.cx,s.cy,Math.atan2(s.cy-620,s.cx-260)*180/Math.PI-90,s.skin,s.shirt);});
    drawFoosball(850,650,15);drawSofa(1050,680,-20);
    drawPlant(80,80,40);drawPlant(430,80,30);drawPlant(1100,80,45);drawPlant(80,700,35);drawPlant(430,700,50);drawPlant(720,350,40);drawPlant(1120,450,30);
    // panel desks (the team) — stable workers, ring around hub
    const pos=_panelPosCached(OFFICE_PANEL.length);
    OFFICE_PANEL.forEach(function(p,i){const x=pos[i][0],y=pos[i][1];drawDesk(x,y,120,60,Math.atan2(y-H/2,x-W/2)+Math.PI/2,true,p,_panelWorkers[i]);});
    const hubCol=hubActive?'#36d6a0':'#0f141d';
    // VERY slow, soft pulse (one breath ~ every 16s)
    const pulse=0.5+0.5*Math.sin(t*0.4);
    ctx.fillStyle='#0f141d';ctx.strokeStyle=hubCol;ctx.lineWidth=2+pulse*1.2;ctx.shadowColor=hubCol;ctx.shadowBlur=6*pulse;rr(W/2-60,H/2-26,120,52,12);ctx.fill();ctx.stroke();ctx.shadowBlur=0;
    ctx.fillStyle='#e6edf3';ctx.textAlign='center';ctx.font='bold 15px Inter';ctx.fillText('wartet',W/2,H/2-4);ctx.font='11px Inter';ctx.fillStyle=hubActive?'#36d6a0':'#8b98a9';ctx.fillText('ANFRAGE',W/2,H/2+14);
    // slow, calm dashed flow lines (no frantic motion)
    ctx.strokeStyle=hubCol;ctx.lineWidth=1.5;ctx.setLineDash([6,5]);ctx.lineDashOffset=-t*4;
    OFFICE_PANEL.forEach(function(p,i){const x=pos[i][0],y=pos[i][1];ctx.beginPath();ctx.moveTo(W/2,H/2);ctx.lineTo(x,y-30);ctx.stroke();});
    ctx.setLineDash([]);
    // live indicator (top-right) — replaces the removed top-bar badge
    const liveCol=window.__liveCol||(hubActive?'#36d6a0':'#f0883e');
    const liveTxt=window.__liveStatus||(hubActive?'live · arbeitet':'live · bereit');
    const bw=22+ctx.measureText(liveTxt).width;
    rr(W-bw-18,18,bw,30,15);ctx.fillStyle='rgba(10,14,20,0.72)';ctx.fill();
    ctx.fillStyle=liveCol;ctx.beginPath();ctx.arc(W-bw+1,33,5,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#c7d2e0';ctx.font='bold 12px Inter,sans-serif';ctx.textAlign='left';
    ctx.fillText(liveTxt,W-bw+12,37);
    }catch(e){console.log('office frame error:',e);}
    requestAnimationFrame(function(){frame(window.__hubActive||false);});
  }
  // click a worker desk -> show role info
  function _workerAt(mx,my){
    const pos=_panelPosCached(OFFICE_PANEL.length);
    for(let i=0;i<pos.length;i++){const x=pos[i][0],y=pos[i][1];if(Math.abs(mx-x)<70&&Math.abs(my-y)<40)return OFFICE_PANEL[i];}
    return null;
  }
  cv.addEventListener('click',function(ev){
    const r=cv.getBoundingClientRect();
    const mx=(ev.clientX-r.left)*(W/r.width), my=(ev.clientY-r.top)*(H/r.height);
    const role=_workerAt(mx,my);
    const pop=$('workpopup');
    if(role&&pop){const pretty=role.replace(/-/g,' ');pop.innerHTML='<b>'+pretty.charAt(0).toUpperCase()+pretty.slice(1)+'</b><br>Prüft mit den anderen Fachleuten, ob dein Fall rechtlich und fachlich wasserdicht ist.';pop.hidden=false;}
    else if(pop){pop.hidden=true;}
  });
  frame(false);
}
window.__hubActive=false;
// start office immediately when modal opens (cp2 is the default-visible tab on open)
officeInit();
function maybeOffice(){if($('cp2')&&$('cp2').classList.contains('on'))officeInit();}
document.querySelectorAll('.cmtab').forEach(function(tab){tab.addEventListener('click',function(){setTimeout(maybeOffice,50);});});

function pollLive(){fetch('/api/center/'+slug+'/live').then(function(r){return r.json()}).then(function(s){
var c=COLOR_MAP[s.status]||'#f0883e';var lbl=LABEL_MAP[s.status]||s.status;
$('tled').style.background=c;
var st=$('tstatus');st.textContent=lbl;st.style.color=c;
window.__hubActive=!!s.active_job;
window.__liveCol=c;
window.__liveStatus=(s.active_job?'live · arbeitet':('live · '+lbl));
var wcap=$('wcaption');if(wcap)wcap.textContent=s.active_job?__T_WORKSHOP_ACTIVE__:__T_WORKSHOP_IDLE__;
var runbtn=$('run');if(runbtn&&!runbtn.disabled)runbtn.classList.toggle('idle',!s.active_job);
}).catch(function(){});}
pollLive();window.__cmPollId=setInterval(pollLive,3000);
})();"""
    js = (js.replace("__SLUG__", slug).replace("__SAMPLE__", json.dumps(c["sample_question"]))
          .replace("__PANEL_JSON__", json.dumps(c["panel"]))
          .replace("__TRACK_URL__", TRACK_URL).replace("__TRACK_SITE__", TRACK_SITE)
          .replace("__T_TYPE_QUESTION__", t["type_question"])
          .replace("__T_ASKING__", t["asking"])
          .replace("__T_SENT_TO_PANEL__", t["sent_to_panel"])
          .replace("__T_DESCRIBE_DECISION__", t["describe_decision"])
          .replace("__T_DESK_DEFAULT__", t["desk_default"])
          .replace("__T_TESTING__", t["testing"])
          .replace("__T_RUNNING_PAST_PANEL__", t["running_past_panel"])
          .replace("__T_CHECKING__", t["checking"])
          .replace("__T_CHECKING_STANDING__", t["checking_standing"])
          .replace("__T_ASK_LABEL__", json.dumps(t["ask_label"]))
          .replace("__T_TEST_LABEL__", json.dumps(t["test_label"]))
          .replace("__T_CHECK_LABEL__", json.dumps(t["check_label"]))
          .replace("__T_DECISION_PLACEHOLDER__", json.dumps(t["decision_placeholder"]))
          .replace("__T_CHECK_PLACEHOLDER__", json.dumps(t["check_placeholder"]))
          .replace("__T_STATUS_LABELS__", json.dumps(t["status_labels"]))
          .replace("__T_WORKSHOP_ACTIVE__", json.dumps(t["workshop_active"]))
          .replace("__T_WORKSHOP_IDLE__", json.dumps(t["workshop_idle"]))
          .replace("__T_HUB_ACTIVE__", json.dumps(t["hub_active"]))
          .replace("__T_HUB_IDLE__", json.dumps(t["hub_idle"]))
          .replace("__T_DESK_ROLE_LINE__", json.dumps(t["desk_role_line"]))
          .replace("__T_WAITING__", json.dumps(t["waiting"])))
    return page + "<script>" + js + "</script>" + _tracker_js(slug)



async def center_page_handler(request):
    """GET /{slug} — direct link / no-JS fallback / SEO entry point. Renders
    the SAME landing grid as GET / with this center's card pre-opened in the
    modal server-side (see _firms_grid_body's `open_slug`), so the URL works
    identically whether or not JS ran."""
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    return web.Response(text=_firms_grid_body(request, open_slug=slug), content_type="text/html")


async def center_card_handler(request):
    """GET /api/center/{slug}/card — the modal's inner HTML fragment, fetched
    by the landing page's JS when a hex is clicked (no full page reload)."""
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    lang = request.query.get("lang", "en")
    if lang not in ("en", "de"):
        lang = "en"
    return web.Response(text=center_card_html(slug, lang=lang), content_type="text/html")


async def briefing_page_handler(request):
    slug = request.match_info["slug"]
    if slug not in CENTERS:
        return web.json_response({"error": "unknown center"}, status=404)
    st = load_state()
    briefs = st.get("briefings", {}).get(slug, [])
    c = CENTERS[slug]
    # briefing subscription uses an existing Stripe link (monthly tier).
    # NOTE: Stripe Payment Links ignore ?metadata[...] URL params, so do NOT
    # append it here — real per-center attribution must be baked into the
    # link at creation time in the Stripe Dashboard/API (metadata["center"]).
    sub_link = STRIPE_LINKS["further_dev_monthly"]
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
</div>
{_footer_html()}
</body></html>""", content_type="text/html")


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
<div class=grid>{cards}</div></div>
{_footer_html()}
</body></html>""", content_type="text/html")


HEX_SIZE = 74         # center-to-vertex, px — the polygon's own geometry
HEX_PITCH = HEX_SIZE * 1.22  # a bit looser than true edge-to-edge Catan tiling — a visible
# gap between tiles so 51 of them read as distinct cards instead of a solid packed wall
HEX_POINTS = " ".join(
    f"{HEX_SIZE * math.cos(math.radians(60 * i - 30)):.1f},"
    f"{HEX_SIZE * math.sin(math.radians(60 * i - 30)):.1f}"
    for i in range(6))


LANDING_TR = {
    "de": {
        "title": "CoEvolution AI — {n} voll autonome Firmen, live",
        "h1": "{n} voll autonome Firmen",
        "lede": "Jede Wabe ist eine eigenständige, autonome Firma. Klick rein für die volle Ansicht: was sie tut, was sie gerade live macht, und wie du sie buchst.",
        "lede_hero": "51 autonome, vollautomatische teams",
        "lede_sub": "Klick, scroll, und pan?",
        "kpi_network": "Firmen im Netzwerk",
        "kpi_healthy": "Healthy",
        "kpi_sessions": "Sessions gesamt",
        "kpi_revenue": "Umsatz gesamt",
        "search_placeholder": "Suche nach Problem, Fachgebiet oder Firma (z.B. GDPR, Security, Hiring)",
        "hint_query": '{n} Zentren gefunden für "{q}"',
        "hint_all": "{n} autonome Firmen, live aus dem Netzwerk",
        "empty": "keine Zentren passen zur Suche",
        "stat_sessions": "Sitzungen",
        "stat_leads": "Anfragen",
        "lang_toggle": "English",
        "mainsite": "rfi-irfos.com ↗",
        "zoom_reset": "Zurücksetzen",
    },
    "en": {
        "title": "CoEvolution AI — {n} fully autonomous teams, live",
        "h1": "{n} fully autonomous teams",
        "lede": "Each tile is its own standing team. Click in for the full picture: what it does, what it's doing live right now, and how to book it.",
        "lede_hero": "51 autonomous, fully automatic teams",
        "lede_sub": "Click, scroll, and pan?",
        "kpi_network": "Teams in the network",
        "kpi_healthy": "Healthy",
        "kpi_sessions": "Total sessions",
        "kpi_revenue": "Total revenue",
        "search_placeholder": "Search by problem, topic or team (e.g. GDPR, security, hiring)",
        "hint_query": '{n} teams match "{q}"',
        "hint_all": "{n} autonomous teams, live from the network",
        "empty": "no teams match that search",
        "stat_sessions": "sessions",
        "stat_leads": "leads",
        "lang_toggle": "Deutsch",
        "mainsite": "rfi-irfos.com ↗",
        "zoom_reset": "Reset",
    },
}


def _smart_order(items):
    """Order centers so graph-adjacent ones (real feeds_into edges from
    CENTER_NETWORK) land next to each other in the spiral, instead of raw
    catalog order — a visitor scanning the grid sees related teams
    clustered together instead of scattered at random. Simple greedy walk:
    from the current tile, prefer an unplaced neighbor; otherwise jump to
    the next unplaced item in the original list."""
    remaining = dict(items)
    order = []
    slug_order = [s for s, _ in items]
    cursor = slug_order[0] if slug_order else None
    while remaining:
        if cursor not in remaining:
            cursor = next(iter(remaining))
        c = remaining.pop(cursor)
        order.append((cursor, c))
        nxt = next((a for a in CENTER_NETWORK.get(cursor, []) if a in remaining), None)
        cursor = nxt if nxt is not None else next(iter(remaining), None)
    return order


# Per-tile category icons — plain geometric line-icons (viewBox 0 0 24 24,
# stroke=currentColor), no external icon library/network fetch. Assigned per
# slug rather than fuzzy keyword-matched so the grouping is a deliberate,
# checked choice (e.g. "coin" = finance/tax/payments, "scale" = legal/
# governance) instead of accidental collisions from substring matching.
HEX_ICONS = {
    "shield": '<path d="M12 2 L20 5 V11 C20 16 16.5 20 12 22 C7.5 20 4 16 4 11 V5 Z"/>',
    "scale": '<path d="M12 4 V20 M6 20 H18 M5 7 H19"/><circle cx=6 cy=11 r=3/><circle cx=18 cy=11 r=3/>',
    "coin": '<circle cx=12 cy=12 r=8/><text x=12 y=16 text-anchor=middle font-size=10 stroke=none fill=currentColor>€</text>',
    "lock": '<rect x=5 y=11 width=14 height=9 rx=2/><path d="M8 11 V8 A4 4 0 0 1 16 8 V11"/>',
    "heart": '<path d="M12 20 C4 14 3 9 6 6.5 C8 5 10.5 5.5 12 8 C13.5 5.5 16 5 18 6.5 C21 9 20 14 12 20 Z"/>',
    "leaf": '<path d="M4 20 C4 10 12 4 20 4 C20 12 14 20 4 20 Z M6 18 C10 14 14 10 18 6"/>',
    "truck": '<rect x=2 y=9 width=12 height=8/><path d="M14 11 H19 L22 14 V17 H14 Z"/><circle cx=7 cy=19 r=2/><circle cx=18 cy=19 r=2/>',
    "cpu": '<rect x=6 y=6 width=12 height=12 rx=1/><rect x=10 y=10 width=4 height=4/>',
    "users": '<circle cx=9 cy=8 r=3/><path d="M3 20 C3 15 6 13 9 13 C12 13 15 15 15 20"/><circle cx=17 cy=9 r=2.5/><path d="M14 20 C14 16.5 16 15 18 15 C20 15 21.5 16.5 21.5 19.5"/>',
    "speech": '<rect x=3 y=5 width=18 height=12 rx=2/><path d="M7 17 V22 L12 17"/>',
    "alert": '<path d="M12 3 L22 20 H2 Z"/><path d="M12 9 V14"/><circle cx=12 cy=17 r=.9 fill=currentColor stroke=none/>',
    "eye": '<ellipse cx=12 cy=12 rx=9 ry=5/><circle cx=12 cy=12 r=2.5/>',
    "grid": '<rect x=3 y=3 width=7 height=7/><rect x=14 y=3 width=7 height=7/><rect x=3 y=14 width=7 height=7/><rect x=14 y=14 width=7 height=7/>',
}
# One accent color per icon category — deliberately NOT tied to live status
# (which is always green/amber/red for healthy/degraded/offline). Without
# this, every center's modal used the status color for its icon badge too,
# so a healthy site was wall-to-wall green regardless of what the center
# actually does — this is the fix for that (confirmed live 2026-07-18).
# "shield" (gdpr-guard, the most-clicked demo center) deliberately avoids
# the brand teal (#36d6a0, also the "healthy" status color) so THAT
# specific center doesn't look unchanged — confirmed still-green complaint
# was this exact collision, not a leftover bug.
ICON_COLORS = {
    "shield": "#60a5fa", "scale": "#a78bfa", "coin": "#fbbf24", "lock": "#38bdf8",
    "heart": "#fb7185", "leaf": "#4ade80", "truck": "#fb923c", "cpu": "#22d3ee",
    "users": "#c084fc", "speech": "#f472b6", "alert": "#f87171", "eye": "#818cf8",
    "grid": "#a3e635",
}
ICON_BY_SLUG = {
    "gdpr-guard": "shield", "ai-act-guard": "cpu", "sox-controls": "coin",
    "hipaa-check": "heart", "contract-risk": "scale", "ip-watch": "scale",
    "employment-law": "users", "litigation-risk": "scale", "license-audit": "cpu",
    "tax-exposure": "coin", "vendor-risk": "truck", "cyber-posture": "lock",
    "threat-intel": "eye", "incident-readiness": "alert", "data-governance": "shield",
    "a11y-audit": "eye", "esg-report": "leaf", "carbon-audit": "leaf",
    "supply-chain-risk": "truck", "procure-leak": "coin", "ma-diligence": "scale",
    "board-gov": "scale", "investor-disclosure": "coin", "crisis-comms": "speech",
    "insurance-review": "shield", "clinical-doc": "heart", "finserv-compliance": "coin",
    "saas-security": "lock", "payments-compliance": "coin", "crypto-reg": "coin",
    "lease-review": "truck", "franchise-compliance": "scale", "nonprofit-gov": "scale",
    "export-control": "alert", "product-safety": "alert", "recall-readiness": "truck",
    "pharma-labeling": "heart", "food-safety": "heart", "energy-compliance": "leaf",
    "telecom-compliance": "alert", "edu-compliance": "shield", "child-safety": "shield",
    "content-policy": "speech", "bias-audit": "cpu", "model-card": "cpu",
    "breach-readiness": "shield", "whistleblower": "speech", "antitrust": "scale",
    "audit-readiness": "coin", "resilience-review": "truck",
}


# Individual company logos — ONE distinct hand-authored glyph per company
# (viewBox 0 0 24 24, stroke=currentColor, same line style as HEX_ICONS),
# because 51 companies sharing 12 category icons made them indistinguishable
# (user feedback 2026-07-19: "they all should have gotten individual SVG
# logos"). Category icons in HEX_ICONS remain as the fallback for daughter
# centers and any future slug without a bespoke mark.
COMPANY_ICONS = {
    "gdpr-guard": '<path d="M12 2 L20 5 V11 C20 16 16.5 20 12 22 C7.5 20 4 16 4 11 V5 Z"/><circle cx=12 cy=10 r=2.2/><path d="M12 12.2 V15.5"/>',
    "ai-act-guard": '<rect x=5 y=5 width=14 height=14 rx=2/><path d="M9 12 L11.2 14.4 L15.4 9.6"/><path d="M9 2.5 V5 M15 2.5 V5 M9 19 V21.5 M15 19 V21.5 M2.5 9 H5 M2.5 15 H5 M19 9 H21.5 M19 15 H21.5"/>',
    "sox-controls": '<path d="M4 20 H20"/><rect x=5 y=11 width=3 height=9/><rect x=10.5 y=7 width=3 height=13/><rect x=16 y=13 width=3 height=7/><path d="M5 5 L11 3.5 L17 5"/>',
    "hipaa-check": '<path d="M12 20 C4 14 3 9 6 6.5 C8 5 10.5 5.5 12 8 C13.5 5.5 16 5 18 6.5 C21 9 20 14 12 20 Z"/><path d="M7 12 H10 L11.3 9.5 L12.8 14 L14 12 H17"/>',
    "contract-risk": '<path d="M6 2.5 H15 L19 6.5 V21.5 H6 Z"/><path d="M15 2.5 V6.5 H19"/><path d="M9 12 H16 M9 15 H16"/><path d="M9 18.5 C10 17.5 11 19.5 12.5 18.2"/>',
    "ip-watch": '<path d="M12 3 C8.7 3 6 5.7 6 9 C6 11.2 7.2 13 8.7 14.2 L9 17 H15 L15.3 14.2 C16.8 13 18 11.2 18 9 C18 5.7 15.3 3 12 3 Z"/><path d="M10 20 H14"/>',
    "employment-law": '<rect x=3.5 y=8 width=17 height=12 rx=2/><path d="M9 8 V6 C9 5 9.8 4 11 4 H13 C14.2 4 15 5 15 6 V8"/><path d="M3.5 13 H20.5 M12 12 V14.5"/>',
    "litigation-risk": '<path d="M5 21 H14"/><path d="M9.5 21 V13"/><path d="M4.5 8.5 L10 3 L16.5 9.5 L11 15 Z"/><path d="M13 12 L20 19"/>',
    "license-audit": '<path d="M8.5 7 L4.5 12 L8.5 17"/><path d="M15.5 7 L19.5 12 L15.5 17"/><circle cx=12 cy=19.5 r=1.6/><path d="M12 14.5 V17.9"/>',
    "tax-exposure": '<circle cx=12 cy=12 r=9/><path d="M8.5 15.5 L15.5 8.5"/><circle cx=9 cy=9 r=1.6/><circle cx=15 cy=15 r=1.6/>',
    "vendor-risk": '<rect x=2 y=9 width=12 height=8/><path d="M14 11 H19 L22 14 V17 H14 Z"/><circle cx=7 cy=19 r=2/><circle cx=18 cy=19 r=2/>',
    "cyber-posture": '<rect x=5 y=11 width=14 height=9 rx=2/><path d="M8 11 V8 A4 4 0 0 1 16 8 V11"/><path d="M12 14.5 V17"/>',
    "threat-intel": '<circle cx=12 cy=12 r=9/><circle cx=12 cy=12 r=5/><circle cx=12 cy=12 r=1.2 fill=currentColor stroke=none/><path d="M12 12 L18.5 5.5"/>',
    "incident-readiness": '<path d="M6 20 H18 V17 C18 12 16 9 12 9 C8 9 6 12 6 17 Z"/><path d="M12 9 V6.5 M5.5 11 L3.8 9.6 M18.5 11 L20.2 9.6 M4 20 H20"/>',
    "data-governance": '<ellipse cx=12 cy=6 rx=7 ry=2.8/><path d="M5 6 V12 C5 13.5 8.1 14.8 12 14.8 C15.9 14.8 19 13.5 19 12 V6"/><path d="M5 12 V18 C5 19.5 8.1 20.8 12 20.8 C15.9 20.8 19 19.5 19 18 V12"/>',
    "a11y-audit": '<circle cx=12 cy=5 r=2/><path d="M4.5 9 C9 10.2 15 10.2 19.5 9"/><path d="M12 10 V14.5"/><path d="M12 14.5 L8.5 20.5 M12 14.5 L15.5 20.5"/>',
    "esg-report": '<circle cx=12 cy=12 r=9/><path d="M12 3 C12 3 7 8 7 12 C7 16 12 21 12 21"/><path d="M12 3 C12 3 17 8 17 12 C17 16 12 21 12 21"/><path d="M3.8 9.5 H20.2 M3.8 14.5 H20.2"/>',
    "carbon-audit": '<path d="M7 17.5 A4.5 4.5 0 0 1 7.5 8.6 A6 6 0 0 1 19 10.5 A3.7 3.7 0 0 1 18 17.5 Z"/><path d="M9.5 13.8 C9.5 12.3 11.8 12.3 11.8 13.8 C11.8 15.3 9.5 15.3 9.5 13.8 M13 12.5 V15"/>',
    "supply-chain-risk": '<rect x=2.5 y=9.5 width=6 height=5 rx=2.4/><rect x=15.5 y=9.5 width=6 height=5 rx=2.4/><path d="M8.5 12 H15.5"/>',
    "procure-leak": '<path d="M4 4 H20 L14 11.5 V18 L10 20.5 V11.5 Z"/><path d="M17.5 16 C17.5 16 19.5 18.2 19.5 19.4 A1.9 1.9 0 0 1 15.6 19.4 C15.6 18.2 17.5 16 17.5 16"/>',
    "ma-diligence": '<circle cx=8.5 cy=12 r=5.5/><circle cx=15.5 cy=12 r=5.5/>',
    "board-gov": '<circle cx=12 cy=12 r=3/><circle cx=12 cy=4 r=1.7/><circle cx=19 cy=8 r=1.7/><circle cx=19 cy=16 r=1.7/><circle cx=12 cy=20 r=1.7/><circle cx=5 cy=16 r=1.7/><circle cx=5 cy=8 r=1.7/>',
    "investor-disclosure": '<path d="M3.5 20.5 V13 M8 20.5 V9 M12.5 20.5 V12 M17 20.5 V6"/><path d="M3.5 8 L9 4.5 L13.5 8 L20.5 3.5"/><path d="M17 3.5 H20.5 V7"/>',
    "crisis-comms": '<path d="M3.5 10 V14 L6.5 14.5 L14 19 V5 L6.5 9.5 Z"/><path d="M17 9 C18 10.5 18 13.5 17 15 M19.7 6.7 C21.6 9.5 21.6 14.5 19.7 17.3"/>',
    "insurance-review": '<path d="M12 3 C7 3 3.5 6.5 3 11 C4.5 9.8 6.5 9.8 8 11 C9.5 9.8 10.5 9.8 12 11 C13.5 9.8 14.5 9.8 16 11 C17.5 9.8 19.5 9.8 21 11 C20.5 6.5 17 3 12 3 Z"/><path d="M12 11 V18 A2.5 2.5 0 0 1 7 18"/>',
    "clinical-doc": '<rect x=5 y=4 width=14 height=17.5 rx=2/><path d="M9 4 V2.5 H15 V4"/><path d="M12 9 V15 M9 12 H15"/>',
    "finserv-compliance": '<path d="M3 9.5 L12 3.5 L21 9.5"/><path d="M5 9.5 V18 M9.7 9.5 V18 M14.3 9.5 V18 M19 9.5 V18"/><path d="M3 20.5 H21"/>',
    "saas-security": '<path d="M6.5 18 A4 4 0 0 1 7 10.1 A5.5 5.5 0 0 1 17.6 11.8 A3.5 3.5 0 0 1 17.5 18 Z"/><rect x=9.5 y=13 width=5 height=4 rx=1/><path d="M10.7 13 V11.8 A1.3 1.3 0 0 1 13.3 11.8 V13"/>',
    "payments-compliance": '<rect x=2.5 y=5.5 width=19 height=13 rx=2.5/><path d="M2.5 9.5 H21.5"/><path d="M6 15 H10 M14 15 L15.4 16.2 L18 13.5"/>',
    "crypto-reg": '<path d="M12 2.5 L20 7 V17 L12 21.5 L4 17 V7 Z"/><path d="M9.5 8 H13.4 A1.9 1.9 0 0 1 13.4 11.9 H9.5 M9.5 11.9 H14 A1.9 1.9 0 0 1 14 15.9 H9.5 M9.5 8 V15.9 M11.3 6.3 V8 M11.3 15.9 V17.6"/>',
    "lease-review": '<path d="M3.5 20.5 V6.5 L9.5 3 V20.5"/><path d="M9.5 8.5 L20.5 8.5 V20.5"/><path d="M3.5 20.5 H20.5"/><path d="M13 12 H15 M17 12 H18 M13 16 H15"/><circle cx=6.5 cy=11 r=1/>',
    "franchise-compliance": '<path d="M3.5 9 L5 4 H19 L20.5 9"/><path d="M3.5 9 C3.5 10.4 4.6 11.5 6 11.5 C7.4 11.5 8.5 10.4 8.5 9 C8.5 10.4 9.6 11.5 11 11.5 C12.4 11.5 13.5 10.4 13.5 9 C13.5 10.4 14.6 11.5 16 11.5 C17.4 11.5 18.5 10.4 18.5 9"/><path d="M5 11.5 V20 H19 V11.5"/><rect x=10 y=15 width=4 height=5/>',
    "nonprofit-gov": '<path d="M3 13 C3 13 5 11 7.5 12 L12 14"/><path d="M3 17.5 L7 18.5 L14.5 17 C16.5 16.5 19 14.5 21 12 C19.5 11 18 11.5 16.5 12.5 L13.5 14.3"/><path d="M12 4 C10.8 2.8 8.8 3 8 4.5 C7.4 5.7 8 7 9.5 8.3 L12 10.3 L14.5 8.3 C16 7 16.6 5.7 16 4.5 C15.2 3 13.2 2.8 12 4 Z"/>',
    "export-control": '<circle cx=10.5 cy=12 r=8/><path d="M2.5 12 H18.5 M10.5 4 C13 6.5 13 17.5 10.5 20 M10.5 4 C8 6.5 8 17.5 10.5 20"/><path d="M15 17 L21.5 17 M18.8 14 L21.8 17 L18.8 20"/>',
    "product-safety": '<path d="M12 2.5 L20.5 6.5 V12 C20.5 17 17 20.5 12 22 C7 20.5 3.5 17 3.5 12 V6.5 Z"/><path d="M8 8.5 L16 15.5 M16 8.5 L8 15.5"/>',
    "recall-readiness": '<path d="M12 4 A8 8 0 1 1 4.5 9.5"/><path d="M4.5 4.5 V9.5 H9.5"/><path d="M9.5 12.5 L11.5 14.5 L15 10.5"/>',
    "pharma-labeling": '<rect x=3 y=8.8 width=18 height=6.4 rx=3.2 transform="rotate(-45 12 12)"/><path d="M8.5 15.5 L15.5 8.5"/><path d="M11 11 L13.5 13.5"/>',
    "food-safety": '<path d="M6 2.5 V10 M3.8 2.5 V6.5 C3.8 7.6 4.7 8.5 6 8.5 C7.3 8.5 8.2 7.6 8.2 6.5 V2.5"/><path d="M6 10 V21.5"/><path d="M16.5 2.5 C14.5 4 13.5 7 13.5 9.5 C13.5 11.5 14.7 13 16.5 13 V21.5 M16.5 13 C18.3 13 19.5 11.5 19.5 9.5 C19.5 7 18.5 4 16.5 2.5"/>',
    "energy-compliance": '<path d="M13.5 2.5 L5 13.5 H11 L10.5 21.5 L19 10.5 H13 Z"/>',
    "telecom-compliance": '<path d="M12 21 V11"/><circle cx=12 cy=9.5 r=1.6/><path d="M8.8 13 C7 11.2 7 7.8 8.8 6 M15.2 13 C17 11.2 17 7.8 15.2 6"/><path d="M6 15.5 C3 12.5 3 6.5 6 3.5 M18 15.5 C21 12.5 21 6.5 18 3.5"/>',
    "edu-compliance": '<path d="M2.5 9 L12 4 L21.5 9 L12 14 Z"/><path d="M6.5 11.5 V16.5 C6.5 18 9 19.5 12 19.5 C15 19.5 17.5 18 17.5 16.5 V11.5"/><path d="M21.5 9 V15"/>',
    "child-safety": '<circle cx=12 cy=7 r=3/><path d="M5.5 21 C5.5 16.5 8.4 14 12 14 C15.6 14 18.5 16.5 18.5 21"/><path d="M4 8.5 C4 6 8 6 12 6 C16 6 20 6 20 8.5"/>',
    "content-policy": '<path d="M5.5 21.5 V3.5"/><path d="M5.5 4 C9 2 12 6 19 4 V13.5 C12 15.5 9 11.5 5.5 13.5"/>',
    "bias-audit": '<path d="M12 4 V20 M5 20 H19"/><path d="M4 7.5 H20"/><path d="M6.5 7.5 L4.5 12.5 A2.6 2.6 0 0 0 8.5 12.5 Z"/><path d="M17.5 7.5 L15.5 15 A2.6 2.6 0 0 0 19.5 15 Z"/>',
    "model-card": '<rect x=4 y=5 width=16 height=14 rx=2/><circle cx=8.5 cy=10 r=1.4/><circle cx=15.5 cy=10 r=1.4/><circle cx=12 cy=14.5 r=1.4/><path d="M9.6 10.8 L11 13.4 M14.4 10.8 L13 13.4"/>',
    "breach-readiness": '<path d="M12 2 L20 5 V11 C20 16 16.5 20 12 22 C7.5 20 4 16 4 11 V5 Z"/><path d="M12 7 V13"/><circle cx=12 cy=16.5 r=1 fill=currentColor stroke=none/>',
    "whistleblower": '<circle cx=8 cy=14 r=5.5/><path d="M12.5 10.5 L21 5.5 L21.5 8.5 L14.5 12.5"/><circle cx=8 cy=14 r=1.4/>',
    "antitrust": '<rect x=3.5 y=3.5 width=7.3 height=7.3 rx=1.5/><rect x=13.2 y=3.5 width=7.3 height=7.3 rx=1.5/><rect x=3.5 y=13.2 width=7.3 height=7.3 rx=1.5/><path d="M13.2 16.8 H20.5 M16.8 13.2 V20.5"/>',
    "audit-readiness": '<rect x=4.5 y=3 width=15 height=18 rx=2/><path d="M8 8 L9.2 9.2 L11.5 6.9 M13.5 8 H16.5"/><path d="M8 13 L9.2 14.2 L11.5 11.9 M13.5 13 H16.5"/><path d="M8 18 L9.2 19.2 L11.5 16.9 M13.5 18 H16.5"/>',
    "resilience-review": '<path d="M12 3 A9 9 0 1 1 3.5 9"/><path d="M3.5 3.5 V9 H9"/><path d="M8 13.5 L10.5 16 L16.5 10"/>',
}


def _hex_icon(slug):
    if slug in COMPANY_ICONS:
        return COMPANY_ICONS[slug]
    # daughter/spin-off centers inherit the parent's logo
    parent = CENTERS.get(slug, {}).get("parent")
    if parent and parent in COMPANY_ICONS:
        return COMPANY_ICONS[parent]
    return HEX_ICONS[ICON_BY_SLUG.get(slug, "shield")]


def _firms_grid_body(request, open_slug=None):
    """Builds the landing page — the {N} centers as a Catan-style honeycomb:
    each a real SVG <polygon> hex (true geometry, clickable, no canvas
    hit-testing) with an HTML <foreignObject> overlay for the name/LED/live
    numbers, laid out via a deterministic organic-growth placement
    (_organic_hex_coords) over a network-clustered ordering (_smart_order)
    and revealed with a staggered per-ring CSS animation on load. Live
    numbers (sessions/revenue/leads/status) are polled from /api/live-grid
    every ~10s and patched into the DOM in place.

    A center's detail view is a MODAL over this same grid, not a separate
    page — clicking a hex fetches /api/center/{slug}/card and injects it
    into #cmbody instead of navigating. `open_slug`, when set (used by
    GET /{slug} for direct links / no-JS fallback / SEO), pre-renders that
    center's card server-side with the modal already open, so the exact
    same URL works whether JS ran or not.
    """
    q = (request.query.get("q") or "").strip().lower()
    lang = request.query.get("lang", "de")
    if lang not in ("en", "de"):
        lang = "de"
    t = LANDING_TR[lang]
    other_lang = "de" if lang == "en" else "en"

    items = list(CENTERS.items())
    if q:
        items = [(s, c) for s, c in items
                 if q in c["name"].lower() or q in (c.get("mandate") or "").lower()
                 or any(q in d.lower() for d in c.get("disciplines") or [])]
    items = _smart_order(items)

    pad = HEX_SIZE + 20
    if items:
        coords = _organic_hex_coords(len(items))
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
            f'<a href="/{s}?lang={lang}">'
            f'<polygon class=hexshape points="{HEX_POINTS}" data-c="{color}" style="stroke:{color}"/>'
            f'<foreignObject x="{-fo_size/2:.1f}" y="{-fo_size/2:.1f}" width="{fo_size:.1f}" height="{fo_size:.1f}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class=hexbody>'
            f'<svg class=hexicon viewBox="0 0 24 24" fill=none stroke="#cdd9e5" stroke-width=1.6 '
            f'stroke-linecap=round stroke-linejoin=round>{_hex_icon(s)}</svg>'
            f'<div class=hexname>{html.escape(c["name"])}</div>'
            f'<div class=hexled style="background:{color}"></div>'
            f'</div></foreignObject>'
            f'</a></g></g>')

    tiles_svg = "".join(_tile(i, s, c) for i, (s, c) in enumerate(items))
    empty_note = "" if items else f'<div class=empty>{t["empty"]}</div>'

    hint = (t["hint_query"].format(n=len(items), q=html.escape(q))
            if q else t["hint_all"].format(n=len(CENTERS)))

    nav_badge = ''
    qparam = ("q=" + html.escape(q) + "&") if q else ""
    nav_right = (
        f'<form class=navsearchform method=get><div class=navsearchwrap>'
        f'<svg class=navsearchicon viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><circle cx=11 cy=11 r=7/><path d="M20 20 L16.2 16.2"/></svg>'
        f'<input class=navsearch name=q placeholder="{t["search_placeholder"]}" value="{html.escape(q)}"></div></form>'
        + _lang_switch_html(lang, f"?{qparam}lang=de", f"?{qparam}lang=en"))

    modal_open = open_slug is not None
    modal_inner = center_card_html(open_slug, lang) if modal_open else ""

    body = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{t['title'].format(n=len(CENTERS)) if not modal_open else CENTERS[open_slug]['name'] + ' — CoEvolution AI'}</title>
<style>
@keyframes hexin{{0%{{opacity:0;transform:scale(.55)}}70%{{opacity:1}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
body{{margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Inter,sans-serif;line-height:1.5}}
.wrap{{width:100%;max-width:none;margin:0;padding:80px 40px 40px;box-sizing:border-box}}
h1{{font-size:30px;font-weight:800;margin:0 0 6px;letter-spacing:-.01em;max-width:900px;line-height:1.25;
background:linear-gradient(90deg,#e6edf3,#9fd0ff 60%,#36d6a0);-webkit-background-clip:text;background-clip:text;color:transparent}}
.ledesub{{color:#8b98a9;font-size:15px;max-width:640px;margin:0 0 8px}}
.lede{{color:#8b98a9;font-size:17px;max-width:680px;margin:0 0 8px}}
.lede a{{color:#4ea1ff;text-decoration:none}}
.hint{{color:#5b6675;font-size:12px;margin:0 0 8px}}
.hcwrap{{position:relative;width:calc(100% + 80px);margin:0 -40px;height:85vh;min-height:520px;overflow:hidden;
background:radial-gradient(ellipse at center,#0d1219,#0a0e14 75%);border:1px solid #1c2733;border-radius:14px;cursor:grab}}
.hcwrap.dragging{{cursor:grabbing}}
.honeycomb{{display:block;position:absolute;top:0;left:0;transform-origin:0 0;will-change:transform}}
.zoomctl{{position:absolute;bottom:14px;right:14px;display:flex;flex-direction:column;gap:6px;z-index:5}}
.zoomctl button{{width:32px;height:32px;background:#0f141d;border:1px solid #1c2733;border-radius:8px;color:#e6edf3;font-size:16px;cursor:pointer;line-height:1}}
.zoomctl button:hover{{border-color:#2c4258}}
.zoomctl .zreset{{font-size:10px;letter-spacing:.02em}}
.hex{{animation:hexin .5s cubic-bezier(.2,.9,.3,1.2) both}}
.hex a{{display:block;text-decoration:none;color:inherit;cursor:pointer}}
.hexshape{{fill:#0f141d;stroke-width:1.5;transition:fill .2s,stroke-width .2s;paint-order:stroke}}
.hex:hover .hexshape{{fill:#141c28;stroke-width:2.5}}
.hexbody{{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:6px;box-sizing:border-box;font-family:-apple-system,Segoe UI,Inter,sans-serif;pointer-events:none}}
.hexicon{{width:26px;height:26px;margin-bottom:5px;flex-shrink:0;color:#cdd9e5}}
.hexname{{color:#e6edf3;font-weight:650;font-size:10.5px;line-height:1.22;margin-bottom:4px;overflow-wrap:break-word;hyphens:auto}}
.hexled{{width:7px;height:7px;border-radius:50%;margin-bottom:4px;animation:blink 1.8s ease-in-out infinite}}
.hexstats{{color:#8b98a9;font-size:9.5px;font-variant-numeric:tabular-nums;letter-spacing:.01em}}
.empty{{color:#5b6675;text-align:center;padding:30px}}
.foot{{color:#5b6675;font-size:12px;margin-top:36px}}
.cmoverlay{{position:fixed;inset:0;z-index:200;background:rgba(6,9,13,.72);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:24px}}
.cmpanel{{position:relative;width:100%;max-width:1180px;height:min(860px,92vh);max-height:92vh;background:#0a0e14;border:1px solid #1c2733;border-radius:20px;box-shadow:0 30px 80px rgba(0,0,0,.6);overflow:hidden;display:flex;flex-direction:column}}
.cmscroll{{overflow-y:auto;padding:30px 34px 0}}
.cmclosebtn{{position:absolute;top:14px;right:14px;z-index:5;width:32px;height:32px;border-radius:50%;background:#0f141d;border:1px solid #1c2733;color:#c7d2e0;font-size:18px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center}}
.cmclosebtn:hover{{border-color:#2c4258;color:#fff}}
@media(max-width:640px){{.hexname{{font-size:9.5px}}.hexstats{{font-size:8.5px}}.hcwrap{{height:60vh}}
.cmoverlay{{padding:0}}.cmpanel{{max-width:none;max-height:100vh;height:100vh;border-radius:0}}
.wizsteps{{display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:18px}}
.wizdot{{width:24px;height:24px;border-radius:50%;background:#0f141d;border:1px solid #1c2733;color:#5b6675;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}}
.wizdot.on{{background:#36d6a0;color:#04140d}}
</style></head><body>{_nav_html('centers', brand_extra=nav_badge, right_html=nav_right)}<div class=wrap>
<h1>{t['lede_hero']}</h1>
<p class=ledesub>{t['lede_sub']}</p>
{f'<p class=hint>{hint}</p>' if q else ''}
{empty_note}
<div class=hcwrap id=hcwrap>
<svg class=honeycomb id=honeycomb viewBox="0 0 {vb_w:.1f} {vb_h:.1f}" width="{vb_w:.1f}" height="{vb_h:.1f}" xmlns="http://www.w3.org/2000/svg">{tiles_svg}</svg>
<div class=zoomctl>
<button id=zin type=button title="zoom in">+</button>
<button id=zout type=button title="zoom out">−</button>
<button id=zreset type=button class=zreset>{t['zoom_reset']}</button>
</div>
</div>
</div>
<div id=centermodal class=cmoverlay style="display:{'flex' if modal_open else 'none'}">
<div class=cmpanel>
<button id=cmclose class=cmclosebtn type=button aria-label=close>&times;</button>
<div id=cmbody class=cmscroll>{modal_inner}</div>
</div>
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
var ld=g.querySelector('[data-k=leads]');if(ld)ld.textContent=s.leads;
}});}}).catch(function(){{}});}}
setInterval(poll,10000);
// Pan/zoom the honeycomb — CSS transform on the SVG element itself inside a
// fixed-height clipping viewport, no canvas re-render needed since the SVG
// stays the same DOM, we just move/scale it. Wheel = zoom (centered on
// cursor), drag = pan, buttons = discrete zoom, reset = fit-to-view.
(function(){{
var wrap=document.getElementById('hcwrap'),svg=document.getElementById('honeycomb');
var vbW={vb_w:.1f},vbH={vb_h:.1f};
var scale=1,tx=0,ty=0,dragging=false,dragged=false,lastX=0,lastY=0;
function fit(){{var r=wrap.getBoundingClientRect();
 var s=Math.min(r.width/vbW,r.height/vbH,1);scale=s;
 tx=(r.width-vbW*s)/2;ty=(r.height-vbH*s)/2;apply();}}
function apply(){{svg.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')';svg.style.transformOrigin='0 0';}}
function clampScale(v){{return Math.max(0.25,Math.min(3,v));}}
wrap.addEventListener('wheel',function(e){{e.preventDefault();
 var r=wrap.getBoundingClientRect();var mx=e.clientX-r.left,my=e.clientY-r.top;
 var old=scale;var ns=clampScale(scale*(e.deltaY<0?1.12:0.89));
 tx=mx-(mx-tx)*(ns/old);ty=my-(my-ty)*(ns/old);scale=ns;apply();}},{{passive:false}});
wrap.addEventListener('mousedown',function(e){{dragging=true;dragged=false;lastX=e.clientX;lastY=e.clientY;wrap.classList.add('dragging');}});
window.addEventListener('mousemove',function(e){{if(!dragging)return;var dx=e.clientX-lastX,dy=e.clientY-lastY;
 if(Math.abs(dx)>3||Math.abs(dy)>3)dragged=true;tx+=dx;ty+=dy;lastX=e.clientX;lastY=e.clientY;apply();}});
window.addEventListener('mouseup',function(){{dragging=false;wrap.classList.remove('dragging');}});
wrap.addEventListener('click',function(e){{if(dragged){{e.stopPropagation();e.preventDefault();dragged=false;}}}},true);
document.getElementById('zin').onclick=function(){{scale=clampScale(scale*1.25);apply();}};
document.getElementById('zout').onclick=function(){{scale=clampScale(scale*0.8);apply();}};
document.getElementById('zreset').onclick=fit;
window.addEventListener('resize',fit);
fit();
}})();
// Center-detail MODAL — clicking a hex fetches /api/center/{{slug}}/card and
// injects it here instead of navigating to a separate page. Scripts inside
// an innerHTML-injected fragment don't auto-execute (browser rule), so
// execScripts() re-creates and re-inserts them — that's the one bit of
// non-obvious plumbing this needs.
(function(){{
var modal=document.getElementById('centermodal'),cmbody=document.getElementById('cmbody');
var CUR_LANG='{lang}';
function execScripts(container){{
 container.querySelectorAll('script').forEach(function(old){{
  var s=document.createElement('script');if(old.type)s.type=old.type;s.text=old.textContent;
  old.parentNode.replaceChild(s,old);
 }});}}
function openModal(slug,lang,push){{
 fetch('/api/center/'+slug+'/card?lang='+lang).then(function(r){{return r.text();}}).then(function(htm){{
  cmbody.innerHTML=htm;execScripts(cmbody);
  modal.style.display='flex';document.body.style.overflow='hidden';
  if(push)history.pushState({{slug:slug,lang:lang}},'','/'+slug+'?lang='+lang);
 }});}}
function closeModal(push){{
 modal.style.display='none';document.body.style.overflow='';
 if(window.__cmPollId){{clearInterval(window.__cmPollId);window.__cmPollId=null;}}
 if(push){{var qs=new URLSearchParams(location.search);var q=qs.get('q');
  history.pushState({{}},'','/'+(q?('?q='+encodeURIComponent(q)):''));}}
}}
document.querySelectorAll('.hex a').forEach(function(a){{
 a.addEventListener('click',function(e){{
  if(e.ctrlKey||e.metaKey||e.shiftKey||e.button===1)return;
  e.preventDefault();
  var g=a.closest('.hex');openModal(g.getAttribute('data-slug'),CUR_LANG,true);
 }});}});
document.getElementById('cmclose').onclick=function(){{closeModal(true);}};
modal.addEventListener('mousedown',function(e){{if(e.target===modal)closeModal(true);}});
window.addEventListener('keydown',function(e){{if(e.key==='Escape'&&modal.style.display!=='none')closeModal(true);}});
window.addEventListener('popstate',function(){{
 var m=location.pathname.match(/^\\/([a-z0-9-]+)$/);
 if(m){{var qs=new URLSearchParams(location.search);openModal(m[1],qs.get('lang')||CUR_LANG,false);}}
 else{{closeModal(false);}}
}});
{"document.body.style.overflow='hidden';" if modal_open else ""}
}})();
}})();</script>
{_footer_html()}
{_tracker_js((('center:' + open_slug) if modal_open else ('search:' + q if q else '')))}</body></html>"""
    return body


async def firms_grid(request):
    return web.Response(text=_firms_grid_body(request), content_type="text/html")


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
            "name": f"{CENTERS[parent]['name']} — Spin-off",
            "mandate": (f"A focused spin-off team from {CENTERS[parent]['name']}, "
                        f"formed because that team kept hitting the same gap"),
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
</div>
{_footer_html()}
</body></html>""", content_type="text/html")


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
app.router.add_get("/api/center/{slug}/card", center_card_handler)
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

# -------------------------------------------------------------------------
# /api/feedback — public, no auth (a visitor's 👍/👎 + note flows
# straight into the firm's autonomous learning record. Laura's wish:
# firms solve their own problems — real signal, not a black box.
# -------------------------------------------------------------------------
async def feedback_handler(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad json"}, status=400)
    slug = data.get("slug")
    value = data.get("value")
    note = str(data.get("note", ""))[:500]
    if not slug or value not in (1, -1):
        return web.json_response({"ok": False, "error": "slug+value required"}, status=400)
    try:
        import firm_foundation as FF
        kind = "feedback_positive" if value > 0 else "feedback_negative"
        FF.record_lesson(state, slug, kind, "visitor_feedback",
                             f"Visitor feedback ({value}): {note}",
                             meta={"value": value, "note": note})
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

app.router.add_post("/api/feedback", feedback_handler)


# -------------------------------------------------------------------------
# Autonomous cron runner (internal).
#
# The scheduled machines (briefing/spawn/evolve) run WITHOUT a state volume
# of their own — the canonical state.json lives on the app machine's volume.
# Instead of each cron maintaining a separate (ephemeral) copy, the cron
# machines simply POST here; the JOB RUNS INSIDE the app process, where
# state already lives and is persisted. This keeps one shared, durable
# state across all autonomous loops with no volume multi-attach needed.
#
# Auth: FT_CRON_KEY (fly secret). Without it, 401. The endpoint is internal
# only — never call it from the public client.
# -------------------------------------------------------------------------
CRON_KEY = os.environ.get("FT_CRON_KEY", "")


async def cron_run_handler(request):
    if not CRON_KEY:
        return web.json_response({"error": "cron key not configured"}, status=500)
    auth = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if auth != CRON_KEY:
        return web.json_response({"error": "unauthorized"}, status=401)
    job = request.match_info.get("job")
    if job == "spawn":
        import daily_spawn as DS
        report = await DS.scale_out()
        return web.json_response({"job": "spawn", "report": report})
    if job == "briefing":
        import daily_brief as DB
        # daily_brief.run() is async and uses the shared state module.
        report = await DB.run()
        return web.json_response({"job": "briefing", "report": report})
    if job == "evolve":
        # Mirror daily_evolve's panel + value-prop recursion, Laura-gated,
        # but run inside the app process so state persists. The Laura gate
        # is the Hermes MCP — if unavailable it blocks (honest, no self-approve).
        import daily_evolve as DE
        report = DE.main()
        return web.json_response({"job": "evolve", "report": report})
    if job == "reflect":
        # Autonomous firm foundation + learning pass (backend-only, no UI).
        import firm_foundation as FF
        summary = FF.reflect_all(state)
        return web.json_response({"job": "reflect", "summary": summary})
    if job == "product":
        # Proactively generate REAL sample products per firm via the live
        # engine (autonomy: firms make themselves useful, never placeholders).
        import firm_foundation as FF
        from runtime import CENTER_SLUGS
        made = 0
        failed = []
        for slug in CENTER_SLUGS:
            try:
                prod = FF.generate_sample_product(slug)
                if prod:
                    made += 1
                else:
                    failed.append(slug)
            except Exception as _e:
                failed.append(f"{slug}:{_e}")
        return web.json_response({"job": "product", "made": made,
                                   "total": len(CENTER_SLUGS),
                                   "failed": failed[:12]})

    return web.json_response({"error": f"unknown job: {job}"}, status=400)


app.router.add_post("/api/cron/run/{job}", cron_run_handler)

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


async def _scheduler(app):
    """In-app autonomous loop. Replaces the flaky external `fly machines run`
    schedulers: as long as the app is live (min_machines_running=1), these
    fire on their own. No human, no external cron machine required."""
    import asyncio as _asyncio
    from aiohttp import ClientSession as _CS

    async def _post(path):
        try:
            from aiohttp import ClientTimeout as _CT
            async with _CS() as s:
                key = os.environ.get("FT_CRON_KEY", "")
                async with s.post(
                    f"http://127.0.0.1:{os.environ.get('FT_PORT', '8091')}{path}",
                    headers={"Authorization": f"Bearer {key}"} if key else {},
                    timeout=_CT(total=120),
                ) as r:
                    return r.status
        except Exception as _e:
            print(f"[scheduler] {path} failed: {_e}", flush=True)
            return None

    jobs = {
        "reflect": 86400,   # daily
        "spawn": 86400,     # daily
        "briefing": 3600,  # hourly
        "evolve": 86400,    # daily
        "product": 86400,   # daily — refresh real sample products
    }
    # wait until the app itself is listening (boot can be slow: catalog
    # expansion + feedparser import on a 512MB machine). Poll async, don't
    # block the event loop with synchronous socket calls.
    port = int(os.environ.get("FT_PORT", "8091"))
    for _ in range(60):  # up to ~5 min
        try:
            _, writer = await _asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            break
        except (OSError, _asyncio.TimeoutError):
            await _asyncio.sleep(5)
    else:
        print("[scheduler] app port never opened; loops will retry on tick",
              flush=True)
    # fire once shortly after the app is up (staggered) then on interval
    await _asyncio.sleep(5)
    for name, interval in jobs.items():
        status = await _post(f"/api/cron/run/{name}")
        print(f"[scheduler] initial {name} -> {status}", flush=True)
    while True:
        await _asyncio.sleep(3600)
        # re-fire each job according to its cadence (simple per-hour tick)
        for name, interval in jobs.items():
            if int(time.time()) // 3600 % max(1, interval // 3600) == 0:
                status = await _post(f"/api/cron/run/{name}")
                print(f"[scheduler] {name} -> {status}", flush=True)


# Start the autonomous scheduler as a FIRE-AND-FORGET background task.
# aiohttp's on_startup awaits every callback, so we make this an async fn
# that spawns the scheduler task and returns immediately (the task runs on).
async def _start_scheduler(app):
    import asyncio as _asyncio
    _asyncio.create_task(_scheduler(app))


app.on_startup.append(_start_scheduler)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("FT_PORT", "8091")))
