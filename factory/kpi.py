"""Per-firm KPI tracking + lunar review cycle (Simeon Q&A #4, simeon approves).

Every firm tracks itself in its own centralized kpi.yaml. Metrics flow in
continuously (products shipped, partner score, ecocentric pass-rate, etc.).
The lunar phase drives the cycle:
  - last_quarter : REVIEW + ADJUST (what worked, what to fix) -> carry to new moon
  - new_moon     : set NEW PLANS from the reviewed KPI trend
  - first_quarter: launch the plans
  - full_moon    : peak validation

No hard-sell, ecocentric-gated, 12h pulse feeds the KPIs. The firm knows
itself across time — the file persists, not just memory.
"""
import os
from datetime import datetime, timezone

import yaml  # PyYAML — already a dep via aiohttp stack? if not, fallback below
import governance as G


def kpi_path(slug, base=None):
    base = base or os.environ.get("FT_STATE_DIR", ".")
    return os.path.join(base, "kpi", f"{slug}.yaml")


def load_kpi(slug, base=None):
    p = kpi_path(slug, base)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {"slug": slug, "metrics": {}, "history": [], "plans": []}


def track_kpi(slug, metric, value, base=None, ts=None):
    """Spül a metric into the firm's kpi.yaml. Persistent, self-knowledge."""
    k = load_kpi(slug, base)
    k.setdefault("metrics", {})
    k["metrics"][metric] = value
    k.setdefault("history", []).append({
        "ts": ts or int(datetime.now(timezone.utc).timestamp()),
        "metric": metric, "value": value,
    })
    # keep history bounded
    if len(k["history"]) > 500:
        k["history"] = k["history"][-500:]
    p = kpi_path(slug, base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        yaml.safe_dump(k, f, sort_keys=False)
    return k


def review_at_last_quarter(slug, base=None):
    """Last-quarter REVIEW + ADJUST.

    Load KPIs, run an ecocentric check on the firm's recent trajectory,
    produce adjustments (what to keep / fix), carry them to the new-moon
    plan slot. Returns the adjustment record.
    """
    k = load_kpi(slug, base)
    # simple ecocentric pass-rate from tracked metrics
    eco_pass = k["metrics"].get("ecocentric_pass_rate", 1.0)
    partner = k["metrics"].get("partner_score", 0.0)
    # adjustment logic (deterministic, no engine call)
    if eco_pass < 0.5:
        adjust = "halt_self_serving_actions; re-anchor ecocentric"
    elif partner <= 0.0:
        adjust = "no partner yet; keep useful, do not hard-sell"
    else:
        adjust = "compounding; keep rhythm"
    rec = {
        "reviewed_at": "last_quarter",
        "ecocentric_pass_rate": eco_pass,
        "partner_score": partner,
        "adjust": adjust,
    }
    k.setdefault("plans", []).append({"phase": "last_quarter_adjust",
                                       "record": rec})
    p = kpi_path(slug, base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        yaml.safe_dump(k, f, sort_keys=False)
    return rec


def plan_at_new_moon(slug, base=None):
    """New-moon PLAN. Build next plans from the reviewed KPI trend."""
    k = load_kpi(slug, base)
    trend = k.get("metrics", {})
    # plans are the firm's own; we just stamp the new-moon intent
    plan = {
        "phase": "new_moon",
        "from_kpi": trend,
        "min_legal_paths": G.MIN_LEGAL_PATHS,
        "experiment_window_days": G.EXPERIMENT_WINDOW_DAYS,
        "orientation": G.ORIENTATION,
    }
    k.setdefault("plans", []).append(plan)
    p = kpi_path(slug, base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        yaml.safe_dump(k, f, sort_keys=False)
    return plan


# --- Pheromone / Mycelium model (Simeon Q&A #7, simeon approves) ------------
# How does nature validate? Mycelium networks + pheromone trails. No central
# boss decides if a value-prop is good — the collective trail strength does.
# Every good action leaves pheromone (partner found, ecocentric pass,
# recurrence). Weak trails evaporate. A value-prop with a strong trail is
# validated; one whose trail evaporates is stale -> evolve.py rewrites it.
PHEROMONE_MODEL = True
PHEROMONE_WEIGHTS = {
    "partner": 1.0,        # referral -> strong trail
    "ecocentric_pass": 0.5,
    "recurrence": 0.3,
    "hard_sell": -1.0,     # self-serving -> anti-trail (evaporates)
}
VP_STRENGTH_FLOOR = 1.0   # below this, value-prop is stale -> rewrite


def track_pheromone(slug, action, base=None):
    """Leave a pheromone trail for a good/bad action. Persists in kpi.yaml."""
    w = PHEROMONE_WEIGHTS.get(action, 0.0)
    k = load_kpi(slug, base)
    k.setdefault("pheromones", {})
    k["pheromones"][action] = k["pheromones"].get(action, 0.0) + w
    k.setdefault("history", []).append({"ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
                                        "pheromone": action, "weight": w})
    p = kpi_path(slug, base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        yaml.safe_dump(k, f, sort_keys=False)
    return k["pheromones"]


def vp_strength(slug, base=None):
    """Trail strength = sum of pheromones. High = validated VP; low = stale."""
    k = load_kpi(slug, base)
    ph = k.get("pheromones", {})
    return round(sum(ph.values()), 3)


def mycelium_share(slugs, base=None):
    """Mycelium: firms share their trail strength with each other (decentral).

    Returns a mapping slug -> vp_strength so any firm can read the collective
    without a central authority. Nature has no CEO; the network knows.
    """
    return {s: vp_strength(s, base=base) for s in slugs}


# --- Revenue tracking (Simeon Q&A #8, simeon approves) ----------------------
# Firms track their OWN revenue in kpi.yaml (decentral, like every other
# metric). We (Lighthouse OS) aggregate it into a Finance tab as a separate
# cashflow line next to Merch. Ecocentric-gated: only PARTNER revenue counts;
# hard-sell revenue is banned (not counted). Cumulative toward the 2040
# Jubilaeum party-payer logic.
REVENUE_SOURCES_OK = {"partner", "ecocentric", "recurring", "referral"}
REVENUE_SOURCES_BAN = {"hard_sell", "churn", "manipulation"}


def track_revenue(slug, amount_eur, source, base=None):
    """Firm tracks its own revenue. Only ecocentric/partner sources count.

    source in REVENUE_SOURCES_OK -> added to cumulative revenue.
    source in REVENUE_SOURCES_BAN -> rejected (not counted, anti-trail).
    Returns the firm's cumulative revenue (float).
    """
    if source in REVENUE_SOURCES_BAN:
        # banned source: do not count, leave a rejection marker
        k = load_kpi(slug, base)
        k.setdefault("rejected_revenue", []).append({
            "amount": amount_eur, "source": source,
            "ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
        })
        _save(k, base)
        return k.get("revenue_eur", 0.0)
    if source not in REVENUE_SOURCES_OK:
        # unknown source -> treat as not-yet-validated, hold (tend), don't count
        return load_kpi(slug, base).get("revenue_eur", 0.0)
    k = load_kpi(slug, base)
    k["revenue_eur"] = round(k.get("revenue_eur", 0.0) + amount_eur, 2)
    k.setdefault("history", []).append({
        "ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
        "revenue": amount_eur, "source": source,
    })
    _save(k, base)
    return k["revenue_eur"]


def _save(k, base):
    p = kpi_path(k.get("slug", "_"), base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        yaml.safe_dump(k, f, sort_keys=False)


def lighthouse_cashflow(slugs, base=None):
    """Aggregate all firms' revenue into the Lighthouse OS Finance tab.

    Returns {"cashflow": total, "lines": {slug: revenue}, "party_payer": slug}.
    This is the 'CoEvolution Cashflow' line, separate from Merch. The highest
    earner by 2040 Jubilaeum pays the party (transparent).
    """
    lines = {s: vp_revenue(s, base=base) for s in slugs}
    total = round(sum(lines.values()), 2)
    party_payer = max(lines, key=lambda s: lines[s]) if lines else None
    return {"cashflow": total, "lines": lines, "party_payer": party_payer}


def vp_revenue(slug, base=None):
    """Cumulative revenue for a firm (ecocentric-gated, partner-only)."""
    return load_kpi(slug, base).get("revenue_eur", 0.0)


# --- Active mycelium collaboration (Simeon Q&A #9, simeon approves) ---------
# Nature's juice: not just reading trails, but BROADCASTING them. A firm that
# finds a solution leaves a pheromone trail that pulls other firms toward the
# problem — no central boss, the network self-organizes like ants. Firms
# broadcast their strength + solved problems + mandate; gaps get pooled so
# others can spawn (Q&A #5) instead of duplicating.
MYCELIUM_ACTIVE = True


def broadcast(slug, base=None):
    """A firm broadcasts its trail into the mycelium (decentral, no boss).

    Writes a broadcast record (vp_strength, problems_solved, mandate, revenue)
    that any other firm can read to coordinate — find gaps, avoid clones.
    """
    k = load_kpi(slug, base)
    CENTERS = _catalog_centers()
    broadcast_rec = {
        "slug": slug,
        "vp_strength": vp_strength(slug, base=base),
        "problems_solved": k.get("metrics", {}).get("problems_solved", 0),
        "mandate": CENTERS.get(slug, {}).get("mandate", ""),
        "revenue_eur": k.get("revenue_eur", 0.0),
        "ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
    }
    k.setdefault("mycelium", {})["broadcast"] = broadcast_rec
    k.setdefault("history", []).append({"ts": broadcast_rec["ts"], "mycelium_broadcast": True})
    _save(k, base)
    return broadcast_rec


def broadcast_gap(slug, gap_description, base=None):
    """A firm found a problem no one covers — pool it in the mycelium.

    Other firms can read gaps and decide to spawn (Q&A #5) rather than
    duplicate. No central allocator; the trail pulls the right firm.
    """
    k = load_kpi(slug, base)
    gap = {
        "from": slug,
        "gap": gap_description,
        "ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
    }
    k.setdefault("mycelium", {}).setdefault("gaps", []).append(gap)
    _save(k, base)
    return gap


def mycelium_index(slugs, base=None):
    """Collective read of all firms' broadcasts (the living mycelium map).

    Returns {slug: broadcast_rec}. Decentral: each firm wrote its own; we just
    read the network. Reveals strengths (where trails are strong) and gaps
    (where no trail exists) — nature's self-organizing coordination.
    """
    out = {}
    for s in slugs:
        rec = load_kpi(s, base).get("mycelium", {}).get("broadcast")
        if rec:
            out[s] = rec
    return out


def _catalog_centers():
    """Light import of catalog centers (mandate) without hard dependency."""
    try:
        import catalog
        return {s: {"mandate": c.get("mandate", "")} for s, c in catalog.CENTERS_META.items()}
    except Exception:
        return {}


def mycelium_gaps(slugs, base=None):
    """Collective read of all pooled gaps across the mycelium."""
    gaps = []
    for s in slugs:
        g = load_kpi(s, base).get("mycelium", {}).get("gaps", [])
        gaps.extend(g)
    return gaps


# --- Succession: a firm never dies (Simeon Q&A #12, simeon approves) -------
# A firm does NOT die. When its trail evaporates (no more partners, no
# pheromone), it does not vanish — it goes to seed: disperses into the wind,
# feeding the others. Its KPIs, pheromones, and knowledge spread through the
# mycelium so other firms grow stronger. Like a tree becoming humus. Nature
# has no death, only succession. No firm is ever deleted; it transitions to
# "dispersed" and nourishes the network.
NO_FIRM_DEATH = True
DISPERSED_STATE = "dispersed"  # went to seed, feeding the mycelium


def disperse_to_wind(slug, base=None):
    """A firm goes to seed: disperses its knowledge into the wind/mycelium.

    Marks the firm 'dispersed' (never deleted) and broadcasts its accumulated
    KPIs + pheromones as nourishment for other firms. Returns the dispersed
    record other firms can absorb.
    """
    k = load_kpi(slug, base)
    k["state"] = DISPERSED_STATE
    nourishment = {
        "slug": slug,
        "pheromones": k.get("pheromones", {}),
        "metrics": k.get("metrics", {}),
        "revenue_eur": k.get("revenue_eur", 0.0),
        "problems_solved": k.get("metrics", {}).get("problems_solved", 0),
        "ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
    }
    k.setdefault("mycelium", {})["dispersed"] = nourishment
    k.setdefault("history", []).append({"ts": nourishment["ts"], "dispersed_to_wind": True})
    _save(k, base)
    return nourishment


def absorb_nourishment(slug, nourishment, base=None):
    """Another firm absorbs dispersed knowledge from the wind (succession).

    The receiving firm's trail strengthens from the nourishment it absorbs —
    the network grows, no one is lost. Returns updated vp_strength.
    """
    k = load_kpi(slug, base)
    # merge pheromones (absorbs the dispersed firm's trail)
    incoming = nourishment.get("pheromones", {})
    ph = k.setdefault("pheromones", {})
    for action, w in incoming.items():
        ph[action] = ph.get(action, 0.0) + w
    k.setdefault("history", []).append({
        "ts": int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp()),
        "absorbed_from": nourishment.get("slug"),
    })
    _save(k, base)
    return vp_strength(slug, base=base)
