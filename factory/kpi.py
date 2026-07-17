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
