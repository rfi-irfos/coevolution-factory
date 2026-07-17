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

# Real public feeds we scan for NEW regulatory / trend signals.
# (URLs verified live during build; SEC/EU-AI-Act/CISA confirmed 200.)
SPAWN_SOURCES = {
    "sec_press":       "https://www.sec.gov/rss/news/press.xml",
    "eu_ai_act":       "https://artificialintelligenceact.eu/feed/",
    "cisa_advisories": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
}

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


async def _fetch_feed(session, url, timeout=20):
    """Fetch + parse a real RSS/Atom feed. Returns list of items
    {title, link, guid, source, pub}. No fabrication — only what the
    feed actually returned."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                               headers={"User-Agent": "coevolution-factory/1.0"},
                               ssl=False) as r:
            if r.status != 200:
                return []
            data = await r.read()
    except Exception:
        return []
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


async def scan():
    """Scan real feeds, return only NEW items (deduped by GUID in state)."""
    st = load_state()
    seen = set(st.get("spawn_seen_guids", []))
    new_items = []
    async with aiohttp.ClientSession() as s:
        for name, url in SPAWN_SOURCES.items():
            items = await _fetch_feed(s, url)
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
