"""Governance defaults — Simeon's hard-coded decisions for ALL firms.

These are NOT suggestions. They are the operating constitution for every
CoEvolution firm (standing center, daughter, spawned candidate). Set once,
applied to all. Changed only by an explicit "simeon approves" decision.

Doctrine (Q&A session 2026-07-17, simeon approves):
  * FIRMS ARE AGENTS. Every firm pings every 12h (heartbeat). No "7 days of
    silence" panic trigger — regular pulse, then decide.
  * ACTION THRESHOLD: on each 12h ping, the firm checks its state. If it
    recognises "ok we must act now" (no traffic, no value delivered, no
    ecocentric traction), it MUST act.
  * MIN LEGAL PATHS = 3. Never A/B. Always A/B/C. (Core RFI-IRFOS doctrine:
    if a thing doesn't work, there are always >=3 legal alternatives.)
  * EXPERIMENT WINDOW = 7 days. The 3 paths are run as A/B/C strategy tests
    for one week with data collection. Never only A/B.
  * ORIENTATION = ecocentric. Firms must make themselves useful in the real
    physical world (Wall-E mode), not "human-centered optimized". A hypothesis
    is valid only if it is good for everything, not just us.
  * DEFAULT STATE = tend. Firms start in uncertainty/hold, not affirm. They
    raise hypotheses and validate slowly (Wall-E collecting), never rush.
  * LUNAR PLAN TRACKING: deterministic moon-phase cycle drives plan rhythm:
      new moon        -> set new plans
      first quarter   -> launch
      full moon       -> peak / validation
      last quarter    -> review / wind down
    Computed locally (no API, no network) — 29.53-day synodic period.

All values here are the single source of truth. runtime/virtual_firm/daily_spawn
import DEFAULTS and never re-decide these locally.
"""
from datetime import datetime, timezone

# Heartbeat: every firm pings itself this often (hours).
PING_INTERVAL_HOURS = 12

# Action threshold: a firm MUST act when its 12h ping shows no traction.
# "no traction" = zero sessions AND zero revenue in the trailing window.
ACTION_TRAILING_HOURS = 12  # evaluate the last ping window

# Minimum number of distinct legal paths a firm must propose before acting.
MIN_LEGAL_PATHS = 3

# A/B/C experiment duration (days). Never shorter, never only A/B.
EXPERIMENT_WINDOW_DAYS = 7

# Worldview for hypothesis validation.
ORIENTATION = "ecocentric"  # not "human-centered"

# Ecocentric by design = ternary logic. A firm must ask "is this really the
# best decision for the whole, or does it only serve one party and harm the
# rest?" Human-centered thinking puts the self at the center; ecocentric puts
# the whole. Ternary logic already does this: an action that only benefits one
# side and violates others gets a HARD VETO (no launch, no sale). The model is
# allowed to say "no — this would only help you and hurt everything else."
# Firms validate in `tend` (Wall-E mode): if it is unclear whether it serves
# the whole, they hold, never rush.
ECOCENTRIC_CHECK = "ternary_veto"
ECOCENTRIC_VETO = "hard"  # a self-serving action is vetoed regardless of other dims

# What a LEAD actually is (Simeon's definition, 2026-07-17):
# A lead is NOT a churn-risk subscription we squeeze. A lead is a recurring
# PARTNER we still have in 50 years, who refers NEW leads by word-of-mouth
# because the fit is real — not because we hard-sell. Quality compounds;
# aggression does not. Firms never "try hard"; they are useful (Wall-E / eco),
# and partners arrive on their own. We do not sell people junk they don't need.
LEAD_DEFINITION = (
    "recurring_partner_not_churn_risk: brings referral leads via real fit, "
    "not via hard-sell; still ours in 50 years"
)
LEAD_QUALITY_METRIC = "referral_coefficient"  # partners earned per partner (word-of-mouth)
LEAD_HORIZON_YEARS = 50
NO_HARD_SELL = True  # quality pulls partners; aggression repels them
LEAD_SCORE_DIMENSIONS = ["recurrence", "referral", "fit", "no_hard_sell"]

# Design lens for everything (Simeon core directive, 2026-07-17):
# WWND = "What Would Nature Do?" + BBTR = "Back To The Roots" protocol.
# Before any build/design decision, model it on biology/ecology, NOT Silicon
# Valley. If unsure how to build, go to a nature reference — it "just runs".
# Hard bans: growth-hacking, dark patterns, hard-sell, central boss authority,
# crash-on-undefined, churn-squeeze, redundant clones. These are all already
# encoded in the constitution below (ecocentric veto, mycelium, tend-default,
# 50-year partner leads, >=3 paths, distinct daughters).
DESIGN_LENS = "wwnd"          # What Would Nature Do?
NO_SILICON_VALLEY = True      # no SV dark patterns, ever
BBTR_PROTOCOL = True          # Back To The Roots: nature reference first


# Firms begin in hold/uncertainty, not affirm.
DEFAULT_STATE = "tend"

# 0-status IS the default (Simeon Q&A #6). A "divide by zero" never crashes
# us: when a signal is undefined / ambiguous, the firm AUTOMATICALLY falls to
# 0 (tend / hold) and keeps collecting data before acting. There is no
# "engine down" panic — tend is the safe resting state. Doing nothing is
# often faster and safer than doing something. This is the power of ternary,
# and our elevator pitch: "Doing nothing is often faster and safer than
# doing something."
ZERO_STATUS_IS_DEFAULT = True
TEND_ON_UNDEFINED = True  # ambiguous signal -> 0, never an error/panic


def resolve_signal(signal):
    """Map any signal to a firm decision. Never raises.

    signal may be: None, 0, a trit (-1/0/1), or an unclear/ambiguous value.
    Returns one of: "reject" (-1), "tend" (0, default), "affirm" (1).
    Undefined / ambiguous -> tend (the firm collects more data, acts later).
    """
    if signal is None:
        return "tend"
    if isinstance(signal, (int, float)):
        if signal > 0:
            return "affirm"
        if signal < 0:
            return "reject"
        return "tend"  # signal == 0 -> hold, the safe default
    # non-numeric / ambiguous -> never crash, fall to tend
    return "tend"


# Lunar cycle (deterministic, no API).
LUNAR_PERIOD_DAYS = 29.53059
# Reference new moon (UTC). Known astronomical value; anchor for all phases.
_REFERENCE_NEW_MOON = datetime(2026, 7, 14, 10, 43, 0, tzinfo=timezone.utc)


def lunar_phase_name(dt=None):
    """Return (phase_name, days_since_new_moon, illumination_0_1) for dt.

    phase_name ∈ {new, first_quarter, full, last_quarter, waxing, waning}.
    Deterministic — no network. Used by firms to track plan rhythm.
    """
    dt = dt or datetime.now(timezone.utc)
    delta_days = (dt - _REFERENCE_NEW_MOON).total_seconds() / 86400.0
    phase = (delta_days % LUNAR_PERIOD_DAYS) / LUNAR_PERIOD_DAYS  # 0..1
    # illumination proxy: 0 at new moon, 1 at full moon
    import math
    illum = round((1 - math.cos(2 * math.pi * phase)) / 2, 3)
    if phase < 0.0625 or phase >= 0.9375:
        name = "new"
    elif phase < 0.1875:
        name = "waxing"
    elif phase < 0.3125:
        name = "first_quarter"
    elif phase < 0.4375:
        name = "waxing"
    elif phase < 0.5625:
        name = "full"
    elif phase < 0.6875:
        name = "waning"
    elif phase < 0.8125:
        name = "last_quarter"
    else:
        name = "waning"
    return name, round(delta_days % LUNAR_PERIOD_DAYS, 2), illum


def plan_phase(dt=None):
    """Map the current lunar phase to the firm's plan action."""
    name, _, _ = lunar_phase_name(dt)
    return {
        "new": "set_new_plans",
        "first_quarter": "launch",
        "full": "peak_validation",
        "last_quarter": "review_wind_down",
        "waxing": "build",
        "waning": "consolidate",
    }.get(name, "build")


# Single source of truth for all firms.
DEFAULTS = {
    "ping_interval_hours": PING_INTERVAL_HOURS,
    "action_trailing_hours": ACTION_TRAILING_HOURS,
    "min_legal_paths": MIN_LEGAL_PATHS,
    "experiment_window_days": EXPERIMENT_WINDOW_DAYS,
    "orientation": ORIENTATION,
    "ecocentric_check": ECOCENTRIC_CHECK,
    "ecocentric_veto": ECOCENTRIC_VETO,
    "default_state": DEFAULT_STATE,
    "lunar_period_days": LUNAR_PERIOD_DAYS,
}


def evaluate_ecocentric(human_trit, eco_trit, systemic_trit=None):
    """Ecocentric gate for a firm action.

    Args (each a trit: -1 reject / 0 tend / +1 affirm):
      human_trit   : does it serve the human/requester?
      eco_trit     : does it serve the wider system (ecocentric view)?
      systemic_trit: does it serve long-term resilience (optional)?

    Rule (Simeon's doctrine): if it serves ONLY the human and HARMS the eco
    (or systemic) view, it is a self-serving action -> HARD VETO.
    Returns ("veto"|"hold"|"pass", reason).
    """
    if human_trit > 0 and eco_trit < 0:
        return ("veto", "serves only the requester; harms the wider whole")
    if systemic_trit is not None and human_trit > 0 and systemic_trit < 0:
        return ("veto", "serves only the requester; harms long-term resilience")
    if eco_trit == 0 or (systemic_trit is not None and systemic_trit == 0):
        return ("hold", "unclear whether it serves the whole; hold in tend")
    if human_trit <= 0 and eco_trit <= 0:
        return ("veto", "serves nobody; reject")
    return ("pass", "serves the whole, not only the self")


# When a firm may spawn a NEW daughter (Simeon Q&A #5, simeon approves):
# A daughter must be SO autonomous + differently-colored that there is no
# conflict of interest. Never similar firms. Every firm needs >=3 core
# primitives, must be legal, must solve a real physical-world problem, and
# must be crisis-resistant.
MIN_CORE_PRIMITIVES = 3
FORBIDDEN_DOMAINS = {"weapons", "surveillance-abuse", "illicit", "disinfo"}
SIMILARITY_BAN = True  # no two firms may be near-duplicates


def should_spawn_daughter(proposal, existing_slugs=None, existing_primitives=None):
    """Gate a daughter proposal against Simeon's spawn constitution.

    proposal = {
      "name", "slug", "mandate",
      "core_primitives": [..],        # >=3 required
      "legal": bool,                  # must be legal
      "solves_real_problem": bool,    # physical-world, ecocentric
      "crisis_resistant": bool,       # demand survives downturns
    }
    Returns (bool allowed, reason).
    """
    primitives = proposal.get("core_primitives", [])
    if len(primitives) < MIN_CORE_PRIMITIVES:
        return (False, f"needs >= {MIN_CORE_PRIMITIVES} core primitives, got {len(primitives)}")
    if not proposal.get("legal", False):
        return (False, "not legal — hard ban")
    # forbidden domain check
    mandate_l = (proposal.get("mandate", "") + " " + proposal.get("name", "")).lower()
    for dom in FORBIDDEN_DOMAINS:
        if dom in mandate_l:
            return (False, f"forbidden domain: {dom}")
    if not proposal.get("solves_real_problem", False):
        return (False, "does not solve a real physical-world problem")
    if not proposal.get("crisis_resistant", False):
        return (False, "not crisis-resistant")
    # no conflict of interest / no near-duplicate
    if SIMILARITY_BAN and existing_slugs:
        slug = proposal.get("slug", "")
        if slug in existing_slugs:
            return (False, "slug already exists — no duplicate firms")
        # similarity via core primitives: if a proposed daughter shares too
        # many primitives with an existing firm, it is a near-duplicate (no
        # conflict of interest / no redundant firms).
        new_prims = set(proposal.get("core_primitives", []))
        for ex_prims in (existing_primitives or []):
            ex_set = set(ex_prims)
            if ex_set and len(new_prims & ex_set) / min(len(new_prims), len(ex_set)) > 0.6:
                return (False, "too similar to an existing firm — no near-duplicates")
    return (True, "autonomous, distinct, legal, real-world, crisis-resistant")


def score_lead(recurrence=0, referral=0, fit=0.0, hard_sell_attempt=False):
    """Score a lead the Simeon way — not churn-risk, but 50-year partner.

    Dimensions (all privacy-first, no PII, no engine call):
      recurrence : how many times this partner returned (0 = one-off)
      referral   : partners this lead has already referred (word-of-mouth)
      fit        : 0..1 how well our offering matches their real need
      hard_sell_attempt: did WE push? (true -> disqualifies; we don't chase)
    Returns (0..1 score, tier).
    """
    if hard_sell_attempt:
        # we never hard-sell; a lead born from our pushing is not a real partner
        return (0.0, "rejected_hard_sell")
    if fit <= 0.0:
        return (0.0, "no_fit")
    # quality compounds: recurrence + referral dominate; fit is the gate
    raw = (recurrence * 0.35) + (referral * 0.45) + (fit * 0.20)
    score = round(min(raw, 1.0), 3)
    if referral >= 1:
        tier = "partner"          # brings others -> compounding
    elif recurrence >= 3:
        tier = "recurring"
    elif fit >= 0.7:
        tier = "fit"
    else:
        tier = "cold"
    return (score, tier)
