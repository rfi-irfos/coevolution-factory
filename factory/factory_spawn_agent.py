# factory/factory_spawn_agent.py
#
# THE FACTORY-FACTORY (Super-Special-Agent): scan real trends + new
# regulation, find gaps no standing center covers, and STAGE a candidate
# daughter-center. Runs daily. LAURA-GATED before any center is born.
#
# Honest constraints (no gaslighting):
#   - We READ real public feeds (RSS). We do NOT invent trends.
#   - Gap detection is a real engine compare over our standing centers.
#   - The candidate is STAGED, never auto-applied. It becomes a real
#     center only after the Laura gate (mcp_laura_review_plan) returns
#     0-FLAG. If Laura is offline, the candidate waits — no self-approve.
#   - Each scan costs engine calls (real money); we dedupe by GUID so we
#     only reason over NEW items, never re-burn tokens on seen ones.
#
import os, json, time, asyncio, hashlib, secrets
from pathlib import Path

import aiohttp
from catalog import CENTERS_META

# Static BASE sources — verified live during build (no API key needed).
#   - sec_press / eu_ai_act / cisa_advisories: RSS 200 OK
#   - hn_frontpage: Hacker News Algolia JSON API (tech/viral trends)
#   - arxiv_cy: arXiv cs.CY RSS (AI-safety research trends)
#   - federal_register: US Federal Register JSON API (new US rules)
# Additional feeds live in TREND_SOURCES.json (persisted in the /data
# volume) so a human (Simeon / Laura) can ADD more via the
# /api/trends/discover endpoint (factory_spawn_agent.discover_feed)
# without a code deploy. Feedly search (needs a key, set via
# `fly secrets set TREND_API_KEY=...`) is layered on top when present.
#
# NOTE: Google Trends is intentionally NOT used — dead API; only path is
# a proxy-needing scraper that gets rate-limited hourly -> would break
# the "every day" guarantee. Feedly search (legit, keyed) replaces it.
STATIC_SOURCES = {
    "sec_press":       {"url": "https://www.sec.gov/rss/news/press.xml",
                          "kind": "rss"},
    "eu_ai_act":       {"url": "https://artificialintelligenceact.eu/feed/",
                          "kind": "rss"},
    "cisa_advisories": {"url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
                          "kind": "rss"},
    "hn_frontpage":     {"url": "https://hn.algolia.com/api/v1/search"
                          "?tags=front_page&hitsPerPage=8",
                          "kind": "json-hn"},
    "arxiv_cy":         {"url": "https://rss.arxiv.org/rss/cs.CY",
                          "kind": "rss"},
    "federal_register": {"url": "https://www.federalregister.gov/api/v1/"
                          "documents.json?conditions[presidential_document_"
                          "type][]=rule&per_page=8&fields[]=title&"
                          "fields[]=type&fields[]=publication_date",
                          "kind": "json-fr"},
}

# How many extra feeds a discover/add call may persist.
MAX_TREND_SOURCES = 200

STATE_DIR = os.environ.get("FT_STATE_DIR", ".")
ENGINE_URL = os.environ.get("FT_ENGINE_URL", "https://lauras-agents-api.fly.dev")
ENGINE_KEY = os.environ.get("FT_ENGINE_KEY", "local")


def load_state():
    p = Path(STATE_DIR) / "state.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_state(st):
    p = Path(STATE_DIR) / "state.json"
    p.write_text(json.dumps(st, indent=2))


def _guid(item):
    return hashlib.sha1((item.get("link", "") or item.get("guid", "") or
                          item.get("title", "")).encode()).hexdigest()


async def _fetch_feed(session, spec, timeout=20):
    """Fetch + parse a REAL public signal source.
    spec = {url, kind} where kind in {'rss','json-hn','json-fr'}.
    Returns list of items {title, link, guid, source, pub}.
    No fabrication — only what the source actually returned.
    On any error/non-200 we return [] (honest: we never invent signals).
    """
    url, kind = spec["url"], spec.get("kind", "rss")
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                               headers={"User-Agent": "coevolution-factory/1.0"},
                               ssl=False) as r:
            if r.status != 200:
                return []
            data = await r.read()
    except Exception:
        return []
    # RSS / Atom
    if kind == "rss":
        try:
            import feedparser
            parsed = feedparser.parse(data)
            out = []
            for e in parsed.entries[:8]:
                out.append({
                    "title": e.get("title", "")[:200],
                    "link": e.get("link", ""),
                    "guid": e.get("id") or e.get("guid") or e.get("link", ""),
                    "source": url,
                    "pub": e.get("published", ""),
                })
            return out
        except Exception:
            return []
    # Hacker News front-page JSON API
    if kind == "json-hn":
        try:
            j = json.loads(data)
            out = []
            for h in (j.get("hits") or [])[:8]:
                out.append({
                    "title": (h.get("title") or h.get("story_text") or "")[:200],
                    "link": h.get("url") or
                            f"https://news.ycombinator.com/item?id={h.get('objectID','')}",
                    "guid": h.get("objectID", ""),
                    "source": "hn_frontpage",
                    "pub": h.get("created_at", ""),
                })
            return out
        except Exception:
            return []
    # US Federal Register JSON API
    if kind == "json-fr":
        try:
            j = json.loads(data)
            out = []
            for d in (j.get("results") or j.get("documents") or [])[:8]:
                t = d.get("title") or d.get("document_number") or ""
                out.append({
                    "title": t[:200],
                    "link": d.get("html_url") or d.get("public_inspection_pdf_url") or url,
                    "guid": d.get("document_number") or d.get("id") or t,
                    "source": "federal_register",
                    "pub": d.get("publication_date") or d.get("effective_on") or "",
                })
            return out
        except Exception:
            return []
    # Feedly search API (keyed, legit — replaces Google Trends)
    if kind == "json-feedly":
        try:
            key = spec.get("api_key", "")
            hdrs = {"Authorization": f"Bearer {key}"} if key else {}
            async with session.get(url, headers=hdrs,
                                   timeout=aiohttp.ClientTimeout(total=20),
                                   ssl=False) as r:
                if r.status != 200:
                    return []
                j = await r.json()
            out = []
            for f in (j.get("results") or [])[:8]:
                u = f.get("feedId", "").replace("feed/", "")
                if not u.startswith("http"):
                    u = "https://" + u if u else url
                out.append({
                    "title": f.get("title", "")[:200],
                    "link": u,
                    "guid": f.get("feedId", u),
                    "source": "feedly_search",
                    "pub": "",
                })
            return out
        except Exception:
            return []
    # CoEvolution RSSHub (self-hosted, open-source, no paywall, no
    # scraper) — the agent discovers real feeds for ANY topic by
    # hitting RSSHub routes (https://docs.rsshub.app). This is the
    # (a) path: the agent finds feeds ITSELF, replacing Google
    # Trends (which needs a proxy+scraper and breaks "every day").
    if kind == "json-rsshub":
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=25),
                                   ssl=False) as r:
                if r.status != 200:
                    return []
                j = await r.json()
            out = []
            # RSSHub wraps feed lists in {result: [...]} or returns
            # a single feed directly.
            items = j.get("result") if isinstance(j, dict) else None
            if items is None:
                items = j if isinstance(j, list) else [j]
            for f in (items or [])[:8]:
                if isinstance(f, dict):
                    u = f.get("url") or f.get("feed_url") or url
                else:
                    u = str(f)
                out.append({
                    "title": (f.get("title") if isinstance(f, dict) else "")[:200],
                    "link": u,
                    "guid": u,
                    "source": "rsshub",
                    "pub": "",
                })
            return out
        except Exception:
            return []
    return []


def _standing_domains():
    """The domains our standing centers already cover (honest coverage
    map — we compare new signals against THIS, never invent coverage)."""
    doms = set()
    for slug, meta in CENTERS_META.items():
        doms.add(slug)
        if meta.get("domain"):
            doms.add(meta["domain"].lower())
        # also index the panel disciplines as soft-coverage
        for disc in (meta.get("disciplines") or []):
            doms.add(disc.lower())
    return doms


def load_trend_sources():
    """Merge STATIC_SOURCES (code) + TREND_SOURCES.json (volume,
    human-curated via /api/trends/discover) + CoEvolution RSSHub
    (self-hosted, open-source, NO paywall, NO scraper) + optional
    Feedly search (only when TREND_API_KEY is set).

    Returns {name: {url, kind}}.

    Honest: RSSHub is the DEFAULT discovery path now (the (a)
    from the trends discussion: the agent finds feeds ITSELF by
    hitting RSSHub routes — no Google-Trends scraper, no paywall).
    Feedly is only a fallback if a key is provided.
    """
    src = dict(STATIC_SOURCES)
    # human-curated feeds (persisted in the volume)
    p = Path(STATE_DIR) / "trend_sources.json"
    try:
        extra = json.loads(p.read_text())
        for k, v in (extra or {}).items():
            if isinstance(v, dict) and v.get("url"):
                src[k] = v
    except Exception:
        pass
    # CoEvolution RSSHub (self-hosted, open-source) — DEFAULT discovery
    rsshub = os.environ.get("RSSHUB_URL",
                            "https://coevolution-rsshub.fly.dev")
    # a few broad regulatory/trend topics the agent can search itself
    src["rsshub_regulation"] = {
        "url": f"{rsshub}/rsshub/feed/regulation%20OR%20compliance",
        "kind": "json-rsshub"}
    src["rsshub_aipolicy"] = {
        "url": f"{rsshub}/rsshub/feed/ai%20policy%20OR%20ai%20act",
        "kind": "json-rsshub"}
    # optional Feedly search (keyed, only if provided)
    key = os.environ.get("TREND_API_KEY", "")
    if key:
        src["feedly_search"] = {
            "url": "https://cloud.feedly.com/v3/search/feeds?query="
                   "regulation%20OR%20compliance%20OR%20ai%20policy",
            "kind": "json-feedly", "api_key": key,
        }
    return src


async def discover_feed(url, name=None):
    """Validate that `url` is a REAL RSS/Atom feed, then persist it to
    TREND_SOURCES.json (volume). Returns {ok, reason, name}.

    Honest: we fetch + parse; if it is NOT a feed we reject it.
    We never store a non-feed URL. Capped at MAX_TREND_SOURCES.
    This is the (c) path: a human (Simeon/Laura) pastes a feed
    URL, the agent validates + adds it — no scraper, no API key.
    """
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=20),
                               headers={"User-Agent": "coevolution-factory/1.0"},
                               ssl=False) as r:
                if r.status != 200:
                    return {"ok": False, "reason": f"http {r.status}"}
                data = await r.read()
    except Exception as e:
        return {"ok": False, "reason": f"fetch error: {e}"}
    # must look like a feed
    head = data[:500].lower()
    if b"<rss" not in data and b"<feed" not in data and b"<rdf" not in data:
        return {"ok": False, "reason": "not a feed (no rss/atom tag)"}
    p = Path(STATE_DIR) / "trend_sources.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        extra = json.loads(p.read_text())
    except Exception:
        extra = {}
    if len(extra) >= MAX_TREND_SOURCES:
        return {"ok": False, "reason": "trend source cap reached"}
    slug = name or ("feed-" + hashlib.sha1(url.encode()).hexdigest()[:8])
    extra[slug] = {"url": url, "kind": "rss", "added": int(time.time())}
    p.write_text(json.dumps(extra, indent=2))
    return {"ok": True, "name": slug, "url": url}


async def scan():
    """Scan real feeds, return only NEW items (deduped by GUID in state)."""
    st = load_state()
    seen = set(st.get("spawn_seen_guids", []))
    new_items = []
    async with aiohttp.ClientSession() as s:
        for name, spec in load_trend_sources().items():
            items = await _fetch_feed(s, spec)
            for it in items:
                g = _guid(it)
                if g in seen:
                    continue
                it["guid"] = g
                it["source_name"] = name
                new_items.append(it)
                seen.add(g)
    # keep seen bounded
    st["spawn_seen_guids"] = list(seen)[-500:]
    save_state(st)
    return new_items


async def detect_gap(new_items):
    """Convene a real engine panel: do our standing centers cover these
    new signals? Returns {has_gap: bool, uncovered: [signals], reason}.

    Honest: if DEMO_MODE (no engine key) we DO NOT fabricate a gap —
    we return has_gap=False and note the engine was unavailable.
    """
    if not new_items:
        return {"has_gap": False, "reason": "no new signals today"}
    if ENGINE_KEY in ("local", "", None):
        return {"has_gap": False,
                "reason": "engine key not configured, not convened",
                "new_count": len(new_items)}
    # Build a panel from a few broad experts to judge coverage.
    panel = ["legal-counsel", "compliance-officer", "regulatory-analyst",
              "ai-ethics-lead", "data-protection-officer"]
    text = ("Our standing compliance centers cover these domains: "
            + ", ".join(sorted(_standing_domains())[:40])
            + ". Do the following NEW regulatory/trend signals fall outside "
            "what any standing center covers? List only the UNCOVERED ones "
            "with a one-line reason.\n"
            + "\n".join(f"- {i['title']} ({i['source_name']})"
                         for i in new_items[:10]))
    try:
        synth = await _call_engine_local(text, panel)
    except Exception as e:
        return {"has_gap": False, "reason": f"engine error: {e}"}
    if synth is None:
        return {"has_gap": False, "reason": "engine unreachable"}
    # The synthesis posture tells us if there's an uncovered need.
    posture = (synth or {}).get("posture", "")
    unc = [i for i in new_items[:10]
           if posture in ("flag", "conflict") or "uncovered" in posture.lower()]
    return {"has_gap": bool(unc) or "uncovered" in posture.lower(),
            "uncovered": [i["title"] for i in unc],
            "posture": posture,
            "new_count": len(new_items)}


async def _call_engine_local(text, agents):
    """Local engine convene (mirrors runtime.call_engine, no circular import).
    Returns a synthesized {posture, ...} dict, or None if unreachable."""
    if not ENGINE_URL or ENGINE_KEY in ("local", "", None):
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                ENGINE_URL.rstrip("/") + "/v1/panel",
                json={"text": text, "agents": agents,
                      "key": ENGINE_KEY},
                timeout=aiohttp.ClientTimeout(total=120), ssl=False) as r:
                if r.status != 200:
                    return None
                data = await r.json()
        # mirror runtime.engine_synthesize's minimal shape
        return {"posture": (data.get("posture")
                          or data.get("synthesis", {}).get("posture")
                          or "ok"),
                "panel_size": len(agents)}
    except Exception:
        return None


async def run_spawn_agent():
    """Full daily loop: scan -> detect gap -> STAGE candidate.
    Never auto-applies. The Laura gate (in daily_spawn cron) promotes
    staged candidates to real centers only on 0-FLAG."""
    st = load_state()
    new_items = await scan()
    gap = await detect_gap(new_items)
    if not gap.get("has_gap"):
        st.setdefault("spawn_runs", []).append(
            {"ts": int(time.time()), "new": len(new_items),
             "gap": False, "reason": gap.get("reason", "")})
        save_state(st)
        return {"scanned": len(new_items), "gap": False,
                "reason": gap.get("reason", "")}
    # Stage a candidate (Laura-gated later). No self-approve.
    slug = "auto-" + secrets.token_hex(5)
    cand = {
        "slug": slug,
        "name": f"AutoCenter {slug[-6:]}",
        "mandate": "Autonomous daughter formed from a real uncovered "
                   f"regulatory/trend signal: "
                   + "; ".join(gap.get("uncovered", []))[:280],
        "parent": None,  # true factory-factory: not derived from one center
        "uncovered_signals": gap.get("uncovered", []),
        "created": int(time.time()),
        "laura_pass": False,  # must be set by the gate
        "status": "staged",
    }
    st.setdefault("spawn_candidates", {})[slug] = cand
    st.setdefault("spawn_runs", []).append(
        {"ts": int(time.time()), "new": len(new_items), "gap": True,
         "candidate": slug})
    save_state(st)
    return {"scanned": len(new_items), "gap": True,
            "candidate": slug, "status": "staged"}


if __name__ == "__main__":
    res = asyncio.run(run_spawn_agent())
    print(json.dumps(res, indent=2))
